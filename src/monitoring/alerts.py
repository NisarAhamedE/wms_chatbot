"""
Advanced monitoring and alerting system for WMS Chatbot
Provides real-time monitoring, alerting, and performance tracking
"""

import asyncio
import json
import logging
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp
import psutil
from sqlalchemy import text
from src.core.config import get_settings
from src.database.connection import get_database_manager

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics to monitor"""
    SYSTEM = "system"
    DATABASE = "database"
    API = "api"
    AGENT = "agent"
    CUSTOM = "custom"

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric_name: str
    threshold: float
    comparison: str  # gt, lt, eq, gte, lte
    level: AlertLevel
    enabled: bool = True
    cooldown_minutes: int = 15
    description: str = ""

@dataclass
class Alert:
    """Alert instance"""
    id: str
    rule_name: str
    level: AlertLevel
    message: str
    value: float
    threshold: float
    timestamp: datetime
    resolved: bool = False
    resolved_at: Optional[datetime] = None

@dataclass
class Metric:
    """Metric data point"""
    name: str
    value: float
    type: MetricType
    timestamp: datetime
    labels: Dict[str, str] = None

class AlertManager:
    """Centralized alert management system"""
    
    def __init__(self):
        self.settings = get_settings()
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.last_alert_times: Dict[str, datetime] = {}
        self.notification_handlers: List[Callable] = []
        
    def add_rule(self, rule: AlertRule):
        """Add alert rule"""
        self.rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_name: str):
        """Remove alert rule"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"Removed alert rule: {rule_name}")
    
    def add_notification_handler(self, handler: Callable):
        """Add notification handler"""
        self.notification_handlers.append(handler)
    
    async def check_metric(self, metric: Metric) -> List[Alert]:
        """Check metric against alert rules"""
        triggered_alerts = []
        
        for rule_name, rule in self.rules.items():
            if not rule.enabled or rule.metric_name != metric.name:
                continue
                
            # Check cooldown
            last_alert = self.last_alert_times.get(rule_name)
            if last_alert:
                cooldown_end = last_alert + timedelta(minutes=rule.cooldown_minutes)
                if datetime.utcnow() < cooldown_end:
                    continue
            
            # Evaluate threshold
            triggered = self._evaluate_threshold(
                metric.value, rule.threshold, rule.comparison
            )
            
            if triggered:
                alert = Alert(
                    id=f"{rule_name}_{int(time.time())}",
                    rule_name=rule_name,
                    level=rule.level,
                    message=f"{rule.description or rule.name}: {metric.value} {rule.comparison} {rule.threshold}",
                    value=metric.value,
                    threshold=rule.threshold,
                    timestamp=datetime.utcnow()
                )
                
                triggered_alerts.append(alert)
                self.active_alerts[alert.id] = alert
                self.alert_history.append(alert)
                self.last_alert_times[rule_name] = datetime.utcnow()
                
                # Send notifications
                await self._send_notifications(alert)
                
                logger.warning(f"Alert triggered: {alert.message}")
        
        return triggered_alerts
    
    def _evaluate_threshold(self, value: float, threshold: float, comparison: str) -> bool:
        """Evaluate threshold condition"""
        if comparison == "gt":
            return value > threshold
        elif comparison == "lt":
            return value < threshold
        elif comparison == "gte":
            return value >= threshold
        elif comparison == "lte":
            return value <= threshold
        elif comparison == "eq":
            return value == threshold
        return False
    
    async def _send_notifications(self, alert: Alert):
        """Send alert notifications"""
        for handler in self.notification_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
    
    async def resolve_alert(self, alert_id: str):
        """Resolve active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.utcnow()
            del self.active_alerts[alert_id]
            logger.info(f"Alert resolved: {alert.message}")

class SystemMonitor:
    """System resource monitoring"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.setup_default_rules()
    
    def setup_default_rules(self):
        """Setup default system monitoring rules"""
        rules = [
            AlertRule(
                name="high_cpu_usage",
                metric_name="system.cpu.percent",
                threshold=80.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                description="High CPU usage detected"
            ),
            AlertRule(
                name="critical_cpu_usage",
                metric_name="system.cpu.percent",
                threshold=95.0,
                comparison="gt",
                level=AlertLevel.CRITICAL,
                description="Critical CPU usage detected"
            ),
            AlertRule(
                name="high_memory_usage",
                metric_name="system.memory.percent",
                threshold=85.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                description="High memory usage detected"
            ),
            AlertRule(
                name="critical_memory_usage",
                metric_name="system.memory.percent",
                threshold=95.0,
                comparison="gt",
                level=AlertLevel.CRITICAL,
                description="Critical memory usage detected"
            ),
            AlertRule(
                name="low_disk_space",
                metric_name="system.disk.percent",
                threshold=85.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                description="Low disk space detected"
            ),
            AlertRule(
                name="critical_disk_space",
                metric_name="system.disk.percent",
                threshold=95.0,
                comparison="gt",
                level=AlertLevel.CRITICAL,
                description="Critical disk space detected"
            )
        ]
        
        for rule in rules:
            self.alert_manager.add_rule(rule)
    
    async def collect_metrics(self) -> List[Metric]:
        """Collect system metrics"""
        timestamp = datetime.utcnow()
        metrics = []
        
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            metrics.append(Metric(
                name="system.cpu.percent",
                value=cpu_percent,
                type=MetricType.SYSTEM,
                timestamp=timestamp
            ))
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics.append(Metric(
                name="system.memory.percent",
                value=memory.percent,
                type=MetricType.SYSTEM,
                timestamp=timestamp
            ))
            
            metrics.append(Metric(
                name="system.memory.available_gb",
                value=memory.available / (1024**3),
                type=MetricType.SYSTEM,
                timestamp=timestamp
            ))
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            metrics.append(Metric(
                name="system.disk.percent",
                value=(disk.used / disk.total) * 100,
                type=MetricType.SYSTEM,
                timestamp=timestamp
            ))
            
            metrics.append(Metric(
                name="system.disk.free_gb",
                value=disk.free / (1024**3),
                type=MetricType.SYSTEM,
                timestamp=timestamp
            ))
            
            # Network metrics
            network = psutil.net_io_counters()
            metrics.append(Metric(
                name="system.network.bytes_sent",
                value=network.bytes_sent,
                type=MetricType.SYSTEM,
                timestamp=timestamp
            ))
            
            metrics.append(Metric(
                name="system.network.bytes_recv",
                value=network.bytes_recv,
                type=MetricType.SYSTEM,
                timestamp=timestamp
            ))
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
        
        return metrics

