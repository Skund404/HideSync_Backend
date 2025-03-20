# HideSync Service Layer Documentation

## 1. Architecture Overview

The HideSync service layer follows a clean architecture pattern that provides a clear separation of concerns between the data access layer (repositories) and the presentation layer (API controllers). This design enhances maintainability, testability, and facilitates future changes to the system.

### 1.1 Key Components

- **Base Service**: A foundation class providing common functionality used across all services.
- **Exception Framework**: Standardized domain-specific exceptions for consistent error handling.
- **Event System**: Supports event-driven architecture for loose coupling between components.
- **Validation Framework**: Ensures data integrity through consistent validation.
- **Service Factory**: Manages service instances and dependencies for proper dependency injection.

### 1.2 Service Layer Patterns

The service layer implements several design patterns:

- **Repository Pattern**: Abstracts data access operations through repositories.
- **Unit of Work Pattern**: Manages transactions with the `transaction()` context manager.
- **Factory Pattern**: Creates service instances with proper dependencies.
- **Observer Pattern**: Used for event handling and propagation.
- **Decorator Pattern**: Applied through validation decorators.

### 1.3 Dependency Injection

Services accept dependencies in their constructors, allowing for:

- Loose coupling between components
- Easier testing through dependency mocking
- Runtime configuration of service behavior

## 2. Core Infrastructure

### 2.1 BaseService

Located at `app/services/base_service.py`, this is the foundation for all services in HideSync.

#### Key Features:

- **Transaction Management**: Handles database transactions with proper rollback.
- **CRUD Operations**: Basic Create, Read, Update, Delete operations.
- **Caching Support**: Optional integration with a caching system.
- **Event Publishing**: Support for domain events.

#### Usage Example:

```python
# Creating a custom service
class MyService(BaseService[MyEntity]):
    def __init__(self, session, repository_class, **kwargs):
        super().__init__(session, repository_class, **kwargs)
        
    def custom_operation(self, data):
        with self.transaction():
            # Business logic here
            result = self.repository.custom_operation(data)
            return result
```

### 2.2 Exception Framework

Located at `app/core/exceptions.py`, provides a hierarchical exception system.

#### Key Exception Types:

- `HideSyncException`: Base exception for all system errors.
- `DomainException`: Base for domain-specific errors.
- `MaterialNotFoundException`, `ProjectNotFoundException`, etc.: Entity-specific exceptions.
- `ValidationException`: For input validation failures.
- `ConcurrentModificationException`: For optimistic locking conflicts.

#### Usage Example:

```python
# Using domain-specific exceptions
if not material:
    raise MaterialNotFoundException(material_id)

# Using validation exceptions
if quantity <= 0:
    raise ValidationException("Invalid quantity", {"quantity": ["Must be greater than zero"]})
```

### 2.3 Event System

Located at `app/core/events.py`, enables event-driven architecture.

#### Key Components:

- `DomainEvent`: Base class for all events.
- `EventBus`: Central component for publishing and subscribing to events.
- Common events: `EntityCreated`, `EntityUpdated`, `EntityDeleted`, etc.

#### Usage Example:

```python
# Publishing an event
self.event_bus.publish(MaterialCreated(
    material_id=material.id,
    material_type=material.material_type,
    user_id=user_id
))

# Subscribing to an event
event_bus.subscribe("MaterialCreated", handle_material_created)
```

### 2.4 Validation Framework

Located at `app/core/validation.py`, ensures data integrity.

#### Key Components:

- `ValidationResult`: Container for validation errors.
- `validate_input`: Decorator for input validation.
- `validate_entity`: Helper for entity validation.
- Common validators for emails, phones, dates, etc.

#### Usage Example:

```python
# Using validation decorators
@validate_input(validate_material)
def create_material(self, data):
    # Method only executes if validation passes
    pass

# Using validation helpers
result = validate_required_fields(data, ["name", "quantity", "unit"])
if not result.is_valid:
    raise ValidationException("Missing required fields", result.to_dict())
```

## 3. Domain Services

### 3.1 MaterialService

Located at `app/services/material_service.py`, manages materials and inventory.

#### Primary Responsibilities:

- Material creation, update, deletion
- Inventory management and tracking
- Material search and categorization
- Stock level monitoring

#### Key Methods:

- `create_material(data)`: Create a new material with type-specific handling
- `adjust_inventory(material_id, quantity_change, reason)`: Update inventory levels
- `adjust_inventory_with_optimistic_locking(...)`: Update inventory with concurrency control
- `get_low_stock_materials(threshold_percentage)`: Get materials below reorder threshold
- `get_materials_by_storage_location(location_id)`: Find materials by location

#### Usage Example:

