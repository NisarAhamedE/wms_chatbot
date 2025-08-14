"""
Advanced security middleware for WMS Chatbot API
Provides rate limiting, DDoS protection, input validation, and threat detection
"""

import asyncio
import time
import json
import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from ipaddress import IPv4Network, IPv6Network, AddressValueError, ip_address
from collections import defaultdict, deque
import aioredis
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import jwt

from src.core.config import get_settings
from src.core.audit import get_audit_logger, AuditEventType

logger = logging.getLogger(__name__)

class ThreatLevel(Enum):
    """Security threat levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RateLimitType(Enum):
    """Rate limit types"""
    PER_IP = "per_ip"
    PER_USER = "per_user"
    PER_ENDPOINT = "per_endpoint"
    GLOBAL = "global"

@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int
    requests_per_hour: int
    burst_limit: int
    window_size: int = 60  # seconds
    block_duration: int = 300  # seconds

@dataclass
class SecurityThreat:
    """Security threat detection"""
    threat_id: str
    threat_type: str
    threat_level: ThreatLevel
    source_ip: str
    timestamp: datetime
    details: Dict[str, Any]
    blocked: bool = False

@dataclass
class ClientInfo:
    """Client information tracking"""
    ip_address: str
    user_agent: str
    first_seen: datetime
    last_seen: datetime
    request_count: int = 0
    blocked_until: Optional[datetime] = None
    threat_score: float = 0.0
    violations: List[str] = field(default_factory=list)

class PatternMatcher:
    """Pattern matching for threat detection"""
    
    # Common attack patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bunion\b.*\bselect\b)",
        r"(\bselect\b.*\bfrom\b.*\bwhere\b.*['\"].*['\"])",
        r"(\bor\b.*['\"].*['\"].*=.*['\"].*['\"])",
        r"(\bdrop\b.*\btable\b)",
        r"(\binsert\b.*\binto\b.*\bvalues\b)",
        r"(\bupdate\b.*\bset\b)",
        r"(\bdelete\b.*\bfrom\b)",
        r"(['\"];.*--)",
        r"(\bexec\b.*\()",
        r"(\bscript\b.*>)"
    ]
    
    XSS_PATTERNS = [
        r"(<script[^>]*>.*?</script>)",
        r"(javascript:)",
        r"(on\w+\s*=)",
        r"(<iframe[^>]*>)",
        r"(<object[^>]*>)",
        r"(<embed[^>]*>)",
        r"(<link[^>]*>)",
        r"(<meta[^>]*>)"
    ]
    
    COMMAND_INJECTION_PATTERNS = [
        r"([;&|`])",
        r"(\$\([^)]*\))",
        r"(\`[^`]*\`)",
        r"(;.*rm\b)",
        r"(;.*wget\b)",
        r"(;.*curl\b)",
        r"(;.*nc\b)",
        r"(\|.*sh\b)"
    ]
    
    def __init__(self):
        self.sql_regex = re.compile('|'.join(self.SQL_INJECTION_PATTERNS), re.IGNORECASE)
        self.xss_regex = re.compile('|'.join(self.XSS_PATTERNS), re.IGNORECASE)
        self.command_regex = re.compile('|'.join(self.COMMAND_INJECTION_PATTERNS), re.IGNORECASE)
    
    def detect_sql_injection(self, text: str) -> bool:
        """Detect SQL injection patterns"""
        return bool(self.sql_regex.search(text))
    
    def detect_xss(self, text: str) -> bool:
        """Detect XSS patterns"""
        return bool(self.xss_regex.search(text))
    
    def detect_command_injection(self, text: str) -> bool:
        """Detect command injection patterns"""
        return bool(self.command_regex.search(text))

class RateLimiter:
    """Advanced rate limiting with Redis backend"""
    
    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.local_cache: Dict[str, Dict] = {}
        self.default_config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=1000,
            burst_limit=20
        )
        
        # Endpoint-specific configurations
        self.endpoint_configs = {
            "/api/v1/chat": RateLimitConfig(60, 500, 10),
            "/api/v1/operational-db/query": RateLimitConfig(30, 200, 5),
            "/api/v1/auth/login": RateLimitConfig(5, 20, 2),
            "/api/v1/admin": RateLimitConfig(20, 100, 5)
        }
    
    async def initialize_redis(self):
        """Initialize Redis connection"""
        try:
            settings = get_settings()
            redis_url = f"redis://:{settings.redis_password}@{settings.redis_host}:{settings.redis_port}/1"
            self.redis_client = await aioredis.from_url(redis_url)
            logger.info("Rate limiter Redis initialized")
        except Exception as e:
            logger.warning(f"Redis initialization failed, using local cache: {e}")
    
    async def check_rate_limit(
        self, 
        identifier: str, 
        endpoint: str, 
        limit_type: RateLimitType = RateLimitType.PER_IP
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check if request is within rate limits"""
        config = self.endpoint_configs.get(endpoint, self.default_config)
        current_time = int(time.time())
        
        # Create cache keys
        minute_key = f"rate_limit:{limit_type.value}:{identifier}:{endpoint}:minute:{current_time // 60}"
        hour_key = f"rate_limit:{limit_type.value}:{identifier}:{endpoint}:hour:{current_time // 3600}"
        burst_key = f"rate_limit:{limit_type.value}:{identifier}:{endpoint}:burst"
        
        try:
            if self.redis_client:
                return await self._check_redis_rate_limit(
                    minute_key, hour_key, burst_key, config
                )
            else:
                return await self._check_local_rate_limit(
                    minute_key, hour_key, burst_key, config
                )
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return True, {}  # Allow request on error
    
    async def _check_redis_rate_limit(
        self, 
        minute_key: str, 
        hour_key: str, 
        burst_key: str, 
        config: RateLimitConfig
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limits using Redis"""
        pipeline = self.redis_client.pipeline()
        
        # Get current counts
        pipeline.get(minute_key)
        pipeline.get(hour_key)
        pipeline.get(burst_key)
        
        results = await pipeline.execute()
        minute_count = int(results[0] or 0)
        hour_count = int(results[1] or 0)
        burst_count = int(results[2] or 0)
        
        # Check limits
        if minute_count >= config.requests_per_minute:
            return False, {
                "error": "Rate limit exceeded",
                "limit_type": "per_minute",
                "limit": config.requests_per_minute,
                "current": minute_count,
                "reset_in": 60 - (int(time.time()) % 60)
            }
        
        if hour_count >= config.requests_per_hour:
            return False, {
                "error": "Rate limit exceeded",
                "limit_type": "per_hour",
                "limit": config.requests_per_hour,
                "current": hour_count,
                "reset_in": 3600 - (int(time.time()) % 3600)
            }
        
        if burst_count >= config.burst_limit:
            return False, {
                "error": "Burst limit exceeded",
                "limit_type": "burst",
                "limit": config.burst_limit,
                "current": burst_count,
                "reset_in": 10
            }
        
        # Increment counters
        pipeline = self.redis_client.pipeline()
        pipeline.incr(minute_key)
        pipeline.expire(minute_key, 60)
        pipeline.incr(hour_key)
        pipeline.expire(hour_key, 3600)
        pipeline.incr(burst_key)
        pipeline.expire(burst_key, 10)
        
        await pipeline.execute()
        
        return True, {
            "minute_count": minute_count + 1,
            "hour_count": hour_count + 1,
            "burst_count": burst_count + 1
        }
    
    async def _check_local_rate_limit(
        self, 
        minute_key: str, 
        hour_key: str, 
        burst_key: str, 
        config: RateLimitConfig
    ) -> Tuple[bool, Dict[str, Any]]:
        """Check rate limits using local cache"""
        current_time = time.time()
        
        # Cleanup old entries
        self._cleanup_local_cache(current_time)
        
        # Get current counts
        minute_count = self.local_cache.get(minute_key, {}).get('count', 0)
        hour_count = self.local_cache.get(hour_key, {}).get('count', 0)
        burst_count = self.local_cache.get(burst_key, {}).get('count', 0)
        
        # Check limits (same logic as Redis version)
        if minute_count >= config.requests_per_minute:
            return False, {"error": "Rate limit exceeded", "limit_type": "per_minute"}
        
        if hour_count >= config.requests_per_hour:
            return False, {"error": "Rate limit exceeded", "limit_type": "per_hour"}
        
        if burst_count >= config.burst_limit:
            return False, {"error": "Burst limit exceeded", "limit_type": "burst"}
        
        # Increment counters
        self.local_cache[minute_key] = {
            'count': minute_count + 1,
            'expires_at': current_time + 60
        }
        self.local_cache[hour_key] = {
            'count': hour_count + 1,
            'expires_at': current_time + 3600
        }
        self.local_cache[burst_key] = {
            'count': burst_count + 1,
            'expires_at': current_time + 10
        }
        
        return True, {}
    
    def _cleanup_local_cache(self, current_time: float):
        """Clean up expired local cache entries"""
        expired_keys = [
            key for key, data in self.local_cache.items()
            if data.get('expires_at', 0) < current_time
        ]
        for key in expired_keys:
            del self.local_cache[key]

class ThreatDetector:
    """Advanced threat detection system"""
    
    def __init__(self):
        self.pattern_matcher = PatternMatcher()
        self.threat_history: Dict[str, List[SecurityThreat]] = defaultdict(list)
        self.blocked_ips: Set[str] = set()
        self.whitelist_ips: Set[str] = set()
        self.suspicious_patterns = deque(maxlen=1000)
        
        # Load IP whitelist (internal networks, known good IPs)
        self.whitelist_ips.update([
            "127.0.0.1", "::1",  # localhost
            "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"  # private networks
        ])
    
    def is_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted"""
        try:
            client_ip = ip_address(ip)
            for whitelist_entry in self.whitelist_ips:
                if "/" in whitelist_entry:  # CIDR notation
                    network = IPv4Network(whitelist_entry, strict=False)
                    if client_ip in network:
                        return True
                else:
                    if str(client_ip) == whitelist_entry:
                        return True
        except (AddressValueError, ValueError):
            pass
        
        return False
    
    async def analyze_request(
        self, 
        request: Request, 
        body: Optional[bytes] = None
    ) -> List[SecurityThreat]:
        """Analyze request for security threats"""
        threats = []
        client_ip = self._get_client_ip(request)
        
        # Skip analysis for whitelisted IPs
        if self.is_whitelisted(client_ip):
            return threats
        
        # Check if IP is already blocked
        if client_ip in self.blocked_ips:
            threats.append(SecurityThreat(
                threat_id=f"blocked_ip_{int(time.time())}",
                threat_type="blocked_ip_access",
                threat_level=ThreatLevel.HIGH,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"message": "Access from blocked IP"},
                blocked=True
            ))
            return threats
        
        # Analyze URL
        url_threats = self._analyze_url(request.url.path, client_ip)
        threats.extend(url_threats)
        
        # Analyze query parameters
        if request.url.query:
            query_threats = self._analyze_query_params(request.url.query, client_ip)
            threats.extend(query_threats)
        
        # Analyze headers
        header_threats = self._analyze_headers(request.headers, client_ip)
        threats.extend(header_threats)
        
        # Analyze request body
        if body:
            body_threats = self._analyze_body(body, client_ip)
            threats.extend(body_threats)
        
        # Analyze request patterns
        pattern_threats = self._analyze_request_patterns(request, client_ip)
        threats.extend(pattern_threats)
        
        # Update threat history
        if threats:
            self.threat_history[client_ip].extend(threats)
            # Keep only recent threats (last 24 hours)
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            self.threat_history[client_ip] = [
                t for t in self.threat_history[client_ip] 
                if t.timestamp > cutoff_time
            ]
        
        return threats
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check for forwarded headers (load balancers, proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _analyze_url(self, path: str, client_ip: str) -> List[SecurityThreat]:
        """Analyze URL path for threats"""
        threats = []
        
        # Check for path traversal
        if "../" in path or "..\\\" in path:
            threats.append(SecurityThreat(
                threat_id=f"path_traversal_{int(time.time())}",
                threat_type="path_traversal",
                threat_level=ThreatLevel.HIGH,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"path": path, "pattern": "directory_traversal"}
            ))
        
        # Check for suspicious file access
        suspicious_extensions = [".env", ".config", ".key", ".log", ".backup"]
        if any(ext in path.lower() for ext in suspicious_extensions):
            threats.append(SecurityThreat(
                threat_id=f"suspicious_file_{int(time.time())}",
                threat_type="suspicious_file_access",
                threat_level=ThreatLevel.MEDIUM,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"path": path, "pattern": "sensitive_file_access"}
            ))
        
        return threats
    
    def _analyze_query_params(self, query: str, client_ip: str) -> List[SecurityThreat]:
        """Analyze query parameters for threats"""
        threats = []
        
        # Check for SQL injection
        if self.pattern_matcher.detect_sql_injection(query):
            threats.append(SecurityThreat(
                threat_id=f"sql_injection_{int(time.time())}",
                threat_type="sql_injection",
                threat_level=ThreatLevel.CRITICAL,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"query": query[:500], "pattern": "sql_injection"}
            ))
        
        # Check for XSS
        if self.pattern_matcher.detect_xss(query):
            threats.append(SecurityThreat(
                threat_id=f"xss_attempt_{int(time.time())}",
                threat_type="xss_attempt",
                threat_level=ThreatLevel.HIGH,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"query": query[:500], "pattern": "xss"}
            ))
        
        # Check for command injection
        if self.pattern_matcher.detect_command_injection(query):
            threats.append(SecurityThreat(
                threat_id=f"command_injection_{int(time.time())}",
                threat_type="command_injection",
                threat_level=ThreatLevel.CRITICAL,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"query": query[:500], "pattern": "command_injection"}
            ))
        
        return threats
    
    def _analyze_headers(self, headers, client_ip: str) -> List[SecurityThreat]:
        """Analyze HTTP headers for threats"""
        threats = []
        
        # Check User-Agent
        user_agent = headers.get("User-Agent", "").lower()
        
        # Detect suspicious tools/scanners
        suspicious_agents = [
            "sqlmap", "nikto", "nmap", "burp", "owasp", "zap",
            "scanner", "exploit", "vulnerability", "penetration"
        ]
        
        if any(agent in user_agent for agent in suspicious_agents):
            threats.append(SecurityThreat(
                threat_id=f"suspicious_agent_{int(time.time())}",
                threat_type="suspicious_user_agent",
                threat_level=ThreatLevel.HIGH,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"user_agent": user_agent, "pattern": "security_tool"}
            ))
        
        # Check for header injection
        for name, value in headers.items():
            if "\r" in value or "\n" in value:
                threats.append(SecurityThreat(
                    threat_id=f"header_injection_{int(time.time())}",
                    threat_type="header_injection",
                    threat_level=ThreatLevel.MEDIUM,
                    source_ip=client_ip,
                    timestamp=datetime.utcnow(),
                    details={"header": name, "value": value[:100]}
                ))
        
        return threats
    
    def _analyze_body(self, body: bytes, client_ip: str) -> List[SecurityThreat]:
        """Analyze request body for threats"""
        threats = []
        
        try:
            body_text = body.decode('utf-8', errors='ignore')
            
            # Check for SQL injection
            if self.pattern_matcher.detect_sql_injection(body_text):
                threats.append(SecurityThreat(
                    threat_id=f"body_sql_injection_{int(time.time())}",
                    threat_type="sql_injection_body",
                    threat_level=ThreatLevel.CRITICAL,
                    source_ip=client_ip,
                    timestamp=datetime.utcnow(),
                    details={"body_excerpt": body_text[:200]}
                ))
            
            # Check for XSS in body
            if self.pattern_matcher.detect_xss(body_text):
                threats.append(SecurityThreat(
                    threat_id=f"body_xss_{int(time.time())}",
                    threat_type="xss_body",
                    threat_level=ThreatLevel.HIGH,
                    source_ip=client_ip,
                    timestamp=datetime.utcnow(),
                    details={"body_excerpt": body_text[:200]}
                ))
            
            # Check for oversized payloads
            if len(body) > 10 * 1024 * 1024:  # 10MB
                threats.append(SecurityThreat(
                    threat_id=f"large_payload_{int(time.time())}",
                    threat_type="large_payload",
                    threat_level=ThreatLevel.MEDIUM,
                    source_ip=client_ip,
                    timestamp=datetime.utcnow(),
                    details={"payload_size": len(body)}
                ))
        
        except Exception as e:
            logger.warning(f"Error analyzing request body: {e}")
        
        return threats
    
    def _analyze_request_patterns(self, request: Request, client_ip: str) -> List[SecurityThreat]:
        """Analyze request patterns for abnormal behavior"""
        threats = []
        
        # Check request frequency from this IP
        recent_requests = [
            t for t in self.threat_history.get(client_ip, [])
            if t.timestamp > datetime.utcnow() - timedelta(minutes=1)
        ]
        
        if len(recent_requests) > 100:  # More than 100 requests per minute
            threats.append(SecurityThreat(
                threat_id=f"high_frequency_{int(time.time())}",
                threat_type="high_frequency_requests",
                threat_level=ThreatLevel.HIGH,
                source_ip=client_ip,
                timestamp=datetime.utcnow(),
                details={"requests_per_minute": len(recent_requests)}
            ))
        
        return threats
    
    def block_ip(self, ip: str, duration_hours: int = 24):
        """Block IP address"""
        self.blocked_ips.add(ip)
        logger.warning(f"Blocked IP {ip} for {duration_hours} hours")
        
        # Schedule unblock (in production, use a proper scheduler)
        asyncio.create_task(self._schedule_unblock(ip, duration_hours * 3600))
    
    async def _schedule_unblock(self, ip: str, delay_seconds: int):
        """Schedule IP unblock"""
        await asyncio.sleep(delay_seconds)
        self.blocked_ips.discard(ip)
        logger.info(f"Unblocked IP {ip}")

