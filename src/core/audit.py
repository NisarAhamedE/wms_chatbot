"""
Comprehensive audit and logging system for WMS Chatbot
Provides detailed logging, user activity tracking, and compliance features
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import traceback
from contextlib import contextmanager
from functools import wraps

from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID

from src.core.config import get_settings
from src.database.connection import get_database_manager

logger = logging.getLogger(__name__)

class AuditEventType(Enum):
    """Types of audit events"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    QUERY_EXECUTED = "query_executed"
    DATA_ACCESSED = "data_accessed"
    DATA_MODIFIED = "data_modified"
    AGENT_INVOKED = "agent_invoked"
    ERROR_OCCURRED = "error_occurred"
    SECURITY_VIOLATION = "security_violation"
    CONFIGURATION_CHANGED = "configuration_changed"
    SYSTEM_EVENT = "system_event"

class LogLevel(Enum):
    """Log severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ComplianceStandard(Enum):
    """Compliance standards"""
    SOX = "sox"  # Sarbanes-Oxley
    GDPR = "gdpr"  # General Data Protection Regulation
    HIPAA = "hipaa"  # Health Insurance Portability and Accountability Act
    PCI_DSS = "pci_dss"  # Payment Card Industry Data Security Standard

@dataclass
class AuditEvent:
    """Audit event structure"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime
    user_id: Optional[str]
    user_role: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: Optional[str]
    action: str
    details: Dict[str, Any]
    success: bool
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None
    compliance_flags: List[ComplianceStandard] = None

@dataclass
class UserSession:
    """User session tracking"""
    session_id: str
    user_id: str
    user_role: str
    login_time: datetime
    last_activity: datetime
    ip_address: str
    user_agent: str
    actions_count: int = 0
    queries_count: int = 0
    is_active: bool = True

Base = declarative_base()

class AuditLog(Base):
    """Database model for audit logs"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    user_id = Column(String(255))
    user_role = Column(String(100))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    resource = Column(String(500))
    action = Column(String(255), nullable=False)
    details = Column(JSON)
    success = Column(Boolean, nullable=False)
    duration_ms = Column(Integer)
    error_message = Column(Text)
    compliance_flags = Column(JSON)

class UserSessionLog(Base):
    """Database model for user sessions"""
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(String(255), nullable=False)
    user_role = Column(String(100), nullable=False)
    login_time = Column(DateTime, nullable=False)
    logout_time = Column(DateTime)
    last_activity = Column(DateTime, nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    actions_count = Column(Integer, default=0)
    queries_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

class StructuredLogger:
    """Enhanced structured logging with correlation IDs"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.correlation_id: Optional[str] = None
        
    @contextmanager
    def correlation_context(self, correlation_id: str):
        """Context manager for correlation ID"""
        old_correlation_id = self.correlation_id
        self.correlation_id = correlation_id
        try:
            yield
        finally:
            self.correlation_id = old_correlation_id
    
    def _format_message(self, message: str, **kwargs) -> str:
        """Format log message with correlation ID and context"""
        log_data = {
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if self.correlation_id:
            log_data["correlation_id"] = self.correlation_id
        
        if kwargs:
            log_data["context"] = kwargs
        
        return json.dumps(log_data, default=str)
    
    def debug(self, message: str, **kwargs):
        """Debug log with structured data"""
        self.logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs):
        """Info log with structured data"""
        self.logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs):
        """Warning log with structured data"""
        self.logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, **kwargs):
        """Error log with structured data"""
        if 'exception' not in kwargs:
            kwargs['exception'] = traceback.format_exc()
        self.logger.error(self._format_message(message, **kwargs))
    
    def critical(self, message: str, **kwargs):
        """Critical log with structured data"""
        if 'exception' not in kwargs:
            kwargs['exception'] = traceback.format_exc()
        self.logger.critical(self._format_message(message, **kwargs))