```python
# Creating a material
material = material_service.create_material({
    "name": "Vegetable Tanned Leather",
    "material_type": "LEATHER", 
    "quantity": 10.5,
    "unit": "SQUARE_FOOT",
    "reorder_point": 5.0
})

# Adjusting inventory
material_service.adjust_inventory(
    material_id=1,
    quantity_change=-2.5,
    reason="Used in project #123"
)
```

### 3.2 ProjectService

Located at `app/services/project_service.py`, manages project workflow.

#### Primary Responsibilities:

- Project creation and management
- Project status workflow
- Component management
- Timeline task tracking
- Material requirements calculation

#### Key Methods:

- `create_project(data)`: Create a new project
- `create_project_with_components(project_data, components)`: Create project with components
- `update_project_status(project_id, new_status, ...)`: Change project status
- `add_component(project_id, component_data)`: Add component to project
- `calculate_material_requirements(project_id)`: Calculate required materials

#### Usage Example:

```python
# Creating a project
project = project_service.create_project({
    "name": "Custom Wallet",
    "type": "WALLET",
    "customer_id": 42,
    "due_date": "2025-04-30"
})

# Updating project status
project_service.update_project_status(
    project_id=1,
    new_status="CUTTING",
    comments="Starting the cutting phase"
)
```

### 3.3 CustomerService

Located at `app/services/customer_service.py`, manages customer data.

#### Primary Responsibilities:

- Customer data management
- Communication history
- Customer segmentation and tiering
- Customer analytics

#### Key Methods:

- `create_customer(data)`: Create a new customer
- `update_customer(customer_id, data)`: Update customer information
- `change_customer_tier(customer_id, new_tier, reason)`: Change customer tier
- `record_communication(customer_id, communication_data)`: Log customer communication
- `get_customer_with_details(customer_id)`: Get comprehensive customer details

#### Usage Example:

```python
# Creating a customer
customer = customer_service.create_customer({
    "name": "John Doe",
    "email": "john.doe@example.com",
    "phone": "+1234567890",
    "source": "WEBSITE"
})

# Recording communication
customer_service.record_communication(
    customer_id=1,
    communication_data={
        "communication_type": "EMAIL",
        "subject": "Order confirmation",
        "content": "Your order has been confirmed."
    }
)
```

### 3.4 SaleService

Located at `app/services/sale_service.py`, manages sales and orders.

#### Primary Responsibilities:

- Sale and order management
- Order item tracking
- Payment status tracking
- Order fulfillment
- Sales analytics

#### Key Methods:

- `create_sale(data)`: Create a new sale
- `add_sale_item(sale_id, item_data)`: Add item to sale
- `update_sale_status(sale_id, new_status)`: Update sale status
- `update_payment_status(sale_id, new_status, amount)`: Update payment status
- `fulfill_sale(sale_id)`: Mark sale as fulfilled and handle inventory

#### Usage Example:

```python
# Creating a sale
sale = sale_service.create_sale({
    "customer_id": 42,
    "items": [
        {
            "product_id": 101,
            "quantity": 1,
            "price": 149.99,
            "name": "Custom Wallet"
        }
    ]
})

# Updating payment status
sale_service.update_payment_status(
    sale_id=1,
    new_status="DEPOSIT_PAID",
    amount=50.00
)
```

## 4. Advanced Services

### 4.1 DashboardService

Located at `app/services/dashboard_service.py`, provides analytics and metrics.

#### Primary Responsibilities:

- Aggregating business metrics
- Generating dashboard summaries
- Monitoring inventory, projects, sales, etc.
- Collecting recent activity

#### Key Methods:

- `get_dashboard_summary(use_cache)`: Get comprehensive dashboard data
- `get_projects_overview()`: Get detailed project metrics
- `get_inventory_overview()`: Get inventory status and metrics
- `get_sales_overview()`: Get sales performance metrics
- `get_customers_overview()`: Get customer metrics

#### Usage Example:

```python
# Getting dashboard summary
summary = dashboard_service.get_dashboard_summary()

# Getting detailed inventory overview
inventory = dashboard_service.get_inventory_overview()
```

### 4.2 FileStorageService

Located at `app/services/storage_service.py`, manages file storage.

#### Primary Responsibilities:

- File storage and retrieval
- File metadata management
- File integrity verification
- Directory management

#### Key Methods:

- `store_file(file_data, filename, content_type, metadata)`: Store a file
- `retrieve_file(file_id)`: Retrieve a file and its metadata
- `delete_file(file_id)`: Delete a file
- `list_files(directory, file_type, limit, offset)`: List files with filtering
- `create_directory(directory_path)`: Create a new directory

#### Usage Example:

```python
# Storing a file
metadata = file_storage_service.store_file(
    file_data=file_bytes,
    filename="pattern.svg",
    metadata={"project_id": 123}
)

# Retrieving a file
file_data, metadata = file_storage_service.retrieve_file("file-id-123")
```

