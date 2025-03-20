# File: app/schemas/compatibility.py
"""
Schema compatibility layer for HideSync API.

This module provides direct mappings for the schema classes expected by
the existing endpoint files. It ensures backward compatibility while
we transition to the new schema structure.
"""

from typing import Dict, List, Optional, Any, Union, Set
from datetime import datetime, date
from pydantic import BaseModel, Field, EmailStr, validator, RootModel

from app.db.models.enums import (
    SaleStatus, PaymentStatus, FulfillmentStatus, CustomerStatus, CustomerTier,
    CustomerSource, InventoryStatus, MaterialType, MaterialQualityGrade,
    ProjectStatus, ProjectType, ToolCategory, StorageLocationType,
    SupplierStatus, PickingListStatus, ComponentType, SkillLevel, UserRole
)

# ===============================
# AUTH SCHEMAS
# ===============================

class Token(BaseModel):
    """Token schema for authentication."""
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """Token payload schema."""
    sub: Optional[int] = None
    exp: Optional[int] = None


# ===============================
# USER SCHEMAS
# ===============================

class UserBase(BaseModel):
    """Base user model with common fields."""
    email: EmailStr
    username: str
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    phone: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""
    password: str

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    phone: Optional[str] = None


class User(UserBase):
    """User model as expected by endpoint files."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserWithPermissions(User):
    """User model with additional permissions information."""
    permissions: Set[str] = set()
    role_name: Optional[str] = None


class PasswordReset(BaseModel):
    """Schema for password reset requests."""
    email: EmailStr


class PasswordChange(BaseModel):
    """Schema for password change requests."""
    old_password: str
    new_password: str

    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


# ===============================
# CUSTOMER SCHEMAS
# ===============================

class Customer(BaseModel):
    """Customer model as expected by endpoint files."""
    id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    status: Optional[CustomerStatus] = None
    tier: Optional[CustomerTier] = None
    source: Optional[CustomerSource] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerCreate(BaseModel):
    """Schema for creating a customer."""
    name: str
    email: EmailStr
    phone: Optional[str] = None
    status: Optional[CustomerStatus] = None
    tier: Optional[CustomerTier] = None
    source: Optional[CustomerSource] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    status: Optional[CustomerStatus] = None
    tier: Optional[CustomerTier] = None
    source: Optional[CustomerSource] = None
    company_name: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CustomerSearchParams(BaseModel):
    """Search parameters for customers."""
    status: Optional[str] = None
    tier: Optional[str] = None
    search: Optional[str] = None


class CustomerWithSales(Customer):
    """Customer model with sales history."""
    sales: List[Any] = []
    total_spent: float = 0.0
    average_order_value: float = 0.0
    first_purchase_date: Optional[datetime] = None
    last_purchase_date: Optional[datetime] = None
    sales_count: int = 0


# ===============================
# SALE SCHEMAS
# ===============================

class SaleItem(BaseModel):
    """Sale item model."""
    id: int
    sale_id: int
    quantity: int
    price: float
    tax: float
    name: str
    type: Optional[str] = None
    sku: Optional[str] = None
    product_id: Optional[int] = None
    project_id: Optional[int] = None
    pattern_id: Optional[int] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class SaleItemCreate(BaseModel):
    """Schema for creating a sale item."""
    quantity: int
    price: float
    tax: Optional[float] = 0.0
    name: str
    type: Optional[str] = None
    sku: Optional[str] = None
    product_id: Optional[int] = None
    project_id: Optional[int] = None
    pattern_id: Optional[int] = None
    notes: Optional[str] = None


class Sale(BaseModel):
    """Sale model."""
    id: int
    customer_id: int
    created_at: datetime
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    subtotal: Optional[float] = None
    taxes: Optional[float] = None
    shipping: Optional[float] = None
    platform_fees: Optional[float] = None
    total_amount: Optional[float] = None
    net_revenue: Optional[float] = None
    deposit_amount: Optional[float] = None
    balance_due: Optional[float] = None
    status: SaleStatus
    payment_status: PaymentStatus
    fulfillment_status: Optional[FulfillmentStatus] = None
    channel: Optional[str] = None
    platform_order_id: Optional[str] = None
    marketplace_data: Optional[Dict[str, Any]] = None
    shipping_method: Optional[str] = None
    shipping_provider: Optional[str] = None
    tracking_number: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    customization: Optional[str] = None

    class Config:
        from_attributes = True


class SaleCreate(BaseModel):
    """Schema for creating a sale."""
    customer_id: int
    due_date: Optional[datetime] = None
    subtotal: Optional[float] = None
    taxes: Optional[float] = None
    shipping: Optional[float] = None
    platform_fees: Optional[float] = None
    total_amount: Optional[float] = None
    net_revenue: Optional[float] = None
    deposit_amount: Optional[float] = None
    balance_due: Optional[float] = None
    status: Optional[SaleStatus] = None
    payment_status: Optional[PaymentStatus] = None
    fulfillment_status: Optional[FulfillmentStatus] = None
    channel: Optional[str] = None
    platform_order_id: Optional[str] = None
    marketplace_data: Optional[Dict[str, Any]] = None
    shipping_method: Optional[str] = None
    shipping_provider: Optional[str] = None
    tracking_number: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    customization: Optional[str] = None
    items: List[SaleItemCreate] = []


class SaleUpdate(BaseModel):
    """Schema for updating a sale."""
    customer_id: Optional[int] = None
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    subtotal: Optional[float] = None
    taxes: Optional[float] = None
    shipping: Optional[float] = None
    platform_fees: Optional[float] = None
    total_amount: Optional[float] = None
    net_revenue: Optional[float] = None
    deposit_amount: Optional[float] = None
    balance_due: Optional[float] = None
    status: Optional[SaleStatus] = None
    payment_status: Optional[PaymentStatus] = None
    fulfillment_status: Optional[FulfillmentStatus] = None
    channel: Optional[str] = None
    platform_order_id: Optional[str] = None
    marketplace_data: Optional[Dict[str, Any]] = None
    shipping_method: Optional[str] = None
    shipping_provider: Optional[str] = None
    tracking_number: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    customization: Optional[str] = None


class SaleSearchParams(BaseModel):
    """Search parameters for sales."""
    status: Optional[str] = None
    customer_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    payment_status: Optional[str] = None
    search: Optional[str] = None


class SaleWithDetails(Sale):
    """Sale with additional details."""
    items: List[SaleItem] = []
    customer: Optional[Customer] = None


class SaleStatusUpdate(BaseModel):
    """Schema for updating sale status."""
    status: str
    notes: Optional[str] = None


class PaymentUpdate(BaseModel):
    """Schema for updating payment status."""
    payment_status: str
    amount: Optional[float] = None
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    notes: Optional[str] = None


# ===============================
# MATERIAL SCHEMAS
# ===============================

class Material(BaseModel):
    """Material model."""
    id: int
    name: str
    material_type: MaterialType
    status: Optional[InventoryStatus] = None
    quantity: float
    unit: str
    quality: Optional[MaterialQualityGrade] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    reorder_point: Optional[float] = None
    supplier_sku: Optional[str] = None
    cost: Optional[float] = None
    price: Optional[float] = None
    storage_location: Optional[str] = None
    notes: Optional[str] = None
    thumbnail: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MaterialCreate(RootModel):
    """Union type for creating any material type."""
    root: Dict[str, Any]


class MaterialUpdate(BaseModel):
    """Schema for updating material information."""
    name: Optional[str] = None
    status: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    quality: Optional[str] = None
    supplier_id: Optional[int] = None
    supplier: Optional[str] = None
    sku: Optional[str] = None
    description: Optional[str] = None
    reorder_point: Optional[float] = None
    supplier_sku: Optional[str] = None
    cost: Optional[float] = None
    price: Optional[float] = None
    storage_location: Optional[str] = None
    notes: Optional[str] = None
    thumbnail: Optional[str] = None


class MaterialSearchParams(BaseModel):
    """Search parameters for materials."""
    material_type: Optional[str] = None
    quality: Optional[str] = None
    in_stock: Optional[bool] = None
    search: Optional[str] = None


class MaterialWithInventory(Material):
    """Material with inventory details."""
    inventory: List[Any] = []
    total_quantity: float = 0.0
    total_value: float = 0.0
    storage_locations: List[str] = []


# ===============================
# PROJECT SCHEMAS
# ===============================

class ProjectComponent(BaseModel):
    """Project component model."""
    id: int
    project_id: int
    component_id: int
    quantity: int
    component_name: Optional[str] = None
    component_type: Optional[ComponentType] = None

    class Config:
        from_attributes = True


class ProjectComponentCreate(BaseModel):
    """Schema for adding a component to a project."""
    component_id: int
    quantity: int


class TimelineTask(BaseModel):
    """Timeline task model."""
    id: str
    project_id: str
    name: str
    start_date: datetime
    end_date: datetime
    progress: Optional[int] = 0
    status: Optional[str] = None
    dependencies: Optional[List[str]] = None
    is_critical_path: Optional[bool] = False
    days_remaining: Optional[int] = None
    is_overdue: Optional[bool] = False

    class Config:
        from_attributes = True


class TimelineTaskCreate(BaseModel):
    """Schema for creating a timeline task."""
    name: str
    start_date: datetime
    end_date: datetime
    progress: Optional[int] = 0
    status: Optional[str] = None
    dependencies: Optional[List[str]] = None
    is_critical_path: Optional[bool] = False
    project_id: str


class TimelineTaskUpdate(BaseModel):
    """Schema for updating a timeline task."""
    name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    progress: Optional[int] = None
    status: Optional[str] = None
    dependencies: Optional[List[str]] = None
    is_critical_path: Optional[bool] = None


class Project(BaseModel):
    """Project model."""
    id: int
    name: str
    description: Optional[str] = None
    type: ProjectType
    status: ProjectStatus
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    progress: Optional[float] = 0
    completion_percentage: Optional[int] = 0
    sale_id: Optional[int] = None
    template_id: Optional[int] = None
    customer: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    """Schema for creating a project."""
    name: str
    description: Optional[str] = None
    type: ProjectType
    status: Optional[ProjectStatus] = ProjectStatus.CONCEPT
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    progress: Optional[float] = 0
    completion_percentage: Optional[int] = 0
    sale_id: Optional[int] = None
    template_id: Optional[int] = None
    customer: Optional[str] = None
    notes: Optional[str] = None
    components: Optional[List[ProjectComponentCreate]] = None
    timeline_tasks: Optional[List[TimelineTaskCreate]] = None


class ProjectUpdate(BaseModel):
    """Schema for updating a project."""
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[ProjectType] = None
    status: Optional[ProjectStatus] = None
    start_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    progress: Optional[float] = None
    completion_percentage: Optional[int] = None
    sale_id: Optional[int] = None
    template_id: Optional[int] = None
    customer: Optional[str] = None
    notes: Optional[str] = None


class ProjectSearchParams(BaseModel):
    """Search parameters for projects."""
    status: Optional[str] = None
    type: Optional[str] = None
    customer_id: Optional[int] = None
    search: Optional[str] = None


class ProjectWithDetails(Project):
    """Project with detailed information."""
    components: List[ProjectComponent] = []
    timeline_tasks: List[TimelineTask] = []
    materials_summary: Optional[Dict[str, Any]] = None
    customer_details: Optional[Dict[str, Any]] = None


# ===============================
# INVENTORY SCHEMAS
# ===============================

class Inventory(BaseModel):
    """Inventory model."""
    id: int
    item_type: str
    item_id: int
    quantity: float
    status: InventoryStatus
    storage_location: Optional[str] = None
    item_name: Optional[str] = None
    value: Optional[float] = None
    is_low_stock: Optional[bool] = None
    reorder_point: Optional[float] = None
    days_of_supply: Optional[int] = None

    class Config:
        from_attributes = True


class InventoryTransaction(BaseModel):
    """Inventory transaction model."""
    id: int
    item_type: str
    item_id: int
    quantity: float
    transaction_type: str
    adjustment_type: Optional[str] = None
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    item_name: Optional[str] = None

    class Config:
        from_attributes = True


class InventoryTransactionCreate(BaseModel):
    """Schema for creating an inventory transaction."""
    item_type: str
    item_id: int
    quantity: float
    transaction_type: str
    adjustment_type: Optional[str] = None
    reference_id: Optional[str] = None
    reference_type: Optional[str] = None
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    notes: Optional[str] = None


class InventorySearchParams(BaseModel):
    """Search parameters for inventory."""
    status: Optional[str] = None
    location: Optional[str] = None
    item_type: Optional[str] = None
    search: Optional[str] = None


class InventoryAdjustment(BaseModel):
    """Schema for inventory adjustment."""
    item_type: str
    item_id: int
    quantity: float
    adjustment_type: str
    reason: str
    notes: Optional[str] = None


class StockLevelReport(BaseModel):
    """Stock level report model."""
    total_value: float
    category_breakdown: Dict[str, Any]
    low_stock_items: List[Inventory]
    out_of_stock_items: List[Inventory]
    items_by_location: Dict[str, int]
    reorder_recommendations: List[Dict[str, Any]]


# ===============================
# STORAGE SCHEMAS
# ===============================

class StorageLocation(BaseModel):
    """Storage location model."""
    id: str
    name: str
    type: StorageLocationType
    section: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[Dict[str, Any]] = None
    capacity: Optional[int] = None
    utilized: Optional[int] = 0
    status: Optional[str] = None
    notes: Optional[str] = None
    parent_storage: Optional[str] = None
    last_modified: Optional[str] = None
    usage_percentage: Optional[float] = None
    item_count: Optional[int] = None
    child_locations: Optional[List[str]] = None

    class Config:
        from_attributes = True


class StorageLocationCreate(BaseModel):
    """Schema for creating a storage location."""
    name: str
    type: StorageLocationType
    section: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[Dict[str, Any]] = None
    capacity: Optional[int] = None
    utilized: Optional[int] = 0
    status: Optional[str] = None
    notes: Optional[str] = None
    parent_storage: Optional[str] = None
    cells: Optional[List[Any]] = None


class StorageLocationUpdate(BaseModel):
    """Schema for updating a storage location."""
    name: Optional[str] = None
    type: Optional[StorageLocationType] = None
    section: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[Dict[str, Any]] = None
    capacity: Optional[int] = None
    utilized: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    parent_storage: Optional[str] = None


class StorageCell(BaseModel):
    """Storage cell model."""
    storage_id: str
    position: Dict[str, Any]
    item_id: Optional[int] = None
    item_type: Optional[str] = None
    occupied: bool = False
    notes: Optional[str] = None
    item_name: Optional[str] = None

    class Config:
        from_attributes = True


class StorageCellCreate(BaseModel):
    """Schema for creating a storage cell."""
    position: Dict[str, Any]
    item_id: Optional[int] = None
    item_type: Optional[str] = None
    occupied: bool = False
    notes: Optional[str] = None
    storage_id: str


class StorageAssignment(BaseModel):
    """Storage assignment model."""
    id: str
    material_id: int
    material_type: str
    storage_id: str
    position: Optional[Dict[str, Any]] = None
    quantity: float
    assigned_date: str
    assigned_by: Optional[str] = None
    notes: Optional[str] = None
    material_name: Optional[str] = None
    storage_name: Optional[str] = None

    class Config:
        from_attributes = True


class StorageAssignmentCreate(BaseModel):
    """Schema for creating a storage assignment."""
    material_id: int
    material_type: str
    storage_id: str
    position: Optional[Dict[str, Any]] = None
    quantity: float
    notes: Optional[str] = None
    assigned_by: Optional[str] = None


class StorageMove(BaseModel):
    """Storage move model."""
    id: str
    material_id: int
    material_type: str
    from_storage_id: str
    to_storage_id: str
    quantity: float
    reason: Optional[str] = None
    notes: Optional[str] = None
    move_date: str
    moved_by: Optional[str] = None
    material_name: Optional[str] = None
    from_storage_name: Optional[str] = None
    to_storage_name: Optional[str] = None

    class Config:
        from_attributes = True


class StorageMoveCreate(BaseModel):
    """Schema for creating a storage move."""
    material_id: int
    material_type: str
    from_storage_id: str
    to_storage_id: str
    quantity: float
    reason: Optional[str] = None
    notes: Optional[str] = None
    moved_by: Optional[str] = None


class StorageSearchParams(BaseModel):
    """Search parameters for storage locations."""
    type: Optional[str] = None
    section: Optional[str] = None
    status: Optional[str] = None
    search: Optional[str] = None


class StorageOccupancyReport(BaseModel):
    """Storage occupancy report model."""
    total_locations: int
    total_capacity: int
    total_utilized: int
    overall_usage_percentage: float
    locations_by_type: Dict[str, int]
    locations_by_section: Dict[str, int]
    most_utilized_locations: List[Dict[str, Any]]
    least_utilized_locations: List[Dict[str, Any]]
    recommendations: List[str]


# ===============================
# SUPPLIER SCHEMAS
# ===============================

class Supplier(BaseModel):
    """Supplier model."""
    id: int
    name: str
    category: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[int] = None
    status: Optional[SupplierStatus] = None
    notes: Optional[str] = None
    material_categories: Optional[List[str]] = None
    logo: Optional[str] = None
    last_order_date: Optional[str] = None
    payment_terms: Optional[str] = None
    min_order_amount: Optional[str] = None
    lead_time: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    average_rating: Optional[float] = None
    total_orders: Optional[int] = None
    total_spent: Optional[float] = None

    class Config:
        from_attributes = True


class SupplierCreate(BaseModel):
    """Schema for creating a supplier."""
    name: str
    category: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[int] = None
    status: Optional[SupplierStatus] = None
    notes: Optional[str] = None
    material_categories: Optional[List[str]] = None
    logo: Optional[str] = None
    payment_terms: Optional[str] = None
    min_order_amount: Optional[str] = None
    lead_time: Optional[str] = None


class SupplierUpdate(BaseModel):
    """Schema for updating a supplier."""
    name: Optional[str] = None
    category: Optional[str] = None
    contact_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[int] = None
    status: Optional[SupplierStatus] = None
    notes: Optional[str] = None
    material_categories: Optional[List[str]] = None
    logo: Optional[str] = None
    payment_terms: Optional[str] = None
    min_order_amount: Optional[str] = None
    lead_time: Optional[str] = None


class SupplierRating(BaseModel):
    """Supplier rating model."""
    id: int
    supplier_id: int
    rating: int
    category: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SupplierRatingCreate(BaseModel):
    """Schema for creating a supplier rating."""
    rating: int
    category: Optional[str] = None
    comments: Optional[str] = None


class SupplierHistory(BaseModel):
    """Supplier history model."""
    id: int
    supplier_id: int
    event_type: str
    description: str
    reference_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SupplierHistoryCreate(BaseModel):
    """Schema for creating a supplier history entry."""
    event_type: str
    description: str
    reference_id: Optional[str] = None


class SupplierSearchParams(BaseModel):
    """Search parameters for suppliers."""
    status: Optional[str] = None
    category: Optional[str] = None
    material_category: Optional[str] = None
    search: Optional[str] = None


class SupplierWithDetails(Supplier):
    """Supplier with detailed information."""
    materials: List[Material] = []
    ratings: List[SupplierRating] = []
    purchase_history: List[Dict[str, Any]] = []


class PurchaseHistorySummary(BaseModel):
    """Purchase history summary model."""
    supplier_id: int
    supplier_name: str
    total_purchases: int
    total_amount: float
    average_order_value: float
    most_purchased_items: List[Dict[str, Any]]
    purchase_trend: List[Dict[str, Any]]
    last_purchase_date: Optional[str] = None
    first_purchase_date: Optional[str] = None


# ===============================
# TOOL SCHEMAS
# ===============================

class Tool(BaseModel):
    """Tool model."""
    id: int
    name: str
    description: Optional[str] = None
    category: ToolCategory
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    specifications: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    image: Optional[str] = None
    last_maintenance: Optional[str] = None
    next_maintenance: Optional[str] = None
    maintenance_interval: Optional[int] = None
    supplier: Optional[str] = None
    supplier_id: Optional[int] = None
    checked_out_to: Optional[str] = None
    checked_out_date: Optional[str] = None
    due_date: Optional[str] = None
    days_until_maintenance: Optional[int] = None
    is_maintenance_due: Optional[bool] = None
    is_checked_out: Optional[bool] = None

    class Config:
        from_attributes = True


class ToolCreate(BaseModel):
    """Schema for creating a tool."""
    name: str
    description: Optional[str] = None
    category: ToolCategory
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    specifications: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    image: Optional[str] = None
    maintenance_interval: Optional[int] = None
    supplier: Optional[str] = None
    supplier_id: Optional[int] = None
    next_maintenance: Optional[str] = None


class ToolUpdate(BaseModel):
    """Schema for updating a tool."""
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ToolCategory] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[str] = None
    specifications: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    image: Optional[str] = None
    last_maintenance: Optional[str] = None
    next_maintenance: Optional[str] = None
    maintenance_interval: Optional[int] = None
    supplier: Optional[str] = None
    supplier_id: Optional[int] = None


class ToolMaintenance(BaseModel):
    """Tool maintenance model."""
    id: int
    tool_id: int
    tool_name: Optional[str] = None
    maintenance_type: str
    date: str
    performed_by: Optional[str] = None
    cost: Optional[float] = None
    internal_service: Optional[bool] = True
    details: Optional[str] = None
    parts: Optional[str] = None
    condition_before: Optional[str] = None
    condition_after: Optional[str] = None
    status: Optional[str] = None
    next_date: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ToolMaintenanceCreate(BaseModel):
    """Schema for creating a tool maintenance record."""
    tool_id: int
    tool_name: Optional[str] = None
    maintenance_type: str
    date: str
    performed_by: Optional[str] = None
    cost: Optional[float] = None
    internal_service: Optional[bool] = True
    details: Optional[str] = None
    parts: Optional[str] = None
    condition_before: Optional[str] = None
    condition_after: Optional[str] = None
    status: Optional[str] = None
    next_date: Optional[str] = None


class ToolMaintenanceUpdate(BaseModel):
    """Schema for updating a tool maintenance record."""
    maintenance_type: Optional[str] = None
    date: Optional[str] = None
    performed_by: Optional[str] = None
    cost: Optional[float] = None
    internal_service: Optional[bool] = None
    details: Optional[str] = None
    parts: Optional[str] = None
    condition_before: Optional[str] = None
    condition_after: Optional[str] = None
    status: Optional[str] = None
    next_date: Optional[str] = None


class ToolCheckout(BaseModel):
    """Tool checkout model."""
    id: int
    tool_id: int
    tool_name: Optional[str] = None
    checked_out_by: str
    checked_out_date: str
    due_date: str
    returned_date: Optional[str] = None
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    condition_before: Optional[str] = None
    condition_after: Optional[str] = None
    issue_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_overdue: Optional[bool] = None
    days_checked_out: Optional[int] = None

    class Config:
        from_attributes = True


class ToolCheckoutCreate(BaseModel):
    """Schema for creating a tool checkout."""
    tool_id: int
    tool_name: Optional[str] = None
    checked_out_by: str
    checked_out_date: str
    due_date: str
    project_id: Optional[int] = None
    project_name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    condition_before: Optional[str] = None


class ToolSearchParams(BaseModel):
    """Search parameters for tools."""
    category: Optional[str] = None
    status: Optional[str] = None
    location: Optional[str] = None
    search: Optional[str] = None


class MaintenanceScheduleItem(BaseModel):
    """Maintenance schedule item model."""
    tool_id: int
    tool_name: str
    maintenance_type: str
    scheduled_date: str
    category: ToolCategory
    status: str
    location: Optional[str] = None
    is_overdue: bool = False
    days_until_due: Optional[int] = None


class MaintenanceSchedule(BaseModel):
    """Maintenance schedule model."""
    schedule: List[MaintenanceScheduleItem]
    total_items: int
    overdue_items: int
    upcoming_items: int
    start_date: str
    end_date: str


# ===============================
# DOCUMENTATION SCHEMAS
# ===============================

class DocumentationResource(BaseModel):
    """Documentation resource model."""
    id: str
    title: str
    description: Optional[str] = None
    content: str
    category: Optional[str] = None
    type: Optional[str] = None
    skill_level: Optional[SkillLevel] = None
    tags: Optional[List[str]] = None
    related_resources: Optional[List[str]] = None
    author: Optional[str] = None
    last_updated: str
    contextual_help_keys: Optional[List[str]] = None
    videos: Optional[Dict[str, Any]] = None
    category_name: Optional[str] = None
    related_titles: Optional[List[str]] = None

    class Config:
        from_attributes = True


class DocumentationResourceCreate(BaseModel):
    """Schema for creating a documentation resource."""
    title: str
    description: Optional[str] = None
    content: str
    category: Optional[str] = None
    type: Optional[str] = None
    skill_level: Optional[SkillLevel] = None
    tags: Optional[List[str]] = None
    related_resources: Optional[List[str]] = None
    author: Optional[str] = None
    contextual_help_keys: Optional[List[str]] = None
    videos: Optional[Dict[str, Any]] = None


class DocumentationResourceUpdate(BaseModel):
    """Schema for updating a documentation resource."""
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    type: Optional[str] = None
    skill_level: Optional[SkillLevel] = None
    tags: Optional[List[str]] = None
    related_resources: Optional[List[str]] = None
    author: Optional[str] = None
    contextual_help_keys: Optional[List[str]] = None
    videos: Optional[Dict[str, Any]] = None


class DocumentationCategory(BaseModel):
    """Documentation category model."""
    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    resources: Optional[List[str]] = None

    class Config:
        from_attributes = True


class DocumentationCategoryCreate(BaseModel):
    """Schema for creating a documentation category."""
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    resources: Optional[List[str]] = None


class DocumentationCategoryUpdate(BaseModel):
    """Schema for updating a documentation category."""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    resources: Optional[List[str]] = None


class DocumentationSearchParams(BaseModel):
    """Search parameters for documentation resources."""
    category: Optional[str] = None
    type: Optional[str] = None
    skill_level: Optional[str] = None
    search: Optional[str] = None
    tags: Optional[List[str]] = None


class Refund(BaseModel):
    """Refund model."""
    id: int
    sale_id: int
    refund_date: datetime
    refund_amount: float
    reason: str
    status: str
    sale_order_number: Optional[str] = None
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True


class RefundCreate(BaseModel):
    """Schema for creating a refund."""
    sale_id: int
    refund_date: datetime
    refund_amount: float
    reason: str
    status: str


class RefundUpdate(BaseModel):
    """Schema for updating a refund."""
    refund_date: Optional[datetime] = None
    refund_amount: Optional[float] = None
    reason: Optional[str] = None
    status: Optional[str] = None