class AuditLogger:
    """Centralized audit logging system"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.active_sessions: Dict[str, UserSession] = {}
        self.audit_queue: List[AuditEvent] = []
        self.batch_size = 100
        self.flush_interval = 30  # seconds
        self.structured_logger = StructuredLogger(__name__)
        
    async def initialize(self):
        """Initialize audit system"""
        try:
            # Ensure audit tables exist
            async with self.db_manager.get_session() as session:
                await session.run_sync(Base.metadata.create_all)
            
            # Start background tasks
            asyncio.create_task(self._audit_flush_worker())
            asyncio.create_task(self._session_cleanup_worker())
            
            self.structured_logger.info("Audit system initialized")
            
        except Exception as e:
            self.structured_logger.error("Failed to initialize audit system", error=str(e))
            raise
    
    async def log_event(self, event: AuditEvent):
        """Log audit event"""
        try:
            # Add to queue for batch processing
            self.audit_queue.append(event)
            
            # Also log to structured logger
            self.structured_logger.info(
                f"Audit event: {event.action}",
                event_type=event.event_type.value,
                user_id=event.user_id,
                resource=event.resource,
                success=event.success,
                details=event.details
            )
            
            # Check for critical events that need immediate processing
            if event.event_type in [
                AuditEventType.SECURITY_VIOLATION,
                AuditEventType.ERROR_OCCURRED
            ]:
                await self._flush_audit_queue()
                
        except Exception as e:
            self.structured_logger.error("Failed to log audit event", error=str(e))
    
    async def create_session(
        self, 
        user_id: str, 
        user_role: str, 
        ip_address: str, 
        user_agent: str
    ) -> str:
        """Create new user session"""
        session_id = str(uuid.uuid4())
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
            login_time=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.active_sessions[session_id] = session
        
        # Log login event
        await self.log_event(AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.USER_LOGIN,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_role=user_role,
            ip_address=ip_address,
            user_agent=user_agent,
            resource="auth",
            action="login",
            details={"session_id": session_id},
            success=True
        ))
        
        # Store in database
        await self._store_session(session)
        
        return session_id
    
    async def end_session(self, session_id: str):
        """End user session"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.is_active = False
            
            # Log logout event
            await self.log_event(AuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=AuditEventType.USER_LOGOUT,
                timestamp=datetime.utcnow(),
                user_id=session.user_id,
                user_role=session.user_role,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                resource="auth",
                action="logout",
                details={
                    "session_id": session_id,
                    "session_duration": (datetime.utcnow() - session.login_time).total_seconds()
                },
                success=True
            ))
            
            # Update database
            await self._update_session(session)
            
            del self.active_sessions[session_id]
    
    async def update_session_activity(self, session_id: str):
        """Update session last activity"""
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.last_activity = datetime.utcnow()
            session.actions_count += 1
    
    async def log_query_execution(
        self,
        session_id: str,
        query: str,
        params: Dict[str, Any],
        execution_time_ms: float,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Log database query execution"""
        session = self.active_sessions.get(session_id)
        if session:
            session.queries_count += 1
            await self.update_session_activity(session_id)
            
            await self.log_event(AuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=AuditEventType.QUERY_EXECUTED,
                timestamp=datetime.utcnow(),
                user_id=session.user_id,
                user_role=session.user_role,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                resource="database",
                action="query",
                details={
                    "query": query[:500],  # Truncate long queries
                    "params_count": len(params) if params else 0,
                    "has_where_clause": "where" in query.lower(),
                    "has_limit_clause": "limit" in query.lower()
                },
                success=success,
                duration_ms=execution_time_ms,
                error_message=error_message,
                compliance_flags=[ComplianceStandard.SOX] if not success else None
            ))
    
    async def log_agent_invocation(
        self,
        session_id: str,
        agent_type: str,
        agent_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        execution_time_ms: float,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Log agent invocation"""
        session = self.active_sessions.get(session_id)
        if session:
            await self.update_session_activity(session_id)
            
            await self.log_event(AuditEvent(
                event_id=str(uuid.uuid4()),
                event_type=AuditEventType.AGENT_INVOKED,
                timestamp=datetime.utcnow(),
                user_id=session.user_id,
                user_role=session.user_role,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                resource=f"agent/{agent_type}",
                action="invoke",
                details={
                    "agent_name": agent_name,
                    "input_size": len(str(input_data)),
                    "output_size": len(str(output_data)) if success else 0,
                    "contains_pii": self._check_for_pii(input_data)
                },
                success=success,
                duration_ms=execution_time_ms,
                error_message=error_message,
                compliance_flags=[ComplianceStandard.GDPR] if self._check_for_pii(input_data) else None
            ))
    
    async def log_security_violation(
        self,
        event_type: str,
        user_id: Optional[str],
        ip_address: str,
        details: Dict[str, Any]
    ):
        """Log security violation"""
        await self.log_event(AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=AuditEventType.SECURITY_VIOLATION,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            user_role=None,
            ip_address=ip_address,
            user_agent=None,
            resource="security",
            action=event_type,
            details=details,
            success=False,
            compliance_flags=[ComplianceStandard.SOX, ComplianceStandard.PCI_DSS]
        ))
    
    def _check_for_pii(self, data: Dict[str, Any]) -> bool:
        """Check for personally identifiable information"""
        pii_patterns = [
            "email", "phone", "ssn", "credit_card", "passport",
            "driver_license", "address", "name", "birthday"
        ]
        
        data_str = json.dumps(data, default=str).lower()
        return any(pattern in data_str for pattern in pii_patterns)
    
    async def _store_session(self, session: UserSession):
        """Store session in database"""
        try:
            async with self.db_manager.get_session() as db_session:
                session_log = UserSessionLog(
                    session_id=session.session_id,
                    user_id=session.user_id,
                    user_role=session.user_role,
                    login_time=session.login_time,
                    last_activity=session.last_activity,
                    ip_address=session.ip_address,
                    user_agent=session.user_agent,
                    actions_count=session.actions_count,
                    queries_count=session.queries_count,
                    is_active=session.is_active
                )
                db_session.add(session_log)
                await db_session.commit()
                
        except Exception as e:
            self.structured_logger.error("Failed to store session", error=str(e))
    
    async def _update_session(self, session: UserSession):
        """Update session in database"""
        try:
            async with self.db_manager.get_session() as db_session:
                result = await db_session.execute(
                    "UPDATE user_sessions SET "
                    "logout_time = :logout_time, "
                    "last_activity = :last_activity, "
                    "actions_count = :actions_count, "
                    "queries_count = :queries_count, "
                    "is_active = :is_active "
                    "WHERE session_id = :session_id",
                    {
                        "logout_time": datetime.utcnow() if not session.is_active else None,
                        "last_activity": session.last_activity,
                        "actions_count": session.actions_count,
                        "queries_count": session.queries_count,
                        "is_active": session.is_active,
                        "session_id": session.session_id
                    }
                )
                await db_session.commit()
                
        except Exception as e:
            self.structured_logger.error("Failed to update session", error=str(e))
    
    async def _flush_audit_queue(self):
        """Flush audit events to database"""
        if not self.audit_queue:
            return
        
        try:
            async with self.db_manager.get_session() as session:
                for event in self.audit_queue:
                    audit_log = AuditLog(
                        event_id=event.event_id,
                        event_type=event.event_type.value,
                        timestamp=event.timestamp,
                        user_id=event.user_id,
                        user_role=event.user_role,
                        ip_address=event.ip_address,
                        user_agent=event.user_agent,
                        resource=event.resource,
                        action=event.action,
                        details=event.details,
                        success=event.success,
                        duration_ms=int(event.duration_ms) if event.duration_ms else None,
                        error_message=event.error_message,
                        compliance_flags=[flag.value for flag in (event.compliance_flags or [])]
                    )
                    session.add(audit_log)
                
                await session.commit()
                
            self.structured_logger.debug(f"Flushed {len(self.audit_queue)} audit events")
            self.audit_queue.clear()
            
        except Exception as e:
            self.structured_logger.error("Failed to flush audit queue", error=str(e))
    
    async def _audit_flush_worker(self):
        """Background worker to flush audit events"""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                if len(self.audit_queue) >= self.batch_size:
                    await self._flush_audit_queue()
            except Exception as e:
                self.structured_logger.error("Error in audit flush worker", error=str(e))
    
    async def _session_cleanup_worker(self):
        """Background worker to cleanup inactive sessions"""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                current_time = datetime.utcnow()
                inactive_sessions = []
                
                for session_id, session in self.active_sessions.items():
                    # Mark sessions inactive after 1 hour of inactivity
                    if (current_time - session.last_activity).total_seconds() > 3600:
                        inactive_sessions.append(session_id)
                
                for session_id in inactive_sessions:
                    await self.end_session(session_id)
                
                if inactive_sessions:
                    self.structured_logger.info(
                        f"Cleaned up {len(inactive_sessions)} inactive sessions"
                    )
                    
            except Exception as e:
                self.structured_logger.error("Error in session cleanup worker", error=str(e))
    
    async def get_audit_report(
        self, 
        start_date: datetime, 
        end_date: datetime,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None
    ) -> Dict[str, Any]:
        """Generate audit report"""
        try:
            async with self.db_manager.get_session() as session:
                query = "SELECT * FROM audit_logs WHERE timestamp BETWEEN :start_date AND :end_date"
                params = {"start_date": start_date, "end_date": end_date}
                
                if user_id:
                    query += " AND user_id = :user_id"
                    params["user_id"] = user_id
                
                if event_type:
                    query += " AND event_type = :event_type"
                    params["event_type"] = event_type.value
                
                result = await session.execute(query, params)
                events = result.fetchall()
                
                return {
                    "report_period": {
                        "start": start_date.isoformat(),
                        "end": end_date.isoformat()
                    },
                    "total_events": len(events),
                    "events": [dict(event) for event in events],
                    "summary": self._generate_audit_summary(events)
                }
                
        except Exception as e:
            self.structured_logger.error("Failed to generate audit report", error=str(e))
            raise

    def _generate_audit_summary(self, events: List[Any]) -> Dict[str, Any]:
        """Generate summary statistics from audit events"""
        if not events:
            return {}
        
        event_types = {}
        users = set()
        success_count = 0
        error_count = 0
        
        for event in events:
            event_type = event.event_type
            event_types[event_type] = event_types.get(event_type, 0) + 1
            
            if event.user_id:
                users.add(event.user_id)
            
            if event.success:
                success_count += 1
            else:
                error_count += 1
        
        return {
            "unique_users": len(users),
            "event_types": event_types,
            "success_rate": success_count / len(events) if events else 0,
            "error_count": error_count,
            "most_common_event": max(event_types.items(), key=lambda x: x[1])[0] if event_types else None
        }

def audit_log(event_type: AuditEventType, resource: str, action: str):
    """Decorator for automatic audit logging"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            success = True
            error_message = None
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                error_message = str(e)
                raise
            finally:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Extract session info if available
                session_id = kwargs.get('session_id') or getattr(args[0], 'session_id', None)
                
                if session_id and hasattr(audit_logger, 'active_sessions'):
                    session = audit_logger.active_sessions.get(session_id)
                    if session:
                        event = AuditEvent(
                            event_id=str(uuid.uuid4()),
                            event_type=event_type,
                            timestamp=start_time,
                            user_id=session.user_id,
                            user_role=session.user_role,
                            ip_address=session.ip_address,
                            user_agent=session.user_agent,
                            resource=resource,
                            action=action,
                            details={"function": func.__name__},
                            success=success,
                            duration_ms=duration_ms,
                            error_message=error_message
                        )
                        
                        await audit_logger.log_event(event)
        
        return wrapper
    return decorator

# Global audit logger instance
audit_logger = AuditLogger()

async def get_audit_logger() -> AuditLogger:
    """Get audit logger instance"""
    return audit_logger

def get_structured_logger(name: str) -> StructuredLogger:
    """Get structured logger instance"""
    return StructuredLogger(name)