### 4.3 AuditService

Located at `app/services/audit_service.py`, provides audit trail functionality.

#### Primary Responsibilities:

- Tracking entity changes
- Logging user actions
- Recording system events
- Providing audit history

#### Key Methods:

- `record_entity_change(entity_type, entity_id, action, changes, ...)`: Record entity change
- `record_create/update/delete(entity, ...)`: Record specific entity actions
- `record_login(user_id, success, ...)`: Record login attempts
- `record_api_access(endpoint, method, status_code, ...)`: Record API access
- `get_entity_history(entity_type, entity_id, ...)`: Get entity change history

#### Usage Example:

```python
# Recording entity creation
audit_service.record_create(entity=material)

# Getting entity history
history = audit_service.get_entity_history(
    entity_type="Material",
    entity_id=42,
    start_date=datetime(2025, 1, 1)
)
```

## 5. Service Factory

Located at `app/services/service_factory.py`, manages service instantiation.

#### Primary Responsibilities:

- Creating service instances with dependencies
- Managing singleton service instances
- Centralizing service creation logic

#### Key Methods:

- `get_material_service()`: Get MaterialService instance
- `get_project_service()`: Get ProjectService instance
- `get_customer_service()`: Get CustomerService instance
- `get_sale_service()`: Get SaleService instance
- `get_service(service_class, **kwargs)`: Get generic service instance

#### Usage Example:

```python
# Creating service factory
service_factory = ServiceFactory(session, security_context=security_context)

# Getting services
material_service = service_factory.get_material_service()
project_service = service_factory.get_project_service()
```

## 6. API Integration

The service layer is designed to integrate smoothly with API controllers.

### 6.1 API Controller Pattern

```python
# Example FastAPI endpoint
@router.get("/materials/{material_id}")
def get_material(
    material_id: int, 
    material_service: MaterialService = Depends(get_material_service)
):
    try:
        material = material_service.get_by_id(material_id)
        if not material:
            raise HTTPException(status_code=404, detail="Material not found")
        return material
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except MaterialNotFoundException:
        raise HTTPException(status_code=404, detail="Material not found")
```

### 6.2 Exception Mapping

The domain exceptions map naturally to HTTP status codes:

| Domain Exception | HTTP Status Code | Description |
|------------------|------------------|-------------|
| EntityNotFoundException | 404 Not Found | Entity not found |
| ValidationException | 400 Bad Request | Invalid input data |
| BusinessRuleError | 422 Unprocessable Entity | Business rule violation |
| ConcurrentModificationException | 409 Conflict | Concurrent modification |
| SecurityException | 401/403 Unauthorized/Forbidden | Security violation |

### 6.3 Dependency Injection Setup

```python
# Dependency for getting services
def get_material_service(
    db: Session = Depends(get_db),
    security_context: SecurityContext = Depends(get_security_context)
) -> MaterialService:
    service_factory = ServiceFactory(db, security_context=security_context)
    return service_factory.get_material_service()
```

## 7. Best Practices

### 7.1 Transaction Management

Always use the `transaction()` context manager for operations that modify data:

```python
with self.transaction():
    # Database operations here
    pass
```

### 7.2 Validation

Use the validation framework for input validation:

```python
@validate_input(validate_entity)
def create_entity(self, data):
    # Method only executes if validation passes
    pass
```

### 7.3 Event Publishing

Publish domain events for significant state changes:

```python
if self.event_bus:
    self.event_bus.publish(EntityCreated(
        entity_id=entity.id,
        user_id=self.security_context.current_user.id if self.security_context else None
    ))
```

### 7.4 Cache Management

Invalidate cache entries when entities change:

```python
if self.cache_service:
    self.cache_service.invalidate(f"Entity:{entity_id}")
```

### 7.5 Error Handling

Use appropriate domain-specific exceptions:

```python
if not entity:
    raise EntityNotFoundException(entity_type, entity_id)
    
if quantity < 0:
    raise ValidationException(
        "Invalid quantity",
        {"quantity": ["Must be a positive number"]}
    )
```

## 8. Further Development

Areas for further service layer development:

1. **Additional Domain Services**:
   - SupplierService
   - PatternService
   - ComponentService
   - ToolService
   - StorageLocationService

2. **Integration Services**:
   - PlatformIntegrationService
   - ImportExportService
   - NotificationService

3. **Advanced Analytics**:
   - Specialized analytics services for each domain
   - Reporting service for generating structured reports
   - Predictive analytics for inventory and sales forecasting

4. **Caching Strategy**:
   - Implement a comprehensive caching service
   - Define caching policies for different entities
   - Add cache warming and background refresh