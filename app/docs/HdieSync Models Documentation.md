# Leathercraft ERP Models Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [Core Architecture](#core-architecture)
   - [Base Models and Mixins](#base-models-and-mixins)
   - [Entity Relationships](#entity-relationships)
   - [Encryption Support](#encryption-support)
3. [Model Groups](#model-groups)
   - [Customer Management](#customer-management)
   - [Material Management](#material-management)
   - [Project Management](#project-management)
   - [Sales and Order Management](#sales-and-order-management)
   - [Inventory Management](#inventory-management)
   - [Supply Chain](#supply-chain)
   - [Production Workflow](#production-workflow)
   - [Tool Management](#tool-management)
   - [Storage Management](#storage-management)
   - [E-commerce Integration](#e-commerce-integration)
   - [Documentation and Support](#documentation-and-support)
4. [Key Design Patterns](#key-design-patterns)
   - [Data Validation](#data-validation)
   - [Audit Trails](#audit-trails)
   - [Inheritance Patterns](#inheritance-patterns)
   - [Calculated Properties](#calculated-properties)
5. [Usage Examples](#usage-examples)
6. [Security Considerations](#security-considerations)

## Introduction

The Leathercraft ERP system is designed to manage all aspects of a leathercraft business, from inventory and customer management to production and sales. The database models form the core of this system, defining how data is structured, validated, and related.

This documentation covers all models in the system, their purpose, relationships, and key functionality. The models are implemented using SQLAlchemy ORM with support for encrypted storage via SQLCipher.

## Core Architecture

### Base Models and Mixins

All models in the system extend from common base classes and mixins that provide shared functionality:

#### AbstractBase

Located in `base.py`, this class provides common fields and functionality for all model entities:

```python
class AbstractBase(Base):
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    is_active = Column(Boolean, default=True)
```

Key features:
- Primary key ID and UUID for each record
- Active status flag for soft deletion
- Conversion methods to/from dictionaries

#### Mixins

Various mixins add specific functionality to models:

- **ValidationMixin**: Field validation logic
- **TimestampMixin**: Created/updated timestamps
- **AuditMixin**: Change history tracking
- **CostingMixin**: Cost and price tracking
- **ComplianceMixin**: GDPR compliance tracking
- **TrackingMixin**: Created/updated by user tracking

### Entity Relationships

The models follow the entity-relationship diagram with proper SQLAlchemy relationship definitions. Key relationship types include:

- **One-to-Many**: e.g., Customer → Sales, Project → Components
- **Many-to-Many**: e.g., Material ↔ Component, Customer ↔ PlatformIntegration
- **Inheritance**: e.g., Material → LeatherMaterial, HardwareMaterial, SuppliesMaterial

### Encryption Support

The system supports database encryption via SQLCipher:

- Sensitive fields are marked with `SENSITIVE_FIELDS` class attributes
- The database connection is configured to use SQLCipher when enabled
- Field-level encryption is available for specific sensitive data

## Model Groups

### Customer Management

#### Customer (`customer.py`)

Represents clients and customers of the leathercraft business.

**Key fields:**
- Basic info: name, email, phone
- Classification: status, tier, source
- GDPR-related: consent fields from ComplianceMixin

**Relationships:**
- One-to-many with Sales
- Many-to-many with PlatformIntegration
- One-to-many with CustomerCommunication

**Methods:**
- `record_interaction()`: Record customer touchpoints
- `update_tier()`: Change customer tier with audit trail

#### CustomerCommunication (`communication.py`)

Tracks all communication with customers across channels.

**Key fields:**
- channel (email, phone, in-person, etc.)
- content, subject
- direction (incoming/outgoing)
- follow-up flags and dates

**Methods:**
- `mark_as_sent()`: Record outbound communication
- `record_response()`: Track customer responses
- `schedule_follow_up()`: Flag for follow-up

### Material Management

#### Material (`material.py`)

Base class for all materials used in leatherworking.

**Key fields:**
- name, status, quantity, unit
- supplier details
- cost tracking (via CostingMixin)
- reorder point, storage location

**Relationships:**
- Many-to-many with Component (via ComponentMaterial)
- One-to-many with PickingListItem

**Methods:**
- Quantity validation with stock status updates
- Value calculation

#### Specialized Material Types

The system implements single-table inheritance for specialized material types:

- **LeatherMaterial**: Adds leather-specific attributes (thickness, tannage, etc.)
- **HardwareMaterial**: Adds hardware-specific attributes (finish, size, etc.)
- **SuppliesMaterial**: Adds attributes for other supplies (thread, dye, etc.)

### Project Management

#### Project (`project.py`)

Represents leatherworking projects, tracking workflow from concept to completion.

**Key fields:**
- name, description, type, status
- timeline: start_date, due_date, completed_date
- progress tracking

**Relationships:**
- Many-to-one with Sale
- Many-to-one with ProjectTemplate
- One-to-many with ProjectComponent
- One-to-many with PickingList
- One-to-many with TimelineTask

**Methods:**
- `calculate_progress()`: Update progress based on tasks
- `update_status()`: Change status with audit trail
- `is_overdue` property: Check if project is past due date

#### Component (`component.py`)

Defines reusable parts used in projects.

**Key fields:**
- name, description, component_type
- design details: path_data, position, attributes

**Relationships:**
- Many-to-one with Pattern
- One-to-many with ComponentMaterial
- Many-to-many with Project (via ProjectComponent)

**Methods:**
- `get_total_material_requirements()`: Calculate materials needed

#### Pattern (`pattern.py`)

Defines design templates for projects.

**Key fields:**
- name, description, skill_level
- file details: file_type, file_path
- estimated time and difficulty

**Relationships:**
- One-to-many with Component
- One-to-many with Product
- Many-to-many with Project (via ProjectTemplate)

### Sales and Order Management

#### Sale (`sales.py`)

Represents customer orders and sales transactions.

**Key fields:**
- Financial: subtotal, taxes, total_amount, etc.
- Status tracking: status, payment_status, fulfillment_status
- Dates: created_at, due_date, completed_date

**Relationships:**
- Many-to-one with Customer
- One-to-many with SaleItem
- One-to-many with Project
- One-to-one with Shipment
- One-to-one with Refund

**Methods:**
- `record_payment()`: Track payments received
- `update_status()`: Change status with audit trail
- `is_paid` property: Check if fully paid
- `profit_margin` property: Calculate profit percentage

#### SaleItem (`sales.py`)

Individual line items within a sale.

**Key fields:**
- quantity, price, tax
- name, type, SKU
- relationship to product, project, or pattern

**Methods:**
- `subtotal` property: Calculate line item subtotal
- `total` property: Calculate with tax included

#### Shipment (`shipment.py`)

Tracks outbound deliveries to customers.

**Key fields:**
- tracking_number, shipping_method
- shipping_cost, ship_date
- status

**Methods:**
- `mark_shipped()`: Record shipping details

#### Refund (`documentation.py`)

Handles customer refunds and returns.

**Key fields:**
- refund_amount, reason, status
- refund_date, payment_method
- transaction_id

**Methods:**
- `process_refund()`: Mark as processed
- `cancel_refund()`: Cancel pending refund

### Inventory Management

#### Inventory (`inventory.py`)

Unified view of all inventory items (materials, products, tools).

**Key fields:**
- item_type, item_id (polymorphic relationship)
- quantity, status
- storage_location

**Methods:**
- Quantity validation with status updates

#### Product (`inventory.py`)

Finished/sellable items available for sale.

**Key fields:**
- name, product_type, sku
- physical: materials, color, dimensions, weight
- pricing: cost_breakdown, selling_price
- inventory: quantity, reorder_point

**Relationships:**
- Many-to-one with Pattern
- One-to-many with SaleItem

**Methods:**
- `sync_inventory()`: Update inventory records
- `is_in_stock()`, `needs_reorder()`: Stock checks

### Supply Chain

#### Supplier (`supplier.py`)

Vendors and material sources.

**Key fields:**
- name, category, contact details
- rating, status
- payment_terms, lead_time

**Relationships:**
- One-to-many with Material
- One-to-many with Purchase
- One-to-many with Tool

**Methods:**
- `average_lead_time_days` property: Calculate from purchase history

#### Purchase (`purchase.py`)

Orders placed with suppliers.

**Key fields:**
- supplier details
- date, delivery_date
- status, total, payment_status

**Relationships:**
- Many-to-one with Supplier
- One-to-many with PurchaseItem

**Methods:**
- `update_status()`: Change status with audit trail
- `calculate_total()`: Sum from line items
- `is_overdue` property: Check if past delivery date

#### PurchaseItem (`purchase.py`)

Line items within supplier orders.

**Key fields:**
- name, quantity, price, total
- item_type, material_type, unit

**Methods:**
- Quantity and price validation

### Production Workflow

#### PickingList (`picking_list.py`)

List of materials to collect for a project.

**Key fields:**
- project_id, sale_id
- status, assigned_to
- completed_at

**Relationships:**
- Many-to-one with Project
- One-to-many with PickingListItem

**Methods:**
- `mark_complete()`: Finalize picking
- `add_item()`: Add materials to pick
- `progress_percentage` property: Calculate completion

#### TimelineTask (`timeline_task.py`)

Tasks within a project timeline.

**Key fields:**
- name, start_date, end_date
- progress, status
- dependencies, is_critical_path

**Methods:**
- `update_progress()`: Track completion
- `duration_days`, `is_overdue` properties: Timeline checks

#### RecurringProject (`recurring_project.py`)

Automation for regularly repeated projects.

**Key fields:**
- template_id, name, description
- is_active, next_occurrence, last_occurrence
- auto_generate, advance_notice_days

**Relationships:**
- Many-to-one with ProjectTemplate
- Many-to-one with RecurrencePattern
- One-to-many with GeneratedProject

**Methods:**
- `update_next_occurrence()`: Schedule next occurrence
- `generate_project()`: Create new project instance

#### RecurrencePattern (`recurring_project.py`)

Defines schedule patterns for recurring projects.

**Key fields:**
- frequency, interval
- start_date, end_date
- Various scheduling parameters (days_of_week, etc.)

**Methods:**
- `get_next_occurrence()`: Calculate next date
- `get_occurrences()`: Generate date sequence

### Tool Management

#### Tool (`tool.py`)

Equipment used in leatherworking.

**Key fields:**
- name, description, category
- product details: brand, model, serial_number
- maintenance tracking
- checkout status

**Relationships:**
- One-to-many with ToolMaintenance
- One-to-many with ToolCheckout

**Methods:**
- `schedule_maintenance()`: Plan maintenance
- `perform_maintenance()`: Record completed maintenance
- `checkout()`, `return_tool()`: Tool usage tracking
- `is_checked_out`, `maintenance_due` properties

#### ToolMaintenance (`tool.py`)

Maintenance records for tools.

**Key fields:**
- maintenance_type, date
- performed_by, cost
- condition_before, condition_after

**Methods:**
- `mark_completed()`: Finalize maintenance record

#### ToolCheckout (`tool.py`)

Tracking tool usage by staff/projects.

**Key fields:**
- checked_out_by, dates
- project details
- status, condition tracking

**Methods:**
- `extend_due_date()`: Adjust return timeline
- `is_overdue` property: Check if past due

### Storage Management

#### StorageLocation (`storage.py`)

Physical storage units (cabinets, shelves, etc.).

**Key fields:**
- name, type, section
- dimensions, capacity, utilized
- status

**Relationships:**
- One-to-many with StorageCell
- One-to-many with StorageAssignment

**Methods:**
- `add_item()`, `remove_item()`: Track capacity
- `available_capacity`, `utilization_percentage` properties

#### StorageCell (`storage.py`)

Individual storage spaces within locations.

**Key fields:**
- position, item details
- occupied flag

**Methods:**
- `assign_item()`: Place item in cell
- `clear()`: Remove item from cell
- `label` property: Human-readable position

#### StorageAssignment (`storage.py`)

Assignments of materials to storage locations.

**Key fields:**
- material details
- storage_id, position
- quantity, assignment metadata

**Methods:**
- `update_quantity()`: Change stored quantity

#### StorageMove (`storage.py`)

Movement of items between storage locations.

**Key fields:**
- material details
- from/to storage locations
- quantity, move details

**Methods:**
- `execute_move()`: Perform the move in storage assignments

### E-commerce Integration

#### PlatformIntegration (`platform_integration.py`)

Connection to external sales platforms (Etsy, Shopify, etc.).

**Key fields:**
- platform, shop_name
- API credentials (encrypted)
- status and sync tracking

**Relationships:**
- One-to-many with SyncEvent
- One-to-many with Sale
- Many-to-many with Customer

**Methods:**
- `is_token_expired()`: Check authentication status
- `record_sync()`: Log synchronization activity

#### SyncEvent (`platform_integration.py`)

Records of platform synchronization activities.

**Key fields:**
- event_type, status
- items_processed
- message (for errors/details)

### Documentation and Support

#### DocumentationResource (`documentation.py`)

Content for help/support documentation.

**Key fields:**
- title, description, content
- category, type, skill_level
- tags, related_resources

**Relationships:**
- Many-to-many with DocumentationCategory

**Methods:**
- `update_content()`: Version content changes
- `word_count`, `reading_time_minutes` properties

#### DocumentationCategory (`documentation.py`)

Categories for organizing documentation.

**Key fields:**
- name, description, icon
- parent_id (for hierarchical organization)

**Relationships:**
- Self-referential parent/child
- Many-to-many with DocumentationResource

**Methods:**
- `get_all_resources()`: Collect resources (including from subcategories)
- `resource_count`, `has_subcategories` properties

## Key Design Patterns

### Data Validation

All models include comprehensive validation through:

1. **SQLAlchemy validators** using the `@validates` decorator
2. **Custom validation methods** in the ValidationMixin
3. **Type checking** with proper SQLAlchemy column types

Example from the Material model:

```python
@validates('quantity')
def validate_quantity(self, key: str, quantity: float) -> float:
    if quantity < 0:
        raise ValueError("Quantity cannot be negative")
        
    # Update status based on quantity
    if quantity <= 0:
        self.status = InventoryStatus.OUT_OF_STOCK
    elif quantity <= self.reorder_point:
        self.status = InventoryStatus.LOW_STOCK
    else:
        self.status = InventoryStatus.IN_STOCK
        
    return quantity
```

### Audit Trails

Changes to critical data are tracked using:

1. **TimestampMixin** for creation/modification times
2. **AuditMixin** for detailed change history
3. **Status update methods** that record who made changes and why

Example from the Sales model:

```python
def update_status(self, new_status: SaleStatus, user: str, 
                notes: Optional[str] = None) -> None:
    old_status = self.status
    self.status = new_status
    
    # Record the change in history
    if hasattr(self, 'record_change'):
        self.record_change(user, {
            'field': 'status',
            'old_value': old_status.name if old_status else None,
            'new_value': new_status.name,
            'notes': notes,
            'timestamp': datetime.now().isoformat()
        })
```

### Inheritance Patterns

The system uses SQLAlchemy's inheritance patterns in two key ways:

1. **Abstract Base Classes** (`AbstractBase` and mixins) that don't create tables
2. **Single-Table Inheritance** for specialized material types

Example of single-table inheritance:

```python
class Material(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    __tablename__ = 'materials'
    
    # Discriminator column for inheritance
    material_type = Column(String(50), nullable=False)
    
    # Inheritance configuration
    __mapper_args__ = {
        'polymorphic_on': material_type,
        'polymorphic_identity': 'material'
    }

class LeatherMaterial(Material):
    __mapper_args__ = {
        'polymorphic_identity': 'leather'
    }
    
    # Leather-specific attributes
    leather_type = Column(Enum(LeatherType))
    thickness = Column(Float)
    # ...
```

### Calculated Properties

Models use SQLAlchemy's hybrid properties for derived values:

```python
@hybrid_property
def is_overdue(self) -> bool:
    if not self.due_date:
        return False
        
    return datetime.now() > self.due_date and self.status != ProjectStatus.COMPLETED
```

These properties can be used both in Python and in database queries.

## Usage Examples

### Creating a Customer

```python
from app.db.models import Customer, CustomerStatus, CustomerTier, CustomerSource
from app.db.config import db_session

with db_session() as session:
    customer = Customer(
        name="John Smith",
        email="john@example.com",
        phone="555-1234",
        status=CustomerStatus.ACTIVE,
        tier=CustomerTier.STANDARD,
        source=CustomerSource.WEBSITE,
        notes="Met at craft fair"
    )
    session.add(customer)
    session.commit()
```

### Recording a Sale

```python
from app.db.models import Sale, SaleStatus, PaymentStatus, SaleItem
from datetime import datetime, timedelta
from app.db.config import db_session

with db_session() as session:
    # Create sale
    sale = Sale(
        customer_id=customer.id,
        due_date=datetime.now() + timedelta(days=14),
        subtotal=150.00,
        taxes=12.00,
        shipping=10.00,
        total_amount=172.00,
        status=SaleStatus.CONFIRMED,
        payment_status=PaymentStatus.DEPOSIT_PAID,
        deposit_amount=86.00,
        balance_due=86.00,
        channel="WEBSITE"
    )
    session.add(sale)
    
    # Add items to sale
    item = SaleItem(
        sale=sale,
        quantity=1,
        price=150.00,
        tax=12.00,
        name="Custom Leather Wallet",
        type="CUSTOM"
    )
    session.add(item)
    
    session.commit()
    
    # Record payment
    sale.record_payment(86.00, "CREDIT_CARD", "admin", "Final payment")
```

### Creating a Project from a Sale

```python
from app.db.models import Project, ProjectStatus, ProjectType, TimelineTask
from datetime import datetime, timedelta
from app.db.config import db_session

with db_session() as session:
    project = Project(
        name="Custom Wallet - John Smith",
        description="Black vegetable-tanned leather wallet with red stitching",
        type=ProjectType.WALLET,
        status=ProjectStatus.PLANNING,
        start_date=datetime.now(),
        due_date=datetime.now() + timedelta(days=10),
        sales_id=sale.id,
        customer="John Smith"
    )
    session.add(project)
    session.commit()
    
    # Add timeline tasks
    tasks = [
        TimelineTask(
            project=project,
            name="Design and pattern",
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=2),
            status="PENDING"
        ),
        TimelineTask(
            project=project,
            name="Material preparation",
            start_date=datetime.now() + timedelta(days=2),
            end_date=datetime.now() + timedelta(days=3),
            status="PENDING",
            dependencies=[1]  # Depends on first task
        ),
        # More tasks...
    ]
    session.add_all(tasks)
    session.commit()
    
    # Create a picking list
    picking_list = PickingList(
        project=project,
        status=PickingListStatus.PENDING
    )
    session.add(picking_list)
    session.commit()
```

### Managing Inventory

```python
from app.db.models import LeatherMaterial, MaterialType, MaterialQualityGrade
from app.db.models import InventoryStatus, MeasurementUnit
from app.db.config import db_session

with db_session() as session:
    # Create material
    material = LeatherMaterial(
        name="Black Vegetable-Tanned Leather",
        material_type="leather",
        status=InventoryStatus.IN_STOCK,
        quantity=10.5,
        unit=MeasurementUnit.SQUARE_FOOT,
        quality=MaterialQualityGrade.PREMIUM,
        reorder_point=5.0,
        supplier="Premium Leathers Inc.",
        cost_price=8.50,
        retail_price=16.99,
        leather_type=LeatherType.VEGETABLE_TANNED,
        thickness=2.5,  # mm
        color="Black"
    )
    session.add(material)
    session.commit()
    
    # Update inventory
    material.quantity -= 2.5  # This triggers quantity validation and status update
    session.commit()
```

## Security Considerations

The Leathercraft ERP models include several security features:

### Encryption

- The system supports SQLCipher database encryption
- Sensitive fields are marked for special handling
- API credentials are stored securely

### GDPR Compliance

- Customer data includes consent tracking
- The ComplianceMixin tracks consent versions and dates
- Data can be exported in structured format for portability

### Access Control

- Relationships are designed to support row-level security
- The AuditMixin tracks all changes with user attribution
- Sensitive operations include validation checks

### Data Integrity

- Comprehensive validation on all models
- Referential integrity through proper foreign keys
- Transaction support for complex operations