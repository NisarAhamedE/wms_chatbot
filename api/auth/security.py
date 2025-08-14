import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import pyotp
import qrcode
from io import BytesIO
import base64

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token scheme
security = HTTPBearer()

class SecurityManager:
    """Handles all security-related operations."""
    
    def __init__(self):
        self.pwd_context = pwd_context
        self.secret_key = SECRET_KEY
        self.algorithm = ALGORITHM
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Verify token type
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token type. Expected {token_type}",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def generate_session_token(self) -> str:
        """Generate a secure session token."""
        return secrets.token_urlsafe(32)
    
    def generate_password_reset_token(self, user_id: int) -> str:
        """Generate a password reset token."""
        data = {
            "user_id": user_id,
            "type": "password_reset",
            "exp": datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        }
        return jwt.encode(data, self.secret_key, algorithm=self.algorithm)
    
    def verify_password_reset_token(self, token: str) -> Optional[int]:
        """Verify a password reset token and return user_id."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get("type") != "password_reset":
                return None
            
            return payload.get("user_id")
            
        except jwt.JWTError:
            return None

class TwoFactorAuth:
    """Handle two-factor authentication operations."""
    
    def __init__(self):
        self.app_name = "WMS Chatbot"
    
    def generate_secret(self) -> str:
        """Generate a new 2FA secret."""
        return pyotp.random_base32()
    
    def generate_qr_code(self, user_email: str, secret: str) -> str:
        """Generate QR code for 2FA setup."""
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email,
            issuer_name=self.app_name
        )
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{qr_code_base64}"
    
    def verify_token(self, secret: str, token: str) -> bool:
        """Verify a 2FA token."""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 1 window of tolerance
    
    def generate_backup_codes(self, count: int = 10) -> list[str]:
        """Generate backup codes for 2FA."""
        return [secrets.token_hex(4).upper() for _ in range(count)]

class RateLimiter:
    """Rate limiting for security."""
    
    def __init__(self):
        self.attempts = {}  # In production, use Redis
    
    def is_rate_limited(self, key: str, max_attempts: int, window_minutes: int) -> bool:
        """Check if a key is rate limited."""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        
        if key not in self.attempts:
            self.attempts[key] = []
        
        # Remove old attempts
        self.attempts[key] = [
            attempt for attempt in self.attempts[key] 
            if attempt > window_start
        ]
        
        return len(self.attempts[key]) >= max_attempts
    
    def record_attempt(self, key: str) -> None:
        """Record an attempt for rate limiting."""
        if key not in self.attempts:
            self.attempts[key] = []
        
        self.attempts[key].append(datetime.utcnow())

# Initialize security components
security_manager = SecurityManager()
two_factor_auth = TwoFactorAuth()
rate_limiter = RateLimiter()

# Dependency functions
async def get_current_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict[str, Any]:
    """Extract and verify the current user's token."""
    token = credentials.credentials
    payload = security_manager.verify_token(token, "access")
    return payload

def validate_password_strength(password: str) -> bool:
    """Validate password meets security requirements."""
    if len(password) < 6:
        return False
    
    # Check for at least one digit, one letter
    has_digit = any(c.isdigit() for c in password)
    has_letter = any(c.isalpha() for c in password)
    
    return has_digit and has_letter

def generate_secure_filename(original_filename: str) -> str:
    """Generate a secure filename to prevent path traversal."""
    # Remove directory paths and dangerous characters
    filename = os.path.basename(original_filename)
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    
    # Add timestamp to avoid conflicts
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    
    return f"{name}_{timestamp}{ext}"

class SecurityAuditLogger:
    """Log security events for auditing."""
    
    def __init__(self):
        self.events = []  # In production, use proper logging system
    
    def log_login_attempt(
        self, 
        username: str, 
        ip_address: str, 
        user_agent: str, 
        success: bool
    ) -> None:
        """Log a login attempt."""
        event = {
            "type": "login_attempt",
            "username": username,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "timestamp": datetime.utcnow()
        }
        self.events.append(event)
    
    def log_password_change(self, user_id: int, ip_address: str) -> None:
        """Log a password change."""
        event = {
            "type": "password_change",
            "user_id": user_id,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow()
        }
        self.events.append(event)
    
    def log_session_created(self, user_id: int, ip_address: str) -> None:
        """Log session creation."""
        event = {
            "type": "session_created",
            "user_id": user_id,
            "ip_address": ip_address,
            "timestamp": datetime.utcnow()
        }
        self.events.append(event)

# Initialize audit logger
audit_logger = SecurityAuditLogger()