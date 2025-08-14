"""
SQLAlchemy models for the WMS Chatbot System.
Implements the comprehensive 16-category database schema with proper relationships.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, 
    DECIMAL, JSON, Index, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class WMSCategory(Base, TimestampMixin):
    """WMS Categories (16 main categories)"""
    __tablename__ = "wms_categories"
    
    category_id = Column(Integer, primary_key=True)
    category_name = Column(String(100), nullable=False)
    category_code = Column(String(20), unique=True, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    sub_categories = relationship("WMSSubCategory", back_populates="category")
    validation_rules = relationship("DataValidationRule", back_populates="category")
    category_assignments = relationship("DataCategoryAssignment", back_populates="category")
    storage_mappings = relationship("DataStorageMapping", back_populates="category")


class WMSSubCategory(Base, TimestampMixin):
    """WMS Sub-Categories (5 sub-categories per main category)"""
    __tablename__ = "wms_sub_categories"
    
    sub_category_id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("wms_categories.category_id"), nullable=False)
    sub_category_name = Column(String(100), nullable=False)
    sub_category_code = Column(String(20), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    category = relationship("WMSCategory", back_populates="sub_categories")
    category_assignments = relationship("DataCategoryAssignment", back_populates="sub_category")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('category_id', 'sub_category_code', name='unique_category_subcat_code'),
        Index('idx_subcategory_category', 'category_id'),
    )


class Location(Base, TimestampMixin):
    """Locations (Category 2) - Warehouse locations and layout"""
    __tablename__ = "locations"
    
    location_id = Column(String(50), primary_key=True)
    zone_id = Column(String(20), nullable=False)
    aisle = Column(String(10))
    bay = Column(String(10))
    level = Column(String(10))
    position = Column(String(10))
    location_type = Column(String(20))  # 'PICK', 'RESERVE', 'STAGING', etc.
    capacity_qty = Column(DECIMAL(15, 3))
    capacity_volume = Column(DECIMAL(15, 3))
    capacity_weight = Column(DECIMAL(15, 3))
    is_pickable = Column(Boolean, default=True)
    is_receivable = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    last_counted = Column(DateTime(timezone=True))
    vector_embedding_id = Column(UUID(as_uuid=True))
    
    # Relationships
    inventory_records = relationship("Inventory", back_populates="location")
    work_assignments = relationship("WorkAssignment", back_populates="location")
    inventory_movements_from = relationship("InventoryMovement", foreign_keys="InventoryMovement.from_location_id", back_populates="from_location")
    inventory_movements_to = relationship("InventoryMovement", foreign_keys="InventoryMovement.to_location_id", back_populates="to_location")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_location_zone', 'zone_id'),
        Index('idx_location_type', 'location_type'),
        Index('idx_location_pickable', 'is_pickable'),
        Index('idx_location_vector', 'vector_embedding_id'),
        CheckConstraint('capacity_qty >= 0', name='check_positive_capacity_qty'),
        CheckConstraint('capacity_volume >= 0', name='check_positive_capacity_volume'),
        CheckConstraint('capacity_weight >= 0', name='check_positive_capacity_weight'),
    )


class Item(Base, TimestampMixin):
    """Items (Category 3) - Product master data"""
    __tablename__ = "items"
    
    item_id = Column(String(50), primary_key=True)
    item_description = Column(Text, nullable=False)
    item_category = Column(String(50))
    item_class = Column(String(20))
    unit_of_measure = Column(String(10))
    standard_cost = Column(DECIMAL(15, 4))
    weight = Column(DECIMAL(15, 3))
    length = Column(DECIMAL(15, 3))
    width = Column(DECIMAL(15, 3))
    height = Column(DECIMAL(15, 3))
    lot_controlled = Column(Boolean, default=False)
    serial_controlled = Column(Boolean, default=False)
    expiration_controlled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    vector_embedding_id = Column(UUID(as_uuid=True))
    
    # Relationships
    inventory_records = relationship("Inventory", back_populates="item")
    work_assignments = relationship("WorkAssignment", back_populates="item")
    inventory_movements = relationship("InventoryMovement", back_populates="item")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_item_category', 'item_category'),
        Index('idx_item_class', 'item_class'),
        Index('idx_item_active', 'is_active'),
        Index('idx_item_vector', 'vector_embedding_id'),
        Index('idx_item_lot_controlled', 'lot_controlled'),
        Index('idx_item_description_gin', 'item_description', postgresql_using='gin', postgresql_ops={'item_description': 'gin_trgm_ops'}),
        CheckConstraint('standard_cost >= 0', name='check_positive_cost'),
        CheckConstraint('weight >= 0', name='check_positive_weight'),
    )


class Inventory(Base, TimestampMixin):
    """Inventory (Category 7) - Stock tracking and management"""
    __tablename__ = "inventory"
    
    inventory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(String(50), ForeignKey("items.item_id"), nullable=False)
    location_id = Column(String(50), ForeignKey("locations.location_id"), nullable=False)
    lot_number = Column(String(50))
    serial_number = Column(String(50))
    expiration_date = Column(DateTime(timezone=True))
    quantity_on_hand = Column(DECIMAL(15, 3), nullable=False, default=0)
    quantity_allocated = Column(DECIMAL(15, 3), nullable=False, default=0)
    last_movement_date = Column(DateTime(timezone=True))
    
    # Relationships
    item = relationship("Item", back_populates="inventory_records")
    location = relationship("Location", back_populates="inventory_records")
    movements = relationship("InventoryMovement", back_populates="inventory")
    
    # Computed column for available quantity
    @property
    def quantity_available(self) -> Decimal:
        return self.quantity_on_hand - self.quantity_allocated
    
    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint('item_id', 'location_id', 'lot_number', 'serial_number', name='unique_inventory_key'),
        Index('idx_inventory_item', 'item_id'),
        Index('idx_inventory_location', 'location_id'),
        Index('idx_inventory_lot', 'lot_number'),
        Index('idx_inventory_serial', 'serial_number'),
        Index('idx_inventory_expiration', 'expiration_date'),
        CheckConstraint('quantity_on_hand >= 0', name='check_positive_on_hand'),
        CheckConstraint('quantity_allocated >= 0', name='check_positive_allocated'),
        CheckConstraint('quantity_allocated <= quantity_on_hand', name='check_allocation_limit'),
    )


class InventoryMovement(Base, TimestampMixin):
    """Inventory Movements - Time-series tracking of all inventory changes"""
    __tablename__ = "inventory_movements"
    
    movement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_id = Column(UUID(as_uuid=True), ForeignKey("inventory.inventory_id"), nullable=False)
    item_id = Column(String(50), ForeignKey("items.item_id"), nullable=False)  # Denormalized for performance
    movement_type = Column(String(20), nullable=False)  # 'RECEIPT', 'SHIPMENT', 'ADJUSTMENT', 'TRANSFER'
    movement_quantity = Column(DECIMAL(15, 3), nullable=False)
    movement_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    reason_code = Column(String(20))
    reference_document = Column(String(50))
    user_id = Column(String(50))
    from_location_id = Column(String(50), ForeignKey("locations.location_id"))
    to_location_id = Column(String(50), ForeignKey("locations.location_id"))
    vector_embedding_id = Column(UUID(as_uuid=True))
    
    # Relationships
    inventory = relationship("Inventory", back_populates="movements")
    item = relationship("Item", back_populates="inventory_movements")
    from_location = relationship("Location", foreign_keys=[from_location_id], back_populates="inventory_movements_from")
    to_location = relationship("Location", foreign_keys=[to_location_id], back_populates="inventory_movements_to")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_movement_date', 'movement_date'),
        Index('idx_movement_inventory', 'inventory_id'),
        Index('idx_movement_item', 'item_id'),
        Index('idx_movement_type', 'movement_type'),
        Index('idx_movement_reference', 'reference_document'),
        Index('idx_movement_user', 'user_id'),
        CheckConstraint('movement_quantity != 0', name='check_nonzero_quantity'),
    )


class WorkAssignment(Base, TimestampMixin):
    """Work Management (Category 6) - Labor management and task assignments"""
    __tablename__ = "work_assignments"
    
    work_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50), nullable=False)
    work_type = Column(String(20), nullable=False)  # 'PICK', 'PUTAWAY', 'COUNT', 'REPLENISH'
    priority = Column(Integer, default=5)
    assigned_at = Column(DateTime(timezone=True), default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    status = Column(String(20), default='ASSIGNED')  # 'ASSIGNED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'
    estimated_duration = Column(Integer)  # in minutes
    actual_duration = Column(Integer)
    location_id = Column(String(50), ForeignKey("locations.location_id"))
    item_id = Column(String(50), ForeignKey("items.item_id"))
    quantity = Column(DECIMAL(15, 3))
    instructions = Column(Text)
    vector_embedding_id = Column(UUID(as_uuid=True))
    
    # Relationships
    location = relationship("Location", back_populates="work_assignments")
    item = relationship("Item", back_populates="work_assignments")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_work_user', 'user_id'),
        Index('idx_work_type', 'work_type'),
        Index('idx_work_status', 'status'),
        Index('idx_work_priority', 'priority'),
        Index('idx_work_assigned', 'assigned_at'),
        CheckConstraint('priority BETWEEN 1 AND 10', name='check_priority_range'),
        CheckConstraint('estimated_duration > 0', name='check_positive_estimated_duration'),
        CheckConstraint('actual_duration > 0', name='check_positive_actual_duration'),
    )


class WMSKpi(Base, TimestampMixin):
    """WMS KPIs and Analytics - Time-series performance metrics"""
    __tablename__ = "wms_kpis"
    
    kpi_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(Integer, ForeignKey("wms_categories.category_id"))
    kpi_name = Column(String(100), nullable=False)
    kpi_value = Column(DECIMAL(15, 4))
    kpi_unit = Column(String(20))
    calculation_date = Column(DateTime(timezone=True), nullable=False, default=func.now())
    data_source = Column(String(50))
    metadata = Column(JSON)
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_kpi_category', 'category_id'),
        Index('idx_kpi_name', 'kpi_name'),
        Index('idx_kpi_date', 'calculation_date'),
        Index('idx_kpi_source', 'data_source'),
    )


class DataCategorizationRequest(Base, TimestampMixin):
    """Category 16: Data Categorization Requests"""
    __tablename__ = "data_categorization_requests"
    
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50), nullable=False)
    raw_data = Column(JSON, nullable=False)
    data_hash = Column(String(64), nullable=False)  # SHA-256 for deduplication
    data_format = Column(String(20))  # 'text', 'image', 'audio', 'video'
    submitted_at = Column(DateTime(timezone=True), default=func.now())
    status = Column(String(20), default='PENDING')  # 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'MANUAL_REVIEW'
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    manual_review_required = Column(Boolean, default=False)
    manual_review_reason = Column(Text)
    vector_embedding_id = Column(UUID(as_uuid=True))
    
    # Relationships
    category_assignments = relationship("DataCategoryAssignment", back_populates="request")
    validation_results = relationship("DataValidationResult", back_populates="request")
    storage_mappings = relationship("DataStorageMapping", back_populates="request")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_categorization_user_status', 'user_id', 'status'),
        Index('idx_categorization_hash', 'data_hash'),
        Index('idx_categorization_format', 'data_format'),
        Index('idx_categorization_submitted', 'submitted_at'),
        Index('idx_categorization_manual_review', 'manual_review_required'),
    )


class DataCategoryAssignment(Base, TimestampMixin):
    """Category assignments for data categorization requests"""
    __tablename__ = "data_category_assignments"
    
    assignment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("data_categorization_requests.request_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("wms_categories.category_id"), nullable=False)
    sub_category_id = Column(Integer, ForeignKey("wms_sub_categories.sub_category_id"))
    assignment_type = Column(String(20), nullable=False)  # 'PRIMARY', 'SECONDARY'
    confidence_score = Column(DECIMAL(5, 4), nullable=False)  # 0.0000 to 1.0000
    assignment_method = Column(String(50), nullable=False)  # 'ML_CLASSIFICATION', 'PATTERN_MATCHING', 'KEYWORD_ANALYSIS', 'MANUAL'
    assigned_at = Column(DateTime(timezone=True), default=func.now())
    assigned_by = Column(String(50))  # user_id or 'SYSTEM'
    validation_status = Column(String(20), default='VALID')  # 'VALID', 'INVALID', 'PENDING_REVIEW'
    validation_notes = Column(Text)
    
    # Relationships
    request = relationship("DataCategorizationRequest", back_populates="category_assignments")
    category = relationship("WMSCategory", back_populates="category_assignments")
    sub_category = relationship("WMSSubCategory", back_populates="category_assignments")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_assignment_request', 'request_id'),
        Index('idx_assignment_category', 'category_id', 'assignment_type'),
        Index('idx_assignment_confidence', 'confidence_score'),
        Index('idx_assignment_method', 'assignment_method'),
        CheckConstraint('confidence_score BETWEEN 0.0 AND 1.0', name='check_confidence_range'),
        CheckConstraint('assignment_type IN (\'PRIMARY\', \'SECONDARY\')', name='check_assignment_type'),
    )


class DataValidationRule(Base, TimestampMixin):
    """Validation rules for each WMS category"""
    __tablename__ = "data_validation_rules"
    
    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id = Column(Integer, ForeignKey("wms_categories.category_id"), nullable=False)
    rule_name = Column(String(100), nullable=False)
    rule_type = Column(String(30), nullable=False)  # 'REQUIRED_FIELD', 'DATA_TYPE', 'BUSINESS_LOGIC', 'PATTERN_MATCH'
    rule_definition = Column(JSON, nullable=False)
    priority = Column(Integer, default=5)  # 1 (highest) to 10 (lowest)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(50))
    
    # Relationships
    category = relationship("WMSCategory", back_populates="validation_rules")
    validation_results = relationship("DataValidationResult", back_populates="rule")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_validation_rule_category', 'category_id', 'is_active'),
        Index('idx_validation_rule_type', 'rule_type'),
        Index('idx_validation_rule_priority', 'priority'),
        CheckConstraint('priority BETWEEN 1 AND 10', name='check_rule_priority_range'),
    )


class DataValidationResult(Base, TimestampMixin):
    """Results of validation rule execution"""
    __tablename__ = "data_validation_results"
    
    result_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("data_categorization_requests.request_id"), nullable=False)
    rule_id = Column(UUID(as_uuid=True), ForeignKey("data_validation_rules.rule_id"), nullable=False)
    validation_passed = Column(Boolean, nullable=False)
    validation_message = Column(Text)
    validation_details = Column(JSON)
    validated_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    request = relationship("DataCategorizationRequest", back_populates="validation_results")
    rule = relationship("DataValidationRule", back_populates="validation_results")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_validation_result_request', 'request_id'),
        Index('idx_validation_result_rule', 'rule_id'),
        Index('idx_validation_result_passed', 'validation_passed'),
        Index('idx_validation_result_date', 'validated_at'),
    )


class DataStorageMapping(Base, TimestampMixin):
    """Mapping between categorization requests and storage locations"""
    __tablename__ = "data_storage_mappings"
    
    mapping_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("data_categorization_requests.request_id"), nullable=False)
    category_id = Column(Integer, ForeignKey("wms_categories.category_id"), nullable=False)
    postgres_table_name = Column(String(100))
    postgres_record_id = Column(String(100))
    vector_collection = Column(String(100))
    vector_record_id = Column(UUID(as_uuid=True))
    storage_status = Column(String(20), default='STORED')  # 'STORED', 'FAILED', 'PENDING'
    storage_metadata = Column(JSON)
    
    # Relationships
    request = relationship("DataCategorizationRequest", back_populates="storage_mappings")
    category = relationship("WMSCategory", back_populates="storage_mappings")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_storage_mapping_request', 'request_id'),
        Index('idx_storage_mapping_category', 'category_id'),
        Index('idx_storage_mapping_table', 'postgres_table_name'),
        Index('idx_storage_mapping_status', 'storage_status'),
    )


# User management tables for multi-role support
class User(Base, TimestampMixin):
    """User accounts with role-based access"""
    __tablename__ = "users"
    
    user_id = Column(String(50), primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(200))
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    user_roles = relationship("UserRole", back_populates="user")
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_user_username', 'username'),
        Index('idx_user_email', 'email'),
        Index('idx_user_active', 'is_active'),
    )


class Role(Base, TimestampMixin):
    """Role definitions for RBAC"""
    __tablename__ = "roles"
    
    role_id = Column(Integer, primary_key=True)
    role_name = Column(String(50), unique=True, nullable=False)
    role_description = Column(Text)
    permissions = Column(JSON)  # List of permissions
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user_roles = relationship("UserRole", back_populates="role")


class UserRole(Base, TimestampMixin):
    """User-Role assignments"""
    __tablename__ = "user_roles"
    
    user_role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id"), nullable=False)
    assigned_by = Column(String(50))
    
    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='unique_user_role'),
        Index('idx_user_role_user', 'user_id'),
        Index('idx_user_role_role', 'role_id'),
    )