class SecurityMiddleware:
    """Main security middleware orchestrator"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.threat_detector = ThreatDetector()
        self.audit_logger = None
        self.client_info: Dict[str, ClientInfo] = {}
        
    async def initialize(self):
        """Initialize security middleware"""
        await self.rate_limiter.initialize_redis()
        self.audit_logger = await get_audit_logger()
        logger.info("Security middleware initialized")
    
    async def __call__(self, request: Request, call_next):
        """Process request through security middleware"""
        start_time = time.time()
        client_ip = self.threat_detector._get_client_ip(request)
        
        try:
            # Read request body for analysis
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                # Restore body for downstream handlers
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
            
            # Threat detection
            threats = await self.threat_detector.analyze_request(request, body)
            
            # Handle critical threats
            critical_threats = [t for t in threats if t.threat_level == ThreatLevel.CRITICAL]
            if critical_threats:
                # Block IP immediately
                self.threat_detector.block_ip(client_ip, 24)
                
                # Log security violation
                if self.audit_logger:
                    await self.audit_logger.log_security_violation(
                        "critical_threat_detected",
                        None,
                        client_ip,
                        {"threats": [asdict(t) for t in critical_threats]}
                    )
                
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"error": "Request blocked due to security violation"}
                )
            
            # Rate limiting
            allowed, limit_info = await self.rate_limiter.check_rate_limit(
                client_ip,
                request.url.path,
                RateLimitType.PER_IP
            )
            
            if not allowed:
                if self.audit_logger:
                    await self.audit_logger.log_security_violation(
                        "rate_limit_exceeded",
                        None,
                        client_ip,
                        limit_info
                    )
                
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content=limit_info,
                    headers={"Retry-After": str(limit_info.get("reset_in", 60))}
                )
            
            # Update client info
            self._update_client_info(client_ip, request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            response = self._add_security_headers(response)
            
            # Log any medium/high threats
            if threats:
                medium_high_threats = [
                    t for t in threats 
                    if t.threat_level in [ThreatLevel.MEDIUM, ThreatLevel.HIGH]
                ]
                if medium_high_threats and self.audit_logger:
                    await self.audit_logger.log_security_violation(
                        "threat_detected",
                        None,
                        client_ip,
                        {"threats": [asdict(t) for t in medium_high_threats]}
                    )
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Security middleware error: {e}")
            # Log error but don't block request
            if self.audit_logger:
                await self.audit_logger.log_security_violation(
                    "middleware_error",
                    None,
                    client_ip,
                    {"error": str(e)}
                )
            
            # Continue with request
            return await call_next(request)
    
    def _update_client_info(self, ip: str, request: Request):
        """Update client information"""
        current_time = datetime.utcnow()
        
        if ip not in self.client_info:
            self.client_info[ip] = ClientInfo(
                ip_address=ip,
                user_agent=request.headers.get("User-Agent", ""),
                first_seen=current_time,
                last_seen=current_time
            )
        else:
            client = self.client_info[ip]
            client.last_seen = current_time
            client.request_count += 1
    
    def _add_security_headers(self, response: Response) -> Response:
        """Add security headers to response"""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": (
                "camera=(), microphone=(), geolocation=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )
        }
        
        for header_name, header_value in security_headers.items():
            response.headers[header_name] = header_value
        
        return response
    
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security statistics"""
        total_threats = sum(
            len(threats) for threats in self.threat_detector.threat_history.values()
        )
        
        blocked_ips = len(self.threat_detector.blocked_ips)
        
        threat_types = defaultdict(int)
        for threats in self.threat_detector.threat_history.values():
            for threat in threats:
                threat_types[threat.threat_type] += 1
        
        return {
            "total_clients": len(self.client_info),
            "blocked_ips": blocked_ips,
            "total_threats_detected": total_threats,
            "threat_types": dict(threat_types),
            "whitelist_ips": len(self.threat_detector.whitelist_ips)
        }

# Global security middleware instance
security_middleware = SecurityMiddleware()

async def get_security_middleware() -> SecurityMiddleware:
    """Get security middleware instance"""
    return security_middleware