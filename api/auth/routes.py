from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..database import get_db
from .models import (
    User, UserSession, LoginRequest, LoginResponse, UserCreate, 
    UserResponse, UserUpdate, RefreshTokenRequest, PasswordResetRequest,
    PasswordResetConfirm, ChangePasswordRequest, SessionInfo, TwoFactorSetup,
    TwoFactorVerify, UserStats
)
from .security import (
    security_manager, two_factor_auth, rate_limiter, audit_logger,
    get_current_user_token, validate_password_strength, MAX_LOGIN_ATTEMPTS
)

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new user."""
    # Validate passwords match
    if user_data.password != user_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    
    # Validate password strength
    if not validate_password_strength(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters with letters and numbers"
        )
    
    # Check rate limiting
    client_ip = request.client.host
    if rate_limiter.is_rate_limited(f"register:{client_ip}", 5, 60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later."
        )
    
    # Check if user already exists
    existing_user = db.query(User).filter(
        or_(User.username == user_data.username, User.email == user_data.email)
    ).first()
    
    if existing_user:
        rate_limiter.record_attempt(f"register:{client_ip}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Create new user
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        role=user_data.role
    )
    db_user.set_password(user_data.password)
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    audit_logger.log_login_attempt(
        username=user_data.username,
        ip_address=client_ip,
        user_agent=request.headers.get("user-agent", ""),
        success=True
    )
    
    return UserResponse.from_orm(db_user)

@router.post("/login", response_model=LoginResponse)
async def login_user(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate user and return tokens."""
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "")
    
    # Check rate limiting
    if rate_limiter.is_rate_limited(f"login:{client_ip}", MAX_LOGIN_ATTEMPTS, 15):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later."
        )
    
    # Find user
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user or not user.verify_password(login_data.password):
        rate_limiter.record_attempt(f"login:{client_ip}")
        audit_logger.log_login_attempt(
            username=login_data.username,
            ip_address=client_ip,
            user_agent=user_agent,
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled"
        )
    
    # Check if account is locked
    if user.is_locked():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is temporarily locked due to multiple failed attempts"
        )
    
    # Reset login attempts on successful login
    user.login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    
    # Create session
    session_token = security_manager.generate_session_token()
    access_token_expires = timedelta(minutes=30)
    refresh_token_expires = timedelta(days=7 if login_data.remember_me else 1)
    
    # Create tokens
    token_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "session_id": session_token
    }
    
    access_token = security_manager.create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    refresh_token = security_manager.create_refresh_token(
        data=token_data,
        expires_delta=refresh_token_expires
    )
    
    # Store session in database
    db_session = UserSession(
        user_id=user.id,
        session_token=session_token,
        refresh_token=refresh_token,
        user_agent=user_agent,
        ip_address=client_ip,
        expires_at=datetime.utcnow() + refresh_token_expires
    )
    
    db.add(db_session)
    db.commit()
    
    audit_logger.log_login_attempt(
        username=login_data.username,
        ip_address=client_ip,
        user_agent=user_agent,
        success=True
    )
    
    audit_logger.log_session_created(
        user_id=user.id,
        ip_address=client_ip
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=int(access_token_expires.total_seconds()),
        user=UserResponse.from_orm(user)
    )

@router.post("/logout")
async def logout_user(
    request: Request,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Logout user and invalidate session."""
    session_id = token_data.get("session_id")
    
    if session_id:
        # Invalidate session
        session = db.query(UserSession).filter(
            UserSession.session_token == session_id
        ).first()
        
        if session:
            session.is_active = False
            db.commit()
    
    return {"message": "Successfully logged out"}

@router.post("/refresh", response_model=dict)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token."""
    try:
        # Verify refresh token
        payload = security_manager.verify_token(refresh_data.refresh_token, "refresh")
        
        # Check if session is still active
        session = db.query(UserSession).filter(
            and_(
                UserSession.refresh_token == refresh_data.refresh_token,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        # Get user
        user = db.query(User).filter(User.id == payload["user_id"]).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        token_data = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role,
            "session_id": payload["session_id"]
        }
        
        access_token = security_manager.create_access_token(data=token_data)
        
        # Update session last active
        session.last_active = datetime.utcnow()
        db.commit()
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 1800  # 30 minutes
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get current user information."""
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse.from_orm(user)

@router.put("/profile", response_model=UserResponse)
async def update_profile(
    user_update: UserUpdate,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Update user profile."""
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    
    if user_update.email is not None:
        # Check if email is already taken
        existing_user = db.query(User).filter(
            and_(User.email == user_update.email, User.id != user.id)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        
        user.email = user_update.email
    
    if user_update.preferences is not None:
        user.preferences = user_update.preferences.dict()
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return UserResponse.from_orm(user)

@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    request: Request,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Change user password."""
    # Validate passwords match
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New passwords do not match"
        )
    
    # Validate password strength
    if not validate_password_strength(password_data.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters with letters and numbers"
        )
    
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not user.verify_password(password_data.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Set new password
    user.set_password(password_data.new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    
    # Log password change
    audit_logger.log_password_change(
        user_id=user.id,
        ip_address=request.client.host
    )
    
    return {"message": "Password changed successfully"}

@router.get("/sessions", response_model=List[SessionInfo])
async def get_user_sessions(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get user's active sessions."""
    current_session_id = token_data.get("session_id")
    
    sessions = db.query(UserSession).filter(
        and_(
            UserSession.user_id == token_data["user_id"],
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        )
    ).order_by(UserSession.last_active.desc()).all()
    
    session_info = []
    for session in sessions:
        session_info.append(SessionInfo(
            id=session.session_token,
            user_agent=session.user_agent,
            ip_address=session.ip_address,
            created_at=session.created_at,
            last_active=session.last_active,
            current=(session.session_token == current_session_id)
        ))
    
    return session_info

@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Revoke a specific session."""
    session = db.query(UserSession).filter(
        and_(
            UserSession.session_token == session_id,
            UserSession.user_id == token_data["user_id"]
        )
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session.is_active = False
    db.commit()
    
    return {"message": "Session revoked successfully"}

@router.delete("/sessions")
async def revoke_all_sessions(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Revoke all user sessions except current one."""
    current_session_id = token_data.get("session_id")
    
    sessions = db.query(UserSession).filter(
        and_(
            UserSession.user_id == token_data["user_id"],
            UserSession.session_token != current_session_id,
            UserSession.is_active == True
        )
    ).all()
    
    for session in sessions:
        session.is_active = False
    
    db.commit()
    
    return {"message": f"Revoked {len(sessions)} sessions"}

@router.get("/stats", response_model=UserStats)
async def get_user_stats(
    token_data: dict = Depends(get_current_user_token),
    db: Session = Depends(get_db)
):
    """Get user statistics."""
    user = db.query(User).filter(User.id == token_data["user_id"]).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Calculate stats (would integrate with other modules in real implementation)
    account_age = (datetime.utcnow() - user.created_at).days
    
    return UserStats(
        total_logins=0,  # Would query login history
        files_uploaded=0,  # Would query file uploads
        chat_sessions=0,  # Would query chat sessions
        database_queries=0,  # Would query database operations
        last_activity=user.last_login,
        account_age_days=account_age
    )