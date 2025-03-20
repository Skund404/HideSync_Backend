# HideSync Repository Pattern Implementation Guide

## Introduction

This guide provides documentation for the repository layer in the HideSync application. The repository pattern is an essential architectural component that separates data access logic from business logic, providing a clean, consistent interface for data operations.

## Repository Architecture

The HideSync repository layer consists of:

1. **BaseRepository**: A generic implementation of common CRUD operations
2. **Specialized Repositories**: Entity-specific repositories with customized query methods
3. **RepositoryFactory**: A factory class that centrally manages repository creation
4. **Integration with Dependency Injection**: A mechanism to inject repositories into services

## Key Features

- **Type Safety**: All repositories use generics to ensure type safety
- **Encryption Support**: Built-in handling of sensitive data encryption/decryption
- **Transaction Management**: Consistent transaction handling across repositories
- **Query Optimization**: Specialized query methods for common data access patterns
- **Error Handling**: Standardized approach to database errors

## BaseRepository

The `BaseRepository` provides a foundation for all entity-specific repositories with standard CRUD operations:

```python
# Key operations provided by BaseRepository
def get_by_id(self, id: int) -> Optional[T]:
    """Retrieve an entity by ID"""

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
    """Count entities matching filters"""
```

## Entity-Specific Repositories

Each entity in the system has a dedicated repository that extends the `BaseRepository` and adds specialized methods:

### Example: CustomerRepository

```python
class CustomerRepository(BaseRepository[Customer]):
    def __init__(self, session: Session, encryption_service=None):
        super().__init__(session, encryption_service)
        self.model = Customer
    
    def find_by_email(self, email: str) -> Optional[Customer]:
        """Find a customer by email address."""
        # Implementation...
    
    def find_active_customers(self, skip: int = 0, limit: int = 100) -> List[Customer]:
        """Retrieve active customers."""
        # Implementation...
```

## Using the RepositoryFactory

The `RepositoryFactory` provides a single point for creating repository instances, ensuring consistent initialization:

```python
# Creating repositories with the factory
factory = RepositoryFactory(session, encryption_service)
customer_repo = factory.create_customer_repository()
material_repo = factory.create_material_repository()

# Example usage of repositories
customers = customer_repo.find_active_customers(limit=10)
low_stock_materials = material_repo.get_low_stock_materials()
```

## Working with Sensitive Data

Repositories support automatic encryption and decryption of sensitive fields:

```python
# Model designates sensitive fields
class PlatformIntegration(Base):
    SENSITIVE_FIELDS = [
        "api_key",
        "api_secret",
        "access_token",
        "refresh_token"
    ]

# Repository handles encryption/decryption automatically
integration = platform_integration_repo.get_by_id(1)
# Fields are automatically decrypted when retrieved
api_key = integration.api_key

# When saving, fields are automatically encrypted
platform_integration_repo.update(1, {
    "api_key": "new_key",  # Will be encrypted before storage
    "name": "Updated Integration"  # Regular field, not encrypted
})
```

## Repository Categories

HideSync includes repositories for the following categories:

### Customer Management
- **CustomerRepository**: Customer data and relationships

### Inventory and Materials
- **MaterialRepository**: Raw materials (leather, hardware, supplies)
- **InventoryRepository**: Inventory tracking and stock levels
- **ProductRepository**: Finished products and stock items
- **SupplierRepository**: Material suppliers and vendor relationships

### Project Management
- **ProjectRepository**: Customer projects and work tracking
- **ComponentRepository**: Components used in projects
- **TimelineTaskRepository**: Project timeline and task management
- **RecurringProjectRepository**: Scheduled recurring projects

### Sales and Orders
- **SaleRepository**: Customer orders and sales
- **RefundRepository**: Order refunds and returns
- **ShipmentRepository**: Shipping and delivery tracking

### Workshop Management
- **ToolRepository**: Leatherworking tools
- **StorageLocationRepository**: Storage organization and tracking
- **PickingListRepository**: Material picking for projects

### Documentation and Knowledge Base
- **DocumentationResourceRepository**: System documentation
- **PatternRepository**: Leatherworking patterns

### E-commerce Integration
- **PlatformIntegrationRepository**: Integration with sales platforms

## Best Practices

### 1. Transaction Management

Always use the same session for operations that need to be atomic:

```python
# Example of cross-repository transaction
def transfer_material(material_id, from_location, to_location, quantity):
    try:
        # Use the same session for both operations
        material_repo.update_inventory_quantity(material_id, -quantity)
        storage_repo.create_move(material_id, from_location, to_location, quantity)
        session.commit()
    except Exception as e:
        session.rollback()
        raise
```

### 2. Pagination and Large Result Sets

Always use pagination for queries that might return large numbers of records:

```python
# Good - uses pagination
materials = material_repo.list(skip=0, limit=25, materialType=MaterialType.LEATHER)

# Bad - could return too many records
materials = material_repo.list(materialType=MaterialType.LEATHER)
```

### 3. Filtering vs. Custom Query Methods

Use the `list()` method with filtering for simple queries, but implement custom methods for complex ones:

```python
# Simple filtering - use list() with filters
active_customers = customer_repo.list(status=CustomerStatus.ACTIVE)

# Complex query - implement a custom method
recent_buyers = customer_repo.get_customers_with_recent_purchases(days=30)
```

### 4. Error Handling

Handle database errors appropriately:

```python
try:
    customer = customer_repo.create(customer_data)
except Exception as e:
    # Log error details
    logger.error(f"Failed to create customer: {str(e)}")
    # Provide appropriate response
    raise ServiceError("Unable to create customer record")
```

## Integration with Service Layer

Repositories should be injected into services via dependency injection:

```python
class CustomerService:
    def __init__(self, customer_repository: CustomerRepository, sale_repository: SaleRepository):
        self.customer_repository = customer_repository
        self.sale_repository = sale_repository
    
    def get_customer_with_purchase_history(self, customer_id: int):
        customer = self.customer_repository.get_by_id(customer_id)
        if not customer:
            return None
        
        sales = self.sale_repository.get_sales_by_customer(customer_id)
        return {
            "customer": customer,
            "sales": sales
        }
```

## Using Repositories with FastAPI

The recommended approach is to use dependency injection in FastAPI endpoints:

```python
# Repository dependencies
def get_customer_repository(db: Session = Depends(get_db)):
    encryption_service = get_encryption_service()
    return CustomerRepository(db, encryption_service)

# Endpoint using repository
@app.get("/customers/{customer_id}")
def get_customer(
    customer_id: int,
    customer_repo: CustomerRepository = Depends(get_customer_repository)
):
    customer = customer_repo.get_by_id(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer
```

## Testing Repositories

For unit testing, use an in-memory SQLite database:

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

## Conclusion

The repository pattern in HideSync provides a structured, maintainable approach to data access. By following this implementation guide, you can effectively work with the repository layer, extend it with new functionality, and ensure robust data handling throughout the application.

For any specific repository implementation details, refer to the docstrings and code comments in the respective repository files.