class DatabaseMonitor:
    """Database performance monitoring"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.db_manager = get_database_manager()
        self.setup_default_rules()
    
    def setup_default_rules(self):
        """Setup default database monitoring rules"""
        rules = [
            AlertRule(
                name="high_db_connections",
                metric_name="database.active_connections",
                threshold=80.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                description="High database connection count"
            ),
            AlertRule(
                name="slow_query_detected",
                metric_name="database.slow_query_count",
                threshold=5.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                description="Multiple slow queries detected"
            ),
            AlertRule(
                name="db_connection_failed",
                metric_name="database.connection_failures",
                threshold=1.0,
                comparison="gte",
                level=AlertLevel.ERROR,
                description="Database connection failures detected"
            )
        ]
        
        for rule in rules:
            self.alert_manager.add_rule(rule)
    
    async def collect_metrics(self) -> List[Metric]:
        """Collect database metrics"""
        timestamp = datetime.utcnow()
        metrics = []
        
        try:
            async with self.db_manager.get_session() as session:
                # Active connections
                result = await session.execute(text(
                    "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
                ))
                active_connections = result.scalar()
                
                metrics.append(Metric(
                    name="database.active_connections",
                    value=float(active_connections),
                    type=MetricType.DATABASE,
                    timestamp=timestamp
                ))
                
                # Database size
                result = await session.execute(text(
                    "SELECT pg_size_pretty(pg_database_size(current_database()))"
                ))
                db_size = result.scalar()
                
                # Slow queries (queries running > 5 seconds)
                result = await session.execute(text("""
                    SELECT count(*) FROM pg_stat_activity 
                    WHERE state = 'active' 
                    AND now() - query_start > interval '5 seconds'
                    AND query NOT LIKE '%pg_stat_activity%'
                """))
                slow_queries = result.scalar()
                
                metrics.append(Metric(
                    name="database.slow_query_count",
                    value=float(slow_queries),
                    type=MetricType.DATABASE,
                    timestamp=timestamp
                ))
                
                # Lock statistics
                result = await session.execute(text(
                    "SELECT count(*) FROM pg_locks WHERE NOT granted"
                ))
                blocked_queries = result.scalar()
                
                metrics.append(Metric(
                    name="database.blocked_queries",
                    value=float(blocked_queries),
                    type=MetricType.DATABASE,
                    timestamp=timestamp
                ))
                
        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")
            metrics.append(Metric(
                name="database.connection_failures",
                value=1.0,
                type=MetricType.DATABASE,
                timestamp=timestamp
            ))
        
        return metrics

class APIMonitor:
    """API performance monitoring"""
    
    def __init__(self, alert_manager: AlertManager):
        self.alert_manager = alert_manager
        self.request_counts = {}
        self.response_times = []
        self.error_counts = {}
        self.setup_default_rules()
    
    def setup_default_rules(self):
        """Setup default API monitoring rules"""
        rules = [
            AlertRule(
                name="high_api_response_time",
                metric_name="api.avg_response_time_ms",
                threshold=5000.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                description="High API response time detected"
            ),
            AlertRule(
                name="high_error_rate",
                metric_name="api.error_rate_percent",
                threshold=5.0,
                comparison="gt",
                level=AlertLevel.ERROR,
                description="High API error rate detected"
            ),
            AlertRule(
                name="api_overload",
                metric_name="api.requests_per_minute",
                threshold=1000.0,
                comparison="gt",
                level=AlertLevel.WARNING,
                description="High API request rate detected"
            )
        ]
        
        for rule in rules:
            self.alert_manager.add_rule(rule)
    
    def record_request(self, endpoint: str, method: str, status_code: int, response_time: float):
        """Record API request metrics"""
        key = f"{method}:{endpoint}"
        
        # Count requests
        if key not in self.request_counts:
            self.request_counts[key] = {"total": 0, "errors": 0, "timestamp": time.time()}
        
        self.request_counts[key]["total"] += 1
        
        # Count errors (4xx and 5xx)
        if status_code >= 400:
            self.request_counts[key]["errors"] += 1
        
        # Record response time
        self.response_times.append({
            "endpoint": key,
            "response_time": response_time,
            "timestamp": time.time()
        })
        
        # Clean old data (keep last hour)
        current_time = time.time()
        self.response_times = [
            rt for rt in self.response_times 
            if current_time - rt["timestamp"] < 3600
        ]
    
    async def collect_metrics(self) -> List[Metric]:
        """Collect API metrics"""
        timestamp = datetime.utcnow()
        metrics = []
        current_time = time.time()
        
        try:
            # Average response time
            recent_times = [
                rt["response_time"] for rt in self.response_times
                if current_time - rt["timestamp"] < 300  # Last 5 minutes
            ]
            
            if recent_times:
                avg_response_time = sum(recent_times) / len(recent_times)
                metrics.append(Metric(
                    name="api.avg_response_time_ms",
                    value=avg_response_time,
                    type=MetricType.API,
                    timestamp=timestamp
                ))
            
            # Request rate and error rate
            total_requests = 0
            total_errors = 0
            
            for key, data in self.request_counts.items():
                if current_time - data["timestamp"] < 60:  # Last minute
                    total_requests += data["total"]
                    total_errors += data["errors"]
            
            metrics.append(Metric(
                name="api.requests_per_minute",
                value=float(total_requests),
                type=MetricType.API,
                timestamp=timestamp
            ))
            
            if total_requests > 0:
                error_rate = (total_errors / total_requests) * 100
                metrics.append(Metric(
                    name="api.error_rate_percent",
                    value=error_rate,
                    type=MetricType.API,
                    timestamp=timestamp
                ))
            
        except Exception as e:
            logger.error(f"Failed to collect API metrics: {e}")
        
        return metrics

class NotificationHandlers:
    """Notification handlers for different channels"""
    
    @staticmethod
    async def email_handler(alert: Alert, email_config: Dict[str, Any]):
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = email_config['from_email']
            msg['To'] = email_config['to_email']
            msg['Subject'] = f"WMS Chatbot Alert - {alert.level.value.upper()}: {alert.rule_name}"
            
            body = f"""
