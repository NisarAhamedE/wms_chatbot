from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from .connection import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    sessions = relationship("UserSession", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    token = Column(String(500), unique=True, nullable=False)
    device_info = Column(JSON)
    ip_address = Column(String(45))
    expires_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="sessions")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    title = Column(String(255))
    category = Column(String(100))
    status = Column(String(50), default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    role = Column(String(50))  # user, assistant, system
    content = Column(Text)
    agent_used = Column(String(100))
    confidence_score = Column(Float)
    sources = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="messages")
    
    __table_args__ = (
        Index('idx_messages_conversation', 'conversation_id'),
        Index('idx_messages_created', 'created_at'),
    )

class FileUpload(Base):
    __tablename__ = "file_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    filename = Column(String(255))
    file_path = Column(String(500))
    file_type = Column(String(50))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    status = Column(String(50), default="pending")
    category = Column(String(100))
    extracted_text = Column(Text)
    metadata = Column(JSON)
    processing_progress = Column(Integer, default=0)
    processing_stage = Column(String(100))
    error_message = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime)
    
    __table_args__ = (
        Index('idx_files_user', 'user_id'),
        Index('idx_files_status', 'status'),
        Index('idx_files_category', 'category'),
    )

# WMS-specific models
class InventoryItem(Base):
    __tablename__ = "inventory_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    warehouse_id = Column(String(50), index=True)
    location_id = Column(String(50), index=True)
    quantity_on_hand = Column(Integer, default=0)
    quantity_available = Column(Integer, default=0)
    quantity_allocated = Column(Integer, default=0)
    last_counted_date = Column(DateTime)
    cycle_count_due = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    __table_args__ = (
        Index('idx_inventory_sku_warehouse', 'sku', 'warehouse_id'),
    )

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), index=True)
    warehouse_id = Column(String(50), index=True)
    status = Column(String(50), index=True)
    priority = Column(Integer, default=5)
    total_lines = Column(Integer)
    total_quantity = Column(Integer)
    wave_id = Column(String(100), index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    shipped_at = Column(DateTime)

class Wave(Base):
    __tablename__ = "waves"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wave_id = Column(String(100), unique=True, nullable=False, index=True)
    warehouse_id = Column(String(50), index=True)
    status = Column(String(50), index=True)
    release_strategy = Column(String(50))
    total_orders = Column(Integer, default=0)
    total_lines = Column(Integer, default=0)
    total_quantity = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    released_at = Column(DateTime)
    completed_at = Column(DateTime)

class PickingTransaction(Base):
    __tablename__ = "picking_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(String(100), index=True)
    wave_id = Column(String(100), index=True)
    user_id = Column(String(100), index=True)
    sku = Column(String(100), index=True)
    location_id = Column(String(50))
    quantity_picked = Column(Integer)
    pick_timestamp = Column(DateTime, server_default=func.now())
    pick_duration_seconds = Column(Integer)
    
    __table_args__ = (
        Index('idx_picking_user_date', 'user_id', 'pick_timestamp'),
    )

class AgentLog(Base):
    __tablename__ = "agent_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(100), index=True)
    agent_category = Column(String(100), index=True)
    agent_name = Column(String(100), index=True)
    input_query = Column(Text)
    output_response = Column(Text)
    execution_time_ms = Column(Integer)
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    tools_used = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index('idx_agent_logs_session', 'session_id'),
        Index('idx_agent_logs_category', 'agent_category'),
    )