# HideSync Repository Layer
## Comprehensive Documentation

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Architecture Overview](#2-architecture-overview)
3. [Base Repository](#3-base-repository)
4. [Repository Factory](#4-repository-factory)
5. [Entity Repositories](#5-entity-repositories)
   - [Customer Management](#51-customer-management)
   - [Inventory Management](#52-inventory-management)
   - [Project Management](#53-project-management)
   - [Sales and Orders](#54-sales-and-orders)
   - [Storage Management](#55-storage-management)
   - [Tool Management](#56-tool-management)
   - [Documentation](#57-documentation)
   - [Platform Integration](#58-platform-integration)
6. [Security and Encryption](#6-security-and-encryption)
7. [Transaction Management](#7-transaction-management)
8. [Integration with Services](#8-integration-with-services)
9. [Testing Strategy](#9-testing-strategy)
10. [Performance Considerations](#10-performance-considerations)
11. [Implementation Best Practices](#11-implementation-best-practices)
12. [Examples](#12-examples)
13. [Troubleshooting](#13-troubleshooting)
14. [Extending the Repository Layer](#14-extending-the-repository-layer)

---

## 1. Introduction

The repository layer in HideSync implements the Repository Pattern, a design pattern that separates the logic that retrieves data from underlying storage from the business logic that acts on the data. This documentation covers the implementation details, usage patterns, and best practices for working with the repository layer.

### 1.1 Purpose and Benefits

The repository layer provides several benefits:

- Abstracts data persistence details away from business logic
- Provides a consistent interface for data access
- Centralizes data access logic in one place
- Enables unit testing through dependency injection
- Supports cross-cutting concerns like encryption, caching, and logging

### 1.2 Key Design Principles

- **Separation of Concerns**: Each repository focuses on one entity or aggregate
- **Type Safety**: Generic typing ensures compile-time type checking
- **Single Responsibility**: Repositories handle only data access, not business rules
- **Encapsulation**: Implementation details are hidden behind well-defined interfaces
- **Consistency**: Common operations are implemented in a base repository

---

## 2. Architecture Overview

The repository layer architecture consists of the following key components:

### 2.1 Component Diagram

```
┌──────────────────┐     ┌─────────────────────┐     ┌──────────────────────┐
│                  │     │                     │     │                      │
│  Service Layer   │────▶│  Repository Layer   │────▶│  Database/ORM Layer  │
│                  │     │                     │     │                      │
└──────────────────┘     └─────────────────────┘     └──────────────────────┘
                                   │
                                   │
                         ┌─────────┴─────────┐
                         ▼                   ▼
                ┌──────────────────┐ ┌──────────────────┐
                │                  │ │                  │
                │  BaseRepository  │ │ RepositoryFactory│
                │                  │ │                  │
                └──────────────────┘ └──────────────────┘
                         │                   │
                         │                   │
                ┌────────┴─────────┐         │
                ▼                  ▼         ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│                   │ │                   │ │                   │
│ Entity Repository │ │ Entity Repository │ │ Entity Repository │
│ (e.g. Customer)   │ │ (e.g. Material)   │ │ (e.g. Project)    │
│                   │ │                   │ │                   │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

### 2.2 Key Components

- **BaseRepository**: Generic implementation of common CRUD operations
- **Entity Repositories**: Specific implementations for each entity type 
- **Repository Factory**: Creates and configures repository instances
- **Dependency Injection**: Mechanism to provide repositories to services

### 2.3 Package Structure

```
app/
  └── repositories/
      ├── base_repository.py
      ├── repository_factory.py
      ├── customer_repository.py
      ├── material_repository.py
      ├── project_repository.py
      ├── sale_repository.py
      ├── inventory_repository.py
      ├── product_repository.py
      ├── supplier_repository.py
      ├── storage_repository.py
      ├── pattern_repository.py
      ├── tool_repository.py
      ├── platform_integration_repository.py
      ├── component_repository.py
      ├── documentation_repository.py
      ├── picking_list_repository.py
      ├── purchase_repository.py
      ├── recurring_project_repository.py
      ├── shipment_repository.py
      └── timeline_task_repository.py
```

---

## 3. Base Repository

The `BaseRepository` class provides a generic implementation of common data access operations that all entity repositories inherit from.

### 3.1 Key Features

- Generic typing for type safety
- Standard CRUD operations (create, read, update, delete)
- Pagination and filtering support
- Search functionality across multiple fields
- Support for field-level encryption/decryption
- Transaction management integration

### 3.2 Implementation Details

```python
# Key methods in BaseRepository
class BaseRepository(Generic[T]):
    def __init__(self, session: Session, encryption_service=None):
        self.session = session
        self.encryption_service = encryption_service
        # Model attribute to be set by derived classes
    
    def get_by_id(self, id: int) -> Optional[T]:
        """Retrieve entity by primary key ID"""
        
    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[T]:
        """List entities with pagination and filtering"""
        
    def create(self, data: Dict[str, Any]) -> T:
        """Create a new entity"""
        
    def update(self, id: int, data: Dict[str, Any]) -> Optional[T]:
        """Update an existing entity"""
        
    def delete(self, id: int) -> bool:
        """Delete an entity by ID"""
        
    def search(self, query: str, fields: List[str], skip: int = 0, limit: int = 100) -> List[T]:
        """Search for entities across specified fields"""
        
    def count(self, **filters) -> int:
        """Count entities matching the given filters"""
```

### 3.3 Usage Example

```python
# Basic usage of BaseRepository through a derived class
customer_repo = CustomerRepository(session)

# Get by ID
customer = customer_repo.get_by_id(123)

# List with pagination and filtering
active_customers = customer_repo.list(
    skip=0, 
    limit=20, 
    status=CustomerStatus.ACTIVE
)

# Create
new_customer = customer_repo.create({
    "name": "John Doe",
    "email": "john@example.com",
    "status": CustomerStatus.ACTIVE
})

# Update
updated = customer_repo.update(123, {
    "name": "John Smith"
})

# Delete
success = customer_repo.delete(123)

# Search
search_results = customer_repo.search(
    query="john", 
    fields=["name", "email"]
)
```

---

## 4. Repository Factory

The `RepositoryFactory` provides a centralized way to create repository instances with consistent configuration.

### 4.1 Purpose

- Ensures consistent configuration of all repositories
- Centralizes dependency injection
- Simplifies repository creation in services
- Facilitates consistent encryption service assignment

### 4.2 Implementation

```python
class RepositoryFactory:
    def __init__(self, session: Session, encryption_service=None):
        self.session = session
        self.encryption_service = encryption_service
    
    # Customer repositories
    def create_customer_repository(self) -> CustomerRepository:
        return CustomerRepository(self.session, self.encryption_service)
    
    # Material repositories
    def create_material_repository(self) -> MaterialRepository:
        return MaterialRepository(self.session, self.encryption_service)
    
    # Project repositories
    def create_project_repository(self) -> ProjectRepository:
        return ProjectRepository(self.session, self.encryption_service)
    
    # ... and so on for all repositories
```

### 4.3 Usage Example

```python
# Create a repository factory
factory = RepositoryFactory(session, encryption_service)

# Create repositories
customer_repo = factory.create_customer_repository()
material_repo = factory.create_material_repository()
```

---

## 5. Entity Repositories

### 5.1 Customer Management

#### 5.1.1 CustomerRepository

The `CustomerRepository` provides data access for customer entities in the system.

**Key Methods:**
- `find_by_email(email: str) -> Optional[Customer]`: Find a customer by email
- `find_active_customers(skip: int = 0, limit: int = 100) -> List[Customer]`: Get active customers
- `find_by_tier(tier, skip: int = 0, limit: int = 100) -> List[Customer]`: Find customers by tier
- `search_customers(query: str, skip: int = 0, limit: int = 100) -> List[Customer]`: Search customers
- `get_customers_with_recent_purchases(days: int = 30, limit: int = 10) -> List[Customer]`: Get customers with recent purchases
- `get_customers_by_source(source, skip: int = 0, limit: int = 100) -> List[Customer]`: Get customers by source

**Example:**
```python
# Find customers by tier
vip_customers = customer_repo.find_by_tier(CustomerTier.VIP)

# Get active customers with pagination
active_customers = customer_repo.find_active_customers(skip=0, limit=20)
```

### 5.2 Inventory Management

#### 5.2.1 MaterialRepository

The `MaterialRepository` handles access to material data, including leather, hardware, and supplies.

**Key Methods:**
- `get_materials_by_type(material_type: MaterialType, skip: int = 0, limit: int = 100) -> List[Material]`: Get materials by type
- `get_materials_by_status(status: InventoryStatus, skip: int = 0, limit: int = 100) -> List[Material]`: Get materials by status
- `get_materials_by_supplier(supplier_id: int, skip: int = 0, limit: int = 100) -> List[Material]`: Get materials from a specific supplier
- `get_low_stock_materials(skip: int = 0, limit: int = 100) -> List[Material]`: Get materials that are low in stock
- `update_inventory_quantity(material_id: int, quantity_change: float) -> Optional[Material]`: Update material quantity
- `search_materials(query: str, skip: int = 0, limit: int = 100) -> List[Material]`: Search for materials
- Leather/hardware-specific methods for specialized material types

**Example:**
```python
# Get low stock materials
low_stock = material_repo.get_low_stock_materials()

# Update material quantity (e.g., after usage in a project)
updated_material = material_repo.update_inventory_quantity(
    material_id=123, 
    quantity_change=-2.5  # Using 2.5 units of material
)
```

#### 5.2.2 InventoryRepository

The `InventoryRepository` manages inventory records for all types of items.

**Key Methods:**
- `get_inventory_by_item_id(item_type: str, item_id: int) -> Optional[Inventory]`: Get inventory for a specific item
- `get_inventory_by_status(status: InventoryStatus, skip: int = 0, limit: int = 100) -> List[Inventory]`: Get inventory by status
- `get_inventory_by_location(location: str, skip: int = 0, limit: int = 100) -> List[Inventory]`: Get inventory at a specific location
- `get_low_stock_inventory(skip: int = 0, limit: int = 100) -> List[Inventory]`: Get inventory items low in stock
- `update_inventory_quantity(inventory_id: int, quantity_change: float) -> Optional[Inventory]`: Update inventory quantity
- `update_inventory_location(inventory_id: int, location: str) -> Optional[Inventory]`: Update storage location
- `get_inventory_statistics() -> Dict[str, Any]`: Get inventory statistics

**Example:**
```python
# Get inventory statistics
stats = inventory_repo.get_inventory_statistics()

# Move inventory to a new location
inventory_repo.update_inventory_location(
    inventory_id=456, 
    location="Shelf B4"
)
```

#### 5.2.3 ProductRepository

The `ProductRepository` handles finished products ready for sale.

**Key Methods:**
- `get_products_by_status(status: InventoryStatus, skip: int = 0, limit: int = 100) -> List[Product]`: Get products by status
- `get_products_by_pattern(pattern_id: int, skip: int = 0, limit: int = 100) -> List[Product]`: Get products based on a pattern
- `get_products_by_price_range(min_price: float, max_price: float, skip: int = 0, limit: int = 100) -> List[Product]`: Get products in price range
- `get_best_selling_products(limit: int = 10) -> List[Product]`: Get best-selling products
- `get_products_low_in_stock(skip: int = 0, limit: int = 100) -> List[Product]`: Get products low in stock
- `update_product_inventory(product_id: int, quantity_change: int) -> Optional[Product]`: Update product inventory
- `update_product_pricing(product_id: int, total_cost: Optional[float] = None, selling_price: Optional[float] = None) -> Optional[Product]`: Update product pricing

**Example:**
```python
# Get best selling products
best_sellers = product_repo.get_best_selling_products(limit=5)

# Update product pricing
product_repo.update_product_pricing(
    product_id=789,
    selling_price=129.99
)
```

#### 5.2.4 SupplierRepository

The `SupplierRepository` manages supplier information and relationships.

**Key Methods:**
- `get_suppliers_by_status(status: SupplierStatus, skip: int = 0, limit: int = 100) -> List[Supplier]`: Get suppliers by status
- `get_suppliers_by_category(category: str, skip: int = 0, limit: int = 100) -> List[Supplier]`: Get suppliers by category
- `get_preferred_suppliers(skip: int = 0, limit: int = 100) -> List[Supplier]`: Get preferred suppliers
- `get_active_suppliers(skip: int = 0, limit: int = 100) -> List[Supplier]`: Get active suppliers
- `get_suppliers_by_material_category(material_category: str, skip: int = 0, limit: int = 100) -> List[Supplier]`: Get suppliers for a material category
- `get_suppliers_by_rating(min_rating: int, skip: int = 0, limit: int = 100) -> List[Supplier]`: Get suppliers with minimum rating
- `update_supplier_status(supplier_id: int, status: SupplierStatus) -> Optional[Supplier]`: Update supplier status
- `update_supplier_rating(supplier_id: int, rating: int) -> Optional[Supplier]`: Update supplier rating

**Example:**
```python
# Get preferred suppliers
preferred = supplier_repo.get_preferred_suppliers()

# Update supplier rating after an order
supplier_repo.update_supplier_rating(
    supplier_id=42,
    rating=5  # 5-star rating
)
```

### 5.3 Project Management

#### 5.3.1 ProjectRepository

The `ProjectRepository` handles customer projects and work tracking.

**Key Methods:**
- `get_projects_by_status(status: ProjectStatus, skip: int = 0, limit: int = 100) -> List[Project]`: Get projects by status
- `get_projects_by_customer(customer_id: int, skip: int = 0, limit: int = 100) -> List[Project]`: Get projects for a customer
- `get_projects_by_type(project_type: ProjectType, skip: int = 0, limit: int = 100) -> List[Project]`: Get projects by type
- `get_projects_in_date_range(start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> List[Project]`: Get projects due in date range
- `get_overdue_projects(skip: int = 0, limit: int = 100) -> List[Project]`: Get overdue projects
- `get_upcoming_projects(days: int = 7, skip: int = 0, limit: int = 100) -> List[Project]`: Get upcoming projects
- `update_project_status(project_id: int, status: ProjectStatus) -> Optional[Project]`: Update project status
- `update_project_progress(project_id: int, progress: float) -> Optional[Project]`: Update project progress
- `get_project_with_components(project_id: int) -> Optional[Dict[str, Any]]`: Get project with components

**Example:**
```python
# Get overdue projects
overdue = project_repo.get_overdue_projects()

# Update project progress
project_repo.update_project_progress(
    project_id=101,
    progress=75.0  # 75% complete
)
```

#### 5.3.2 ComponentRepository

The `ComponentRepository` manages project components and their material requirements.

**Key Methods:**
- `get_components_by_pattern(pattern_id: int, skip: int = 0, limit: int = 100) -> List[Component]`: Get components for a pattern
- `get_components_by_type(component_type: ComponentType, skip: int = 0, limit: int = 100) -> List[Component]`: Get components by type
- `get_components_by_author(author_name: str, skip: int = 0, limit: int = 100) -> List[Component]`: Get components by author
- `get_optional_components(pattern_id: int, skip: int = 0, limit: int = 100) -> List[Component]`: Get optional components
- `search_components(query: str, skip: int = 0, limit: int = 100) -> List[Component]`: Search for components
- `get_component_with_materials(component_id: int) -> Optional[Dict[str, Any]]`: Get component with materials
- `update_component_position(component_id: int, position: Dict[str, Any], rotation: int) -> Optional[Component]`: Update component position

**Example:**
```python
# Get component with required materials
component_data = component_repo.get_component_with_materials(component_id=456)

# Get optional components for a pattern
optional_components = component_repo.get_optional_components(pattern_id=789)
```

#### 5.3.3 ComponentMaterialRepository

The `ComponentMaterialRepository` manages relationships between components and materials.

**Key Methods:**
- `get_materials_by_component(component_id: int) -> List[ComponentMaterial]`: Get materials for a component
- `get_components_using_material(material_id: int) -> List[ComponentMaterial]`: Get components using a material
- `get_required_materials() -> List[ComponentMaterial]`: Get all required material relationships
- `update_material_quantity(id: int, quantity: float) -> Optional[ComponentMaterial]`: Update required quantity
- `update_alternative_materials(id: int, alternative_material_ids: List[int]) -> Optional[ComponentMaterial]`: Update alternative materials

**Example:**
```python
# Get materials needed for a component
materials = component_material_repo.get_materials_by_component(component_id=456)

# Find all components using a specific material
components = component_material_repo.get_components_using_material(material_id=123)
```

#### 5.3.4 TimelineTaskRepository

The `TimelineTaskRepository` manages project timeline tasks and dependencies.

**Key Methods:**
- `get_tasks_by_project(project_id: str) -> List[TimelineTask]`: Get tasks for a project
- `get_tasks_by_status(status: str, skip: int = 0, limit: int = 100) -> List[TimelineTask]`: Get tasks by status
- `get_critical_path_tasks(project_id: str) -> List[TimelineTask]`: Get critical path tasks
- `get_tasks_in_date_range(start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> List[TimelineTask]`: Get tasks in date range
- `get_upcoming_tasks(days: int = 7, skip: int = 0, limit: int = 100) -> List[TimelineTask]`: Get upcoming tasks
- `get_overdue_tasks(skip: int = 0, limit: int = 100) -> List[TimelineTask]`: Get overdue tasks
- `update_task_progress(task_id: str, progress: int) -> Optional[TimelineTask]`: Update task progress
- `update_task_dates(task_id: str, start_date: datetime, end_date: datetime) -> Optional[TimelineTask]`: Update task dates
- `update_task_dependencies(task_id: str, dependencies: List[str]) -> Optional[TimelineTask]`: Update task dependencies
- `set_critical_path(task_id: str, is_critical_path: bool) -> Optional[TimelineTask]`: Set critical path status
- `get_project_timeline_summary(project_id: str) -> Dict[str, Any]`: Get project timeline summary

**Example:**
```python
# Get project timeline summary
timeline_summary = timeline_task_repo.get_project_timeline_summary(project_id="abc123")

# Update task progress
timeline_task_repo.update_task_progress(
    task_id="task456",
    progress=50  # 50% complete
)
```

#### 5.3.5 RecurringProjectRepository

The `RecurringProjectRepository` manages projects that run on a recurring schedule.

**Key Methods:**
- `get_active_recurring_projects(skip: int = 0, limit: int = 100) -> List[RecurringProject]`: Get active recurring projects
- `get_recurring_projects_by_template(template_id: str, skip: int = 0, limit: int = 100) -> List[RecurringProject]`: Get recurring projects by template
- `get_recurring_projects_by_client(client_id: str, skip: int = 0, limit: int = 100) -> List[RecurringProject]`: Get recurring projects by client
- `get_recurring_projects_due_for_generation() -> List[RecurringProject]`: Get projects due for generation
- `update_recurring_project_status(project_id: str, is_active: bool) -> Optional[RecurringProject]`: Update active status
- `update_next_occurrence(project_id: str, next_occurrence: str) -> Optional[RecurringProject]`: Update next occurrence date
- `get_recurring_project_with_pattern(project_id: str) -> Optional[Dict[str, Any]]`: Get recurring project with pattern

**Example:**
```python
# Get projects due for generation
due_projects = recurring_project_repo.get_recurring_projects_due_for_generation()

# Update project status
recurring_project_repo.update_recurring_project_status(
    project_id="rec123",
    is_active=False  # Deactivate the recurring project
)
```

#### 5.3.6 RecurrencePatternRepository

The `RecurrencePatternRepository` manages recurrence patterns for scheduled projects.

**Key Methods:**
- `get_patterns_by_frequency(frequency: str, skip: int = 0, limit: int = 100) -> List[RecurrencePattern]`: Get patterns by frequency
- `get_active_patterns(skip: int = 0, limit: int = 100) -> List[RecurrencePattern]`: Get active patterns
- `calculate_next_occurrence(pattern_id: str, from_date: Optional[datetime] = None) -> Optional[datetime]`: Calculate next occurrence date

**Example:**
```python
# Calculate next occurrence date for a pattern
next_date = recurrence_pattern_repo.calculate_next_occurrence(
    pattern_id="pattern789",
    from_date=datetime.now()
)
```

#### 5.3.7 GeneratedProjectRepository

The `GeneratedProjectRepository` manages projects generated from recurring templates.

**Key Methods:**
- `get_generated_projects_by_recurring_project(recurring_project_id: str) -> List[GeneratedProject]`: Get projects for a recurring project
- `get_generated_projects_by_status(status: str, skip: int = 0, limit: int = 100) -> List[GeneratedProject]`: Get projects by status
- `get_upcoming_generated_projects(days: int = 30, skip: int = 0, limit: int = 100) -> List[GeneratedProject]`: Get upcoming generated projects
- `update_generated_project_status(project_id: str, status: str) -> Optional[GeneratedProject]`: Update project status

**Example:**
```python
# Get upcoming generated projects
upcoming = generated_project_repo.get_upcoming_generated_projects(days=14)

# Update project status
generated_project_repo.update_generated_project_status(
    project_id="gen456",
    status="scheduled"
)
```

### 5.4 Sales and Orders

#### 5.4.1 SaleRepository

The `SaleRepository` manages customer sales and orders.

**Key Methods:**
- `get_sales_by_customer(customer_id: int, skip: int = 0, limit: int = 100) -> List[Sale]`: Get sales for a customer
- `get_sales_by_status(status: SaleStatus, skip: int = 0, limit: int = 100) -> List[Sale]`: Get sales by status
- `get_sales_by_payment_status(payment_status: PaymentStatus, skip: int = 0, limit: int = 100) -> List[Sale]`: Get sales by payment status
- `get_sales_in_date_range(start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> List[Sale]`: Get sales in date range
- `get_recent_sales(days: int = 30, skip: int = 0, limit: int = 100) -> List[Sale]`: Get recent sales
- `get_pending_shipments(skip: int = 0, limit: int = 100) -> List[Sale]`: Get sales ready for shipping
- `get_overdue_payments(skip: int = 0, limit: int = 100) -> List[Sale]`: Get sales with overdue payments
- `update_sale_status(sale_id: int, status: SaleStatus) -> Optional[Sale]`: Update sale status
- `update_payment_status(sale_id: int, payment_status: PaymentStatus) -> Optional[Sale]`: Update payment status
- `get_sale_with_items(sale_id: int) -> Optional[Dict[str, Any]]`: Get sale with items
- `get_revenue_by_period(period: str = 'month', start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict[str, Any]]`: Get revenue data

**Example:**
```python
# Get sales with overdue payments
overdue = sale_repo.get_overdue_payments()

# Update sale status
sale_repo.update_sale_status(
    sale_id=101,
    status=SaleStatus.IN_PRODUCTION
)
```

#### 5.4.2 RefundRepository

The `RefundRepository` manages customer refunds and returns.

**Key Methods:**
- `get_refunds_by_sale(sale_id: int) -> List[Refund]`: Get refunds for a sale
- `get_refunds_by_status(status: str, skip: int = 0, limit: int = 100) -> List[Refund]`: Get refunds by status
- `get_refunds_by_date_range(start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> List[Refund]`: Get refunds in date range
- `get_refund_statistics() -> Dict[str, Any]`: Get refund statistics
- `create_refund(sale_id: int, refund_amount: float, reason: str) -> Refund`: Create a new refund
- `update_refund_status(refund_id: int, status: str) -> Optional[Refund]`: Update refund status

**Example:**
```python
# Create a new refund
refund = refund_repo.create_refund(
    sale_id=123,
    refund_amount=49.99,
    reason="Customer not satisfied with product"
)

# Get refund statistics
stats = refund_repo.get_refund_statistics()
```

#### 5.4.3 ShipmentRepository

The `ShipmentRepository` manages order shipments and tracking.

**Key Methods:**
- `get_shipments_by_sale(sale_id: int) -> List[Shipment]`: Get shipments for a sale
- `get_shipments_by_status(status: str, skip: int = 0, limit: int = 100) -> List[Shipment]`: Get shipments by status
- `get_shipments_by_tracking_number(tracking_number: str) -> Optional[Shipment]`: Get shipment by tracking number
- `get_shipments_by_date_range(start_date: datetime, end_date: datetime, skip: int = 0, limit: int = 100) -> List[Shipment]`: Get shipments in date range
- `get_shipments_by_shipping_method(shipping_method: str, skip: int = 0, limit: int = 100) -> List[Shipment]`: Get shipments by method
- `get_recent_shipments(days: int = 30, skip: int = 0, limit: int = 100) -> List[Shipment]`: Get recent shipments
- `update_shipment_status(shipment_id: int, status: str) -> Optional[Shipment]`: Update shipment status
- `update_tracking_information(shipment_id: int, tracking_number: str, shipping_method: str) -> Optional[Shipment]`: Update tracking info
- `get_shipment_statistics() -> Dict[str, Any]`: Get shipment statistics

**Example:**
```python
# Update tracking information
shipment_repo.update_tracking_information(
    shipment_id=789,
    tracking_number="1Z999AA10123456784",
    shipping_method="UPS Ground"
)

# Get shipment by tracking number
shipment = shipment_repo.get_shipments_by_tracking_number("1Z999AA10123456784")
```

### 5.5 Storage Management

#### 5.5.1 StorageLocationRepository

The `StorageLocationRepository` manages storage locations and organization.

**Key Methods:**
- `get_storage_by_type(storage_type: StorageLocationType, skip: int = 0, limit: int = 100) -> List[StorageLocation]`: Get storage by type
- `get_storage_by_section(section: str, skip: int = 0, limit: int = 100) -> List[StorageLocation]`: Get storage by section
- `get_available_storage(skip: int = 0, limit: int = 100) -> List[StorageLocation]`: Get storage with available capacity
- `get_child_locations(parent_id: str, skip: int = 0, limit: int = 100) -> List[StorageLocation]`: Get child locations
- `update_storage_utilization(storage_id: str, change: int) -> Optional[StorageLocation]`: Update storage utilization
- `search_storage_locations(query: str, skip: int = 0, limit: int = 100) -> List[StorageLocation]`: Search storage locations
- `get_storage_utilization_summary() -> Dict[str, Any]`: Get storage utilization statistics

**Example:**
```python
# Get available storage locations
available = storage_location_repo.get_available_storage()

# Update storage utilization after adding items
storage_location_repo.update_storage_utilization(
    storage_id="loc123",
    change=5  # Added 5 units of capacity utilization
)
```

#### 5.5.2 StorageCellRepository

The `StorageCellRepository` manages individual storage cells within locations.

**Key Methods:**
- `get_cells_by_storage(storage_id: str) -> List[StorageCell]`: Get cells for a storage location
- `get_occupied_cells(storage_id: str) -> List[StorageCell]`: Get occupied cells
- `get_empty_cells(storage_id: str) -> List[StorageCell]`: Get empty cells
- `assign_cell(storage_id: str, position: Dict[str, Any], item_id: int, item_type: str) -> Optional[StorageCell]`: Assign item to cell
- `clear_cell(storage_id: str, position: Dict[str, Any]) -> Optional[StorageCell]`: Clear a cell

**Example:**
```python
# Get empty cells in a storage location
empty_cells = storage_cell_repo.get_empty_cells(storage_id="shelf-a1")

# Assign a material to a cell
storage_cell_repo.assign_cell(
    storage_id="shelf-a1",
    position={"row": 2, "column": 3},
    item_id=456,
    item_type="material"
)
```

#### 5.5.3 StorageAssignmentRepository

The `StorageAssignmentRepository` manages material storage assignments.

**Key Methods:**
- `get_assignments_by_material(material_id: int, material_type: str) -> List[StorageAssignment]`: Get storage for a material
- `get_assignments_by_storage(storage_id: str) -> List[StorageAssignment]`: Get assigned materials in storage
- `create_assignment(material_id: int, material_type: str, storage_id: str, position: Dict[str, Any], quantity: float, assigned_by: str) -> StorageAssignment`: Create assignment
- `update_assignment_quantity(assignment_id: str, quantity: float) -> Optional[StorageAssignment]`: Update quantity

**Example:**
```python
# Get storage assignments for a material
assignments = storage_assignment_repo.get_assignments_by_material(
    material_id=789,
    material_type="LEATHER"
)

# Create new storage assignment
storage_assignment_repo.create_assignment(
    material_id=789,
    material_type="LEATHER",
    storage_id="cab-b2",
    position={"shelf": 3, "bin": 5},
    quantity=10.5,
    assigned_by="john.smith"
)
```

#### 5.5.4 StorageMoveRepository

The `StorageMoveRepository` tracks material movements between storage locations.

**Key Methods:**
- `get_moves_by_material(material_id: int, material_type: str, skip: int = 0, limit: int = 100) -> List[StorageMove]`: Get moves for a material
- `get_moves_by_storage(storage_id: str, is_source: bool = True, skip: int = 0, limit: int = 100) -> List[StorageMove]`: Get moves for a storage location
- `get_recent_moves(days: int = 7, skip: int = 0, limit: int = 100) -> List[StorageMove]`: Get recent moves
- `create_move(material_id: int, material_type: str, from_storage_id: str, to_storage_id: str, quantity: float, moved_by: str, reason: str = None) -> StorageMove`: Create move record

**Example:**
```python
# Get recent storage moves
recent_moves = storage_move_repo.get_recent_moves(days=3)

# Create storage move record
storage_move_repo.create_move(
    material_id=123,
    material_type="HARDWARE",
    from_storage_id="shelf-a2",
    to_storage_id="shelf-c4",
    quantity=25,
    moved_by="mike.jones",
    reason="Reorganizing storage"
)
```

### 5.6 Tool Management

#### 5.6.1 ToolRepository

The `ToolRepository` manages leatherworking tools and equipment.

**Key Methods:**
- `get_tools_by_category(category: ToolCategory, skip: int = 0, limit: int = 100) -> List[Tool]`: Get tools by category
- `get_tools_by_status(status: str, skip: int = 0, limit: int = 100) -> List[Tool]`: Get tools by status
- `get_tools_by_location(location: str, skip: int = 0, limit: int = 100) -> List[Tool]`: Get tools at a location
- `get_tools_due_for_maintenance(skip: int = 0, limit: int = 100) -> List[Tool]`: Get tools due for maintenance
- `get_checked_out_tools(skip: int = 0, limit: int = 100) -> List[Tool]`: Get checked out tools
- `update_tool_status(tool_id: int, status: str) -> Optional[Tool]`: Update tool status
- `update_tool_maintenance_schedule(tool_id: int, last_maintenance: str, next_maintenance: str) -> Optional[Tool]`: Update maintenance schedule
- `search_tools(query: str, skip: int = 0, limit: int = 100) -> List[Tool]`: Search for tools

**Example:**
```python
# Get tools due for maintenance
due_tools = tool_repo.get_tools_due_for_maintenance()

# Update tool maintenance schedule
tool_repo.update_tool_maintenance_schedule(
    tool_id=456,
    last_maintenance=datetime.now().isoformat(),
    next_maintenance=(datetime.now() + timedelta(days=90)).isoformat()
)
```

#### 5.6.2 ToolMaintenanceRepository

The `ToolMaintenanceRepository` tracks tool maintenance records.

**Key Methods:**
- `get_maintenance_by_tool(tool_id: int, skip: int = 0, limit: int = 100) -> List[ToolMaintenance]`: Get maintenance for a tool
- `get_maintenance_by_status(status: str, skip: int = 0, limit: int = 100) -> List[ToolMaintenance]`: Get maintenance by status
- `get_maintenance_by_date_range(start_date: str, end_date: str, skip: int = 0, limit: int = 100) -> List[ToolMaintenance]`: Get maintenance in date range
- `get_scheduled_maintenance(skip: int = 0, limit: int = 100) -> List[ToolMaintenance]`: Get scheduled maintenance
- `update_maintenance_status(maintenance_id: int, status: str) -> Optional[ToolMaintenance]`: Update maintenance status
- `create_maintenance_record(tool_id: int, tool_name: str, maintenance_type: str, performed_by: str, status: str = "SCHEDULED", date: Optional[str] = None) -> ToolMaintenance`: Create maintenance record

**Example:**
```python
# Get maintenance history for a tool
history = tool_maintenance_repo.get_maintenance_by_tool(tool_id=123)

# Create maintenance record
tool_maintenance_repo.create_maintenance_record(
    tool_id=123,
    tool_name="Leather Skiving Machine",
    maintenance_type="Blade Replacement",
    performed_by="alex.johnson",
    status="COMPLETED"
)
```

#### 5.6.3 ToolCheckoutRepository

The `ToolCheckoutRepository` manages tool checkout and usage tracking.

**Key Methods:**
- `get_checkouts_by_tool(tool_id: int, skip: int = 0, limit: int = 100) -> List[ToolCheckout]`: Get checkouts for a tool
- `get_checkouts_by_project(project_id: int, skip: int = 0, limit: int = 100) -> List[ToolCheckout]`: Get checkouts for a project
- `get_checkouts_by_user(checked_out_by: str, skip: int = 0, limit: int = 100) -> List[ToolCheckout]`: Get checkouts by user
- `get_active_checkouts(skip: int = 0, limit: int = 100) -> List[ToolCheckout]`: Get active checkouts
- `get_overdue_checkouts(skip: int = 0, limit: int = 100) -> List[ToolCheckout]`: Get overdue checkouts
- `create_checkout(tool_id: int, tool_name: str, checked_out_by: str, due_date: str, project_id: Optional[int] = None, project_name: Optional[str] = None) -> ToolCheckout`: Create checkout
- `return_tool(checkout_id: int, condition_after: Optional[str] = None, issue_description: Optional[str] = None) -> Optional[ToolCheckout]`: Record tool return

**Example:**
```python
# Get overdue tool checkouts
overdue = tool_checkout_repo.get_overdue_checkouts()

# Create a new checkout
tool_checkout_repo.create_checkout(
    tool_id=789,
    tool_name="Hand Stitching Set",
    checked_out_by="sarah.miller",
    due_date=(datetime.now() + timedelta(days=3)).isoformat(),
    project_id=456,
    project_name="Custom Wallet"
)
```

### 5.7 Documentation

#### 5.7.1 DocumentationResourceRepository

The `DocumentationResourceRepository` manages system documentation resources.

**Key Methods:**
- `get_resources_by_category(category: str, skip: int = 0, limit: int = 100) -> List[DocumentationResource]`: Get resources by category
- `get_resources_by_type(resource_type: str, skip: int = 0, limit: int = 100) -> List[DocumentationResource]`: Get resources by type
- `get_resources_by_skill_level(skill_level: SkillLevel, skip: int = 0, limit: int = 100) -> List[DocumentationResource]`: Get resources by skill level
- `get_resources_by_tags(tags: List[str], skip: int = 0, limit: int = 100) -> List[DocumentationResource]`: Get resources by tags
- `get_resources_by_author(author: str, skip: int = 0, limit: int = 100) -> List[DocumentationResource]`: Get resources by author
- `get_recently_updated_resources(skip: int = 0, limit: int = 100) -> List[DocumentationResource]`: Get recently updated resources
- `search_resources(query: str, skip: int = 0, limit: int = 100) -> List[DocumentationResource]`: Search for resources
- `update_resource_content(resource_id: str, content: str) -> Optional[DocumentationResource]`: Update resource content
- `update_resource_tags(resource_id: str, tags: List[str]) -> Optional[DocumentationResource]`: Update resource tags

**Example:**
```python
# Get recently updated documentation
recent_docs = documentation_resource_repo.get_recently_updated_resources(limit=10)

# Search for documentation
search_results = documentation_resource_repo.search_resources(query="leather dyeing")
```

#### 5.7.2 DocumentationCategoryRepository

The `DocumentationCategoryRepository` manages documentation categories.

**Key Methods:**
- `get_category_with_resources(category_id: str) -> Optional[Dict[str, Any]]`: Get category with resources
- `search_categories(query: str, skip: int = 0, limit: int = 100) -> List[DocumentationCategory]`: Search for categories
- `update_category_resources(category_id: str, resources: List[str]) -> Optional[DocumentationCategory]`: Update category resources

**Example:**
```python
# Get a documentation category with all its resources
category = documentation_category_repo.get_category_with_resources(category_id="cat123")

# Update resources in a category
documentation_category_repo.update_category_resources(
    category_id="cat123",
    resources=["doc1", "doc2", "doc3"]
)
```

#### 5.7.3 PatternRepository

The `PatternRepository` manages leatherworking patterns and designs.

**Key Methods:**
- `get_patterns_by_project_type(project_type: ProjectType, skip: int = 0, limit: int = 100) -> List[Pattern]`: Get patterns by project type
- `get_patterns_by_skill_level(skill_level: SkillLevel, skip: int = 0, limit: int = 100) -> List[Pattern]`: Get patterns by skill level
- `get_patterns_by_author(author_name: str, skip: int = 0, limit: int = 100) -> List[Pattern]`: Get patterns by author
- `get_favorite_patterns(skip: int = 0, limit: int = 100) -> List[Pattern]`: Get favorite patterns
- `get_public_patterns(skip: int = 0, limit: int = 100) -> List[Pattern]`: Get public patterns
- `get_patterns_by_tags(tags: List[str], skip: int = 0, limit: int = 100) -> List[Pattern]`: Get patterns by tags
- `search_patterns(query: str, skip: int = 0, limit: int = 100) -> List[Pattern]`: Search for patterns
- `toggle_favorite(pattern_id: int) -> Optional[Pattern]`: Toggle favorite status
- `update_pattern_tags(pattern_id: int, tags: List[str]) -> Optional[Pattern]`: Update pattern tags

**Example:**
```python
# Get patterns for beginners
beginner_patterns = pattern_repo.get_patterns_by_skill_level(SkillLevel.BEGINNER)

# Toggle a pattern's favorite status
pattern_repo.toggle_favorite(pattern_id=123)
```

#### 5.7.4 ProjectTemplateRepository

The `ProjectTemplateRepository` manages reusable project templates.

**Key Methods:**
- `get_templates_by_project_type(project_type: ProjectType, skip: int = 0, limit: int = 100) -> List[ProjectTemplate]`: Get templates by project type
- `get_templates_by_skill_level(skill_level: SkillLevel, skip: int = 0, limit: int = 100) -> List[ProjectTemplate]`: Get templates by skill level
- `get_public_templates(skip: int = 0, limit: int = 100) -> List[ProjectTemplate]`: Get public templates
- `get_templates_by_tags(tags: List[str], skip: int = 0, limit: int = 100) -> List[ProjectTemplate]`: Get templates by tags
- `search_templates(query: str, skip: int = 0, limit: int = 100) -> List[ProjectTemplate]`: Search for templates
- `get_template_with_components(template_id: str) -> Optional[Dict[str, Any]]`: Get template with components

**Example:**
```python
# Get template with its components
template = project_template_repo.get_template_with_components(template_id="temp456")

# Search for templates
search_results = project_template_repo.search_templates(query="wallet")
```

### 5.8 Platform Integration

#### 5.8.1 PlatformIntegrationRepository

The `PlatformIntegrationRepository` manages e-commerce platform integrations.

**Key Methods:**
- `get_integration_by_platform(platform: str) -> Optional[PlatformIntegration]`: Get integration by platform
- `get_integration_by_shop(shop_name: str) -> Optional[PlatformIntegration]`: Get integration by shop
- `get_active_integrations(skip: int = 0, limit: int = 100) -> List[PlatformIntegration]`: Get active integrations
- `update_integration_tokens(integration_id: str, access_token: str, refresh_token: Optional[str] = None, token_expires_at: Optional[datetime] = None) -> Optional[PlatformIntegration]`: Update tokens
- `update_sync_timestamp(integration_id: str) -> Optional[PlatformIntegration]`: Update sync timestamp
- `toggle_active_status(integration_id: str) -> Optional[PlatformIntegration]`: Toggle active status
- `update_settings(integration_id: str, settings: Dict[str, Any]) -> Optional[PlatformIntegration]`: Update settings

**Example:**
```python
# Get integration for Etsy platform
etsy_integration = platform_integration_repo.get_integration_by_platform("etsy")

# Update API tokens after refresh
platform_integration_repo.update_integration_tokens(
    integration_id="int123",
    access_token="new_access_token",
    refresh_token="new_refresh_token",
    token_expires_at=datetime.now() + timedelta(days=30)
)
```

#### 5.8.2 SyncEventRepository

The `SyncEventRepository` tracks platform synchronization events.

**Key Methods:**
- `get_events_by_integration(platform_integration_id: str, skip: int = 0, limit: int = 100) -> List[SyncEvent]`: Get events for an integration
- `get_events_by_type(event_type: str, skip: int = 0, limit: int = 100) -> List[SyncEvent]`: Get events by type
- `get_events_by_status(status: str, skip: int = 0, limit: int = 100) -> List[SyncEvent]`: Get events by status
- `get_recent_events(days: int = 7, skip: int = 0, limit: int = 100) -> List[SyncEvent]`: Get recent events
- `create_sync_event(platform_integration_id: str, event_type: str, status: str, items_processed: int = 0, message: Optional[str] = None) -> SyncEvent`: Create sync event
- `get_sync_statistics(platform_integration_id: str) -> Dict[str, Any]`: Get sync statistics

**Example:**
```python
# Create a new sync event record
sync_event_repo.create_sync_event(
    platform_integration_id="int123",
    event_type="order_import",
    status="success",
    items_processed=5,
    message="Imported 5 new orders from Etsy"
)

# Get sync statistics
stats = sync_event_repo.get_sync_statistics(platform_integration_id="int123")
```

---

## 6. Security and Encryption

### 6.1 Sensitive Data Handling

The repository layer includes built-in support for encrypting and decrypting sensitive data fields:

```python
# Example of sensitive field designation in model
class Customer(Base):
    # ...
    SENSITIVE_FIELDS = ["phone", "address"]

# Example of encryption in BaseRepository
def _encrypt_sensitive_fields(self, data: Dict[str, Any], entity_id=None) -> Dict[str, Any]:
    """Encrypt sensitive fields in the data dictionary."""
    if not self.encryption_service or not hasattr(self.model, 'SENSITIVE_FIELDS'):
        return data
        
    encrypted_data = data.copy()
    for field in self.model.SENSITIVE_FIELDS:
        if field in encrypted_data and encrypted_data[field] is not None:
            encrypted_data[field] = self.encryption_service.encrypt_field(
                entity_id or 'new',
                field,
                encrypted_data[field]
            )
            
    return encrypted_data
```

### 6.2 Encryption Service Integration

The `EncryptionService` is injected into repositories to handle encryption/decryption:

```python
# Example encryption service usage
class EncryptionService:
    def __init__(self, master_key):
        self.master_key = master_key
        
    def encrypt_field(self, entity_id, field_name, value):
        """Encrypt a field value"""
        # Encryption implementation...
        
    def decrypt_field(self, entity_id, field_name, encrypted_value):
        """Decrypt a field value"""
        # Decryption implementation...
```

### 6.3 Secure Repositories

Repositories with higher security needs (like `PlatformIntegrationRepository`) have additional security measures:

```python
# Example of enhanced security for platform integration
class PlatformIntegrationRepository(BaseRepository[PlatformIntegration]):
    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = PlatformIntegration
        
        # Define sensitive fields that need encryption
        if not hasattr(self.model, 'SENSITIVE_FIELDS'):
            self.model.SENSITIVE_FIELDS = [
                "api_key", 
                "api_secret", 
                "access_token", 
                "refresh_token"
            ]
```

---

## 7. Transaction Management

### 7.1 Session Management

All repositories use a shared SQLAlchemy session for consistent transaction handling:

```python
# Example of session injection into repositories
def get_repository_factory(db: Session) -> RepositoryFactory:
    """Create a repository factory with the current database session."""
    encryption_service = get_encryption_service()
    return RepositoryFactory(db, encryption_service)

# Using the same session for multiple repositories
factory = get_repository_factory(db)
customer_repo = factory.create_customer_repository()
sale_repo = factory.create_sale_repository()

# Both repositories use the same session, ensuring transaction integrity
```

### 7.2 Transaction Context

For multi-step operations that need atomic behavior, use explicit transaction contexts:

```python
# Example of transaction context in a service
def process_order(customer_id, order_data):
    try:
        # Start multiple operations in the same transaction
        customer = customer_repo.get_by_id(customer_id)
        if not customer:
            raise ValueError("Customer not found")
            
        sale = sale_repo.create(order_data)
        product_repo.update_product_inventory(order_data['product_id'], -1)
        
        # Commit all changes at once
        db.commit()
        return sale
    except Exception as e:
        # Roll back all changes if any operation fails
        db.rollback()
        raise
```

---

## 8. Integration with Services

### 8.1 Service Layer Structure

The repository layer integrates with the service layer, which contains business logic:

```python
# Example service using repositories
class CustomerService:
    def __init__(self, customer_repository, sale_repository):
        self.customer_repository = customer_repository
        self.sale_repository = sale_repository
    
    def get_customer_with_orders(self, customer_id):
        """Get a customer with their order history."""
        # Get customer from repository
        customer = self.customer_repository.get_by_id(customer_id)
        if not customer:
            return None
            
        # Get customer's sales from repository
        sales = self.sale_repository.get_sales_by_customer(customer_id)
        
        # Combine and return
        return {
            "customer": customer,
            "sales": sales
        }
```

### 8.2 Dependency Injection

Repositories are injected into services through dependency injection:

```python
# Example of dependency injection in FastAPI
def get_customer_service(
    db: Session = Depends(get_db),
    encryption_service = Depends(get_encryption_service)
) -> CustomerService:
    """Create a CustomerService with injected repositories."""
    factory = RepositoryFactory(db, encryption_service)
    customer_repo = factory.create_customer_repository()
    sale_repo = factory.create_sale_repository()
    return CustomerService(customer_repo, sale_repo)

@app.get("/customers/{id}/with-orders")
def get_customer_with_orders(
    id: int,
    customer_service: CustomerService = Depends(get_customer_service)
):
    """API endpoint using the service."""
    return customer_service.get_customer_with_orders(id)
```

---

## 9. Testing Strategy

### 9.1 Unit Testing Repositories

Each repository should have unit tests that verify its functionality:

```python
# Example repository test
def test_customer_repository():
    # Setup in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    # Create test session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create repository
    repo = CustomerRepository(session)
    
    # Test operations
    customer_data = {"name": "Test User", "email": "test@example.com"}
    customer = repo.create(customer_data)
    
    # Assertions
    assert customer.id is not None
    assert customer.name == "Test User"
    
    # Test retrieval
    retrieved = repo.get_by_id(customer.id)
    assert retrieved.email == "test@example.com"
```

### 9.2 Mock Dependencies

When testing services that use repositories, mock the repositories:

```python
# Example of mocking repositories in service tests
def test_customer_service():
    # Create mock repositories
    mock_customer_repo = MagicMock()
    mock_sale_repo = MagicMock()
    
    # Setup return values
    mock_customer = MagicMock()
    mock_customer.id = 1
    mock_customer.name = "Test Customer"
    mock_customer_repo.get_by_id.return_value = mock_customer
    
    mock_sales = [MagicMock(), MagicMock()]
    mock_sale_repo.get_sales_by_customer.return_value = mock_sales
    
    # Create service with mock repositories
    service = CustomerService(mock_customer_repo, mock_sale_repo)
    
    # Test service method
    result = service.get_customer_with_orders(1)
    
    # Assertions
    assert result["customer"] == mock_customer
    assert result["sales"] == mock_sales
    mock_customer_repo.get_by_id.assert_called_once_with(1)
    mock_sale_repo.get_sales_by_customer.assert_called_once_with(1)
```

---

## 10. Performance Considerations

### 10.1 Query Optimization

Repositories implement efficient queries to minimize database load:

```python
# Example of optimized query in a repository
def get_active_customers_with_purchases(self, days: int = 30, skip: int = 0, limit: int = 100) -> List[Customer]:
    """
    Get active customers who made purchases within the specified period.
    
    Uses a JOIN to fetch data in a single query rather than multiple queries.
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    
    query = (
        self.session.query(self.model)
        .join(Sale, Sale.customer_id == self.model.id)
        .filter(
            and_(
                self.model.status == CustomerStatus.ACTIVE,
                Sale.createdAt >= cutoff_date
            )
        )
        .group_by(self.model.id)
        .offset(skip)
        .limit(limit)
    )
    
    return [self._decrypt_sensitive_fields(entity) for entity in query.all()]
```

### 10.2 Pagination

All list operations support pagination to handle large datasets efficiently:

```python
# Example of pagination
customers = customer_repo.list(skip=0, limit=20)
next_page_customers = customer_repo.list(skip=20, limit=20)
```

### 10.3 Lazy Loading vs. Eager Loading

Repositories can implement eager loading when appropriate to avoid N+1 query problems:

```python
# Example of eager loading in a repository
def get_project_with_components_and_materials(self, project_id: int) -> Optional[Project]:
    """
    Get a project with its components and materials.
    
    Uses eager loading to load all related data in fewer queries.
    """
    query = (
        self.session.query(self.model)
        .options(
            joinedload(self.model.components)
            .joinedload(ProjectComponent.component)
            .joinedload(Component.materials)
        )
        .filter(self.model.id == project_id)
    )
    
    entity = query.first()
    return self._decrypt_sensitive_fields(entity) if entity else None
```

---

## 11. Implementation Best Practices

### 11.1 Code Style Guidelines

- Follow PEP 8 for Python code style
- Use descriptive method names that indicate the operation
- Include type hints for all parameters and return values
- Document methods with docstrings that explain parameters and return values
- Keep methods focused on a single responsibility

### 11.2 Error Handling

Repositories should handle database errors gracefully:

```python
# Example of error handling in a repository
def create(self, data: Dict[str, Any]) -> T:
    """Create a new entity."""
    try:
        # Encrypt sensitive fields before saving
        encrypted_data = self._encrypt_sensitive_fields(data)
        entity = self.model(**encrypted_data)
        self.session.add(entity)
        self.session.commit()
        self.session.refresh(entity)
        return self._decrypt_sensitive_fields(entity)
    except SQLAlchemyError as e:
        self.session.rollback()
        # Convert to application-specific error
        raise RepositoryError(f"Failed to create {self.model.__name__}: {str(e)}")
```

### 11.3 Naming Conventions

- Repository classes should be named `EntityRepository`
- Method names should clearly indicate their purpose:
  - `get_*` for retrieving entities
  - `create_*` for creating entities
  - `update_*` for modifying entities
  - `delete_*` for removing entities
  - `search_*` for search operations
  - `find_*` for specialized queries

### 11.4 Security Best Practices

- Never store sensitive data unencrypted
- Use the `SENSITIVE_FIELDS` designation for fields that need encryption
- Don't expose database errors directly to the client
- Always validate inputs before using them in queries
- Use parameterized queries to prevent SQL injection

---

## 12. Examples

### 12.1 Basic CRUD Operations

```python
# Creating a new customer
customer_data = {
    "name": "John Smith",
    "email": "john.smith@example.com",
    "phone": "555-123-4567",
    "status": CustomerStatus.ACTIVE
}
customer = customer_repo.create(customer_data)

# Retrieving the customer
retrieved = customer_repo.get_by_id(customer.id)

# Updating the customer
updated_data = {
    "name": "John R. Smith",
    "phone": "555-987-6543"
}
updated = customer_repo.update(customer.id, updated_data)

# Deleting the customer
deleted = customer_repo.delete(customer.id)
```

### 12.2 Advanced Querying

```python
# Get active customers with pagination and filtering
active_premium_customers = customer_repo.list(
    status=CustomerStatus.ACTIVE,
    tier=CustomerTier.PREMIUM,
    skip=0,
    limit=20
)

# Search customers
search_results = customer_repo.search_customers(query="smith")

# Get customers with recent purchases
recent_buyers = customer_repo.get_customers_with_recent_purchases(days=30)
```

### 12.3 Transaction Example

```python
# Process a new sale with inventory updates in a transaction
def process_sale(customer_id, product_ids, quantities):
    try:
        # Start transaction
        sale_data = {
            "customer_id": customer_id,
            "createdAt": datetime.now(),
            "status": SaleStatus.CONFIRMED,
            "paymentStatus": PaymentStatus.PAID
        }
        
        # Create the sale
        sale = sale_repo.create(sale_data)
        
        # Create sale items and update inventory
        total_amount = 0
        for i, product_id in enumerate(product_ids):
            quantity = quantities[i]
            
            # Get product to calculate price
            product = product_repo.get_by_id(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
                
            # Create sale item
            item_data = {
                "sale_id": sale.id,
                "product_id": product_id,
                "quantity": quantity,
                "price": product.sellingPrice,
                "name": product.name
            }
            sale_item_repo.create(item_data)
            
            # Update product inventory
            product_repo.update_product_inventory(product_id, -quantity)
            
            # Update total
            total_amount += product.sellingPrice * quantity
        
        # Update sale with total
        sale_repo.update(sale.id, {"total_amount": total_amount})
        
        # Commit transaction
        db.commit()
        return sale
    except Exception as e:
        # Rollback on error
        db.rollback()
        raise
```

---

## 13. Troubleshooting

### 13.1 Common Issues

#### 13.1.1 Session Management Errors

**Problem**: "Object has been detached from its parent session"

**Solution**: Ensure you're using the same session for related operations. Don't mix sessions across repositories when working with related data.

#### 13.1.2 Encryption/Decryption Errors

**Problem**: "Cannot decrypt field: Invalid token"

**Solution**: Check that the same encryption key is being used for encryption and decryption. Fields encrypted with one key cannot be decrypted with another.

#### 13.1.3 Transaction Issues

**Problem**: Changes not being persisted to the database

**Solution**: Ensure you're calling `session.commit()` after operations. In transaction blocks, make sure exceptions are properly handled and `rollback()` is called on errors.

### 13.2 Debugging Tips

1. Enable SQLAlchemy echo mode to see SQL queries:
   ```python
   engine = create_engine(url, echo=True)
   ```

2. Check for uncommitted transactions:
   ```python
   # See if there are pending changes
   pending_changes = session.new.union(session.dirty).union(session.deleted)
   if pending_changes:
       print("Uncommitted changes:", pending_changes)
   ```

3. Verify encryption configuration:
   ```python
   # Test encryption service directly
   encrypted = encryption_service.encrypt_field("test_id", "test_field", "test_value")
   decrypted = encryption_service.decrypt_field("test_id", "test_field", encrypted)
   assert decrypted == "test_value"
   ```

---

## 14. Extending the Repository Layer

### 14.1 Adding a New Repository

To add a new repository for a model:

1. Create a new repository class that extends `BaseRepository`:
   ```python
   class NewEntityRepository(BaseRepository[NewEntity]):
       def __init__(self, session: Session, encryption_service=None):
           super().__init__(session, encryption_service)
           self.model = NewEntity
           
       # Add entity-specific methods here
       def get_by_custom_field(self, value: str) -> Optional[NewEntity]:
           entity = self.session.query(self.model).filter(self.model.custom_field == value).first()
           return self._decrypt_sensitive_fields(entity) if entity else None
   ```

2. Add a factory method to `RepositoryFactory`:
   ```python
   def create_new_entity_repository(self) -> NewEntityRepository:
       """Create a NewEntityRepository instance."""
       return NewEntityRepository(self.session, self.encryption_service)
   ```

3. Add a dependency injection function if needed:
   ```python
   def get_new_entity_repository(
       factory: RepositoryFactory = Depends(get_repository_factory)
   ) -> NewEntityRepository:
       """Dependency provider for NewEntityRepository."""
       return factory.create_new_entity_repository()
   ```

### 14.2 Adding New Features

To add a new feature to an existing repository:

1. Identify the appropriate repository class
2. Add a new method with proper documentation:
   ```python
   def find_entities_with_special_condition(self, condition_value: str, skip: int = 0, limit: int = 100) -> List[Entity]:
       """
       Find entities with a special condition.
       
       Args:
           condition_value (str): The condition value to match
           skip (int): Number of records to skip
           limit (int): Maximum number of records to return
           
       Returns:
           List[Entity]: List of matching entities
       """
       query = self.session.query(self.model).filter(self.model.special_field == condition_value)
       
       entities = query.offset(skip).limit(limit).all()
       return [self._decrypt_sensitive_fields(entity) for entity in entities]
   ```

3. Add tests for the new method

### 14.3 Supporting New Database Operations

To extend the `BaseRepository` with new operations for all repositories:

1. Add the method to `BaseRepository`:
   ```python
   def bulk_create(self, data_list: List[Dict[str, Any]]) -> List[T]:
       """
       Create multiple entities in a single operation.
       
       Args:
           data_list (List[Dict[str, Any]]): List of data dictionaries for multiple entities
           
       Returns:
           List[T]: List of created entities
       """
       entities = []
       for data in data_list:
           encrypted_data = self._encrypt_sensitive_fields(data)
           entity = self.model(**encrypted_data)
           entities.append(entity)
           
       self.session.add_all(entities)
       self.session.commit()
       
       # Refresh all entities to get generated IDs and defaults
       for entity in entities:
           self.session.refresh(entity)
           
       return [self._decrypt_sensitive_fields(entity) for entity in entities]
   ```

2. Add tests for the new operation