Alert Details:
- Rule: {alert.rule_name}
- Level: {alert.level.value.upper()}
- Message: {alert.message}
- Value: {alert.value}
- Threshold: {alert.threshold}
- Time: {alert.timestamp}

System: WMS Chatbot
Environment: {get_settings().env}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(email_config['smtp_host'], email_config['smtp_port'])
            server.starttls()
            server.login(email_config['username'], email_config['password'])
            text = msg.as_string()
            server.sendmail(email_config['from_email'], email_config['to_email'], text)
            server.quit()
            
            logger.info(f"Email alert sent for: {alert.rule_name}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    @staticmethod
    async def webhook_handler(alert: Alert, webhook_url: str):
        """Send webhook notification"""
        try:
            payload = {
                "alert_id": alert.id,
                "rule_name": alert.rule_name,
                "level": alert.level.value,
                "message": alert.message,
                "value": alert.value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp.isoformat(),
                "system": "wms-chatbot",
                "environment": get_settings().env
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Webhook alert sent for: {alert.rule_name}")
                    else:
                        logger.error(f"Webhook alert failed with status: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    @staticmethod
    async def slack_handler(alert: Alert, slack_webhook_url: str):
        """Send Slack notification"""
        try:
            color_map = {
                AlertLevel.INFO: "good",
                AlertLevel.WARNING: "warning",
                AlertLevel.ERROR: "danger",
                AlertLevel.CRITICAL: "danger"
            }
            
            payload = {
                "text": f"WMS Chatbot Alert: {alert.rule_name}",
                "attachments": [
                    {
                        "color": color_map.get(alert.level, "warning"),
                        "fields": [
                            {
                                "title": "Level",
                                "value": alert.level.value.upper(),
                                "short": True
                            },
                            {
                                "title": "Message",
                                "value": alert.message,
                                "short": False
                            },
                            {
                                "title": "Value",
                                "value": str(alert.value),
                                "short": True
                            },
                            {
                                "title": "Threshold",
                                "value": str(alert.threshold),
                                "short": True
                            },
                            {
                                "title": "Time",
                                "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                                "short": True
                            }
                        ],
                        "footer": "WMS Chatbot Monitoring",
                        "ts": int(alert.timestamp.timestamp())
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    slack_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        logger.info(f"Slack alert sent for: {alert.rule_name}")
                    else:
                        logger.error(f"Slack alert failed with status: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

class MonitoringService:
    """Main monitoring service orchestrator"""
    
    def __init__(self):
        self.alert_manager = AlertManager()
        self.system_monitor = SystemMonitor(self.alert_manager)
        self.database_monitor = DatabaseMonitor(self.alert_manager)
        self.api_monitor = APIMonitor(self.alert_manager)
        self.running = False
        self.monitoring_task = None
        
    async def start(self):
        """Start monitoring service"""
        if self.running:
            return
            
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Monitoring service started")
    
    async def stop(self):
        """Stop monitoring service"""
        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Monitoring service stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Collect all metrics
                all_metrics = []
                
                # System metrics
                system_metrics = await self.system_monitor.collect_metrics()
                all_metrics.extend(system_metrics)
                
                # Database metrics
                db_metrics = await self.database_monitor.collect_metrics()
                all_metrics.extend(db_metrics)
                
                # API metrics
                api_metrics = await self.api_monitor.collect_metrics()
                all_metrics.extend(api_metrics)
                
                # Check each metric against alert rules
                for metric in all_metrics:
                    await self.alert_manager.check_metric(metric)
                
                # Log metrics summary
                logger.debug(f"Collected {len(all_metrics)} metrics")
                
                # Wait before next collection
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)  # Wait less time on error
    
    def get_api_monitor(self) -> APIMonitor:
        """Get API monitor instance for middleware"""
        return self.api_monitor
    
    def get_alert_manager(self) -> AlertManager:
        """Get alert manager instance"""
        return self.alert_manager

# Global monitoring service instance
monitoring_service = MonitoringService()

async def get_monitoring_service() -> MonitoringService:
    """Get monitoring service instance"""
    return monitoring_service