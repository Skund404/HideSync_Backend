# Product Domain Documentation

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Model](#data-model)
4. [API Endpoints](#api-endpoints)
5. [Service Layer](#service-layer)
6. [Repository Layer](#repository-layer)
7. [Business Rules](#business-rules)
8. [Unit Conversion System](#unit-conversion-system)
9. [Error Handling](#error-handling)
10. [Integration Points](#integration-points)
11. [Usage Examples](#usage-examples)
12. [Troubleshooting](#troubleshooting)

---

## Overview

The Product domain manages finished products available for sale or use in projects within the ERP system. It provides comprehensive product lifecycle management including creation, updates, inventory tracking, cost calculation, and sales analytics.

### Key Features
- ✅ **Product CRUD Operations** - Create, read, update, delete products
- ✅ **Inventory Integration** - One-to-one relationship with inventory tracking
- ✅ **Cost Calculation** - Automatic cost breakdown based on material requirements
- ✅ **Unit Conversion** - Smart unit conversion for accurate cost calculations
- ✅ **Advanced Filtering** - Search and filter by multiple criteria
- ✅ **SKU Management** - Automatic SKU generation with collision detection
- ✅ **Event Publishing** - Domain events for integration with other systems
- ✅ **Audit Trail** - Comprehensive logging and tracking

---

## Architecture

The Product domain follows a layered architecture pattern:

```
┌─────────────────────┐
│   API Endpoints     │  ← REST API Layer
├─────────────────────┤
│   Service Layer     │  ← Business Logic
├─────────────────────┤
│  Repository Layer   │  ← Data Access
├─────────────────────┤
│    Data Model       │  ← Entity Definition
└─────────────────────┘
```

### Components
- **Product Model** (`app/db/models/product.py`)
- **Product Service** (`app/services/product_service.py`)
- **Product Repository** (`app/repositories/product_repository.py`)
- **Product API** (`app/api/v1/endpoints/products.py`)
- **Unit Converter** (`app/utils/unit_converter.py`)

---

## Data Model

### Product Entity

```python
class Product(AbstractBase, ValidationMixin, CostingMixin, TimestampMixin):
    """Represents finished products available for sale or use in projects."""
```

#### Core Fields

| Field | Type | Description | Required |
|-------|------|-------------|----------|
| `id` | Integer | Primary key | Yes |
| `name` | String(255) | Product name | Yes |
| `sku` | String(100) | Stock Keeping Unit (unique) | Yes |
| `product_type` | Enum(ProjectType) | Product category | No |
| `description` | Text | Detailed description | No |

#### Attributes

| Field | Type | Description |
|-------|------|-------------|
| `materials` | JSON | List of material IDs or details |
| `color` | String(50) | Product color |
| `dimensions` | String(100) | Physical dimensions |
| `weight` | Float | Product weight |
| `thumbnail` | String(255) | Image URL |
| `notes` | Text | Additional notes |
| `batch_number` | String(50) | Manufacturing batch |
| `customizations` | JSON | Custom attributes |

#### Inventory Control

| Field | Type | Description |
|-------|------|-------------|
| `reorder_point` | Integer | Minimum stock level trigger |

#### Pricing

| Field | Type | Description |
|-------|------|-------------|
| `cost_breakdown` | JSON | Detailed cost analysis |
| `total_cost` | Float | Total production cost |
| `selling_price` | Float | Retail price |

#### Sales Metrics

| Field | Type | Description |
|-------|------|-------------|
| `last_sold` | DateTime | Last sale timestamp |
| `sales_velocity` | Float | Sales rate metric |

#### Relationships

| Relationship | Type | Description |
|-------------|------|-------------|
| `inventory` | One-to-One | Associated inventory record |
| `pattern` | Many-to-One | Manufacturing pattern |
| `project` | Many-to-One | Associated project |
| `sale_items` | One-to-Many | Sales transaction items |

### Calculated Properties

#### `profit_margin`
```python
@hybrid_property
def profit_margin(self) -> Optional[float]:
    """Calculate profit margin percentage: (Price - Cost) / Price"""
```

Returns the profit margin as a percentage, or `None` if calculation isn't possible.

---

## API Endpoints

Base URL: `/api/v1/products`

### Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List products with filtering |
| POST | `/` | Create new product |
| GET | `/{id}` | Get product by ID |
| PUT | `/{id}` | Update product |
| DELETE | `/{id}` | Delete product |
| GET | `/by-sku/{sku}` | Get product by SKU |
| POST | `/{id}/calculate-cost` | Trigger cost calculation |

### 1. List Products

**GET** `/api/v1/products`

Retrieves paginated list of products with advanced filtering capabilities.

#### Query Parameters

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `skip` | int | Records to skip (pagination) | `0` |
| `limit` | int | Max records to return (1-500) | `100` |
| `searchQuery` | string | Search in name/SKU/description | `"leather wallet"` |
| `status` | array | Filter by inventory status | `["in_stock", "low_stock"]` |
| `productType` | array | Filter by product type | `["WALLET", "BAG"]` |
| `storageLocation` | string | Filter by storage location | `"WAREHOUSE_A"` |
| `priceRange[min]` | float | Minimum price filter | `10.00` |
| `priceRange[max]` | float | Maximum price filter | `100.00` |
| `dateAddedRange[from]` | string | Start date (YYYY-MM-DD) | `"2024-01-01"` |
| `dateAddedRange[to]` | string | End date (YYYY-MM-DD) | `"2024-12-31"` |
| `patternId` | int | Filter by pattern ID | `123` |
| `projectId` | int | Filter by project ID | `456` |

#### Response Format

```json
{
  "items": [
    {
      "id": 1,
      "name": "Premium Leather Wallet",
      "sku": "WAL-PREM-A1B2C3",
      "product_type": "wallet",
      "description": "Handcrafted premium leather wallet",
      "quantity": 25.0,
      "status": "in_stock",
      "storage_location": "WAREHOUSE_A",
      "reorder_point": 10,
      "selling_price": 89.99,
      "total_cost": 45.50,
      "profit_margin": 49.44,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:25:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "size": 100,
  "pages": 2
}
```

### 2. Create Product

**POST** `/api/v1/products`

Creates a new product with associated inventory record.

#### Request Body

```json
{
  "name": "Premium Leather Wallet",
  "product_type": "WALLET",
  "description": "Handcrafted premium leather wallet with RFID protection",
  "sku": "WAL-PREM-001",  // Optional - auto-generated if omitted
  "color": "Brown",
  "dimensions": "4.5\" x 3.5\" x 0.5\"",
  "weight": 0.15,
  "selling_price": 89.99,
  "total_cost": 45.50,
  "reorder_point": 10,
  "quantity": 25.0,  // Initial inventory
  "storage_location": "WAREHOUSE_A",
  "pattern_id": 123,
  "materials": [1, 2, 3],  // Material IDs
  "notes": "Premium product line"
}
```

#### Response

Returns the created product with generated ID and SKU (if auto-generated).

### 3. Get Product by ID

**GET** `/api/v1/products/{id}`

Retrieves a single product by its unique ID.

#### Path Parameters
- `id` (required): Product ID

#### Response
Returns complete product information including inventory details.

### 4. Update Product

**PUT** `/api/v1/products/{id}`

Updates an existing product's details. Inventory-related fields (`quantity`, `status`, `storage_location`) must be updated through the inventory endpoints.

#### Request Body
Same as create, but all fields are optional. Only provided fields will be updated.

### 5. Delete Product

**DELETE** `/api/v1/products/{id}`

Deletes a product and its associated inventory record.

#### Business Rules
- Cannot delete products with active sales
- Cascades to delete associated inventory
- Publishes `ProductDeleted` event

### 6. Get Product by SKU

**GET** `/api/v1/products/by-sku/{sku}`

Retrieves a product by its unique SKU.

#### Path Parameters
- `sku` (required): Product SKU

### 7. Calculate Product Cost

**POST** `/api/v1/products/{id}/calculate-cost`

Triggers recalculation of product cost based on current material prices and pattern requirements.

#### Response
Returns updated product with new cost breakdown.

---

## Service Layer

The `ProductService` class handles all business logic for product management.

### Key Methods

#### `create_product(product_in: ProductCreate, user_id: Optional[int]) -> Product`

Creates a new product with the following workflow:
1. Validates input data
2. Generates SKU if not provided (with collision detection)
3. Creates product record
4. Creates associated inventory record via `InventoryService`
5. Publishes `ProductCreated` event
6. Returns product with loaded inventory relationship

#### `update_product(product_id: int, product_update: ProductUpdate, user_id: Optional[int]) -> Product`

Updates product details (non-inventory fields):
1. Validates product exists
2. Checks SKU uniqueness if changed
3. Updates product record
4. Re-evaluates inventory status if reorder point changed
5. Publishes `ProductUpdated` event
6. Invalidates cache

#### `delete_product(product_id: int, user_id: Optional[int]) -> bool`

Deletes product and associated records:
1. Validates no active sales exist
2. Deletes inventory record via `InventoryService`
3. Deletes product record
4. Publishes `ProductDeleted` event
5. Invalidates cache

#### `adjust_inventory(product_id: int, quantity_change: float, reason: str, ...) -> Product`

Delegates inventory adjustments to `InventoryService`:
1. Validates product exists
2. Calls `InventoryService.adjust_inventory()`
3. Publishes `ProductInventoryChanged` event
4. Returns updated product

#### `calculate_cost_breakdown(product_id: int) -> Dict[str, Any]`

Calculates detailed cost breakdown:
1. Validates required services are available
2. Fetches pattern material requirements
3. Retrieves material costs and details
4. Performs unit conversions when needed
5. Calculates total costs (material + labor + overhead)
6. Updates product record with results
7. Returns detailed breakdown with any errors

#### `get_low_stock_products() -> List[Dict[str, Any]]`

Returns products below their reorder points with additional metrics:
- Percentage of reorder point
- Units below reorder point
- Sorted by urgency

### Event Publishing

The service publishes domain events for integration:

- `ProductCreated` - New product created
- `ProductUpdated` - Product details changed
- `ProductDeleted` - Product removed
- `ProductInventoryChanged` - Stock level changed

---

## Repository Layer

The `ProductRepository` handles all database operations with advanced querying capabilities.

### Key Features

#### Inventory Integration
- Automatic JOIN with inventory table for status/location filtering
- Eager loading of inventory relationships
- Prevents direct inventory field updates

#### Advanced Filtering
```python
def list_products_paginated(
    skip: int = 0, 
    limit: int = 100, 
    filters: Optional[ProductFilter] = None
) -> Dict[str, Any]
```

Supports complex filtering including:
- Text search across name/SKU/description
- Product type filtering with enum validation
- Inventory status filtering via JOIN
- Storage location filtering
- Price range filtering
- Date range filtering

#### Specialized Queries

- `get_products_by_status()` - Filter by inventory status
- `get_products_by_pattern()` - Filter by pattern ID
- `get_products_by_price_range()` - Filter by price range
- `get_best_selling_products()` - Top performers by sales velocity
- `get_products_low_in_stock()` - Below reorder point
- `get_products_out_of_stock()` - Zero or negative quantity

---

## Business Rules

### SKU Management
1. **Uniqueness**: SKUs must be unique across all products
2. **Auto-generation**: If not provided, system generates format: `{TYPE}-{NAME}-{UUID}`
3. **Collision Detection**: Up to 3 retry attempts for generated SKUs
4. **Validation**: SKUs are normalized (trimmed, uppercase)

### Inventory Integration
1. **One-to-One Relationship**: Each product has exactly one inventory record
2. **Cascade Creation**: Inventory created automatically with product
3. **Cascade Deletion**: Inventory deleted when product is deleted
4. **Delegation**: Stock changes must go through `InventoryService`

### Cost Calculation
1. **Pattern Dependency**: Requires associated pattern with material requirements
2. **Service Dependencies**: Requires `PatternService` and `MaterialService`
3. **Unit Conversion**: Automatic conversion between compatible units
4. **Error Handling**: Continues calculation even with conversion failures
5. **Audit Trail**: All calculations logged with detailed breakdown

### Deletion Constraints
1. **Active Sales**: Cannot delete products with active sale items
2. **Cascade Rules**: Safely removes associated inventory
3. **Event Publishing**: Notifies other systems of deletion

---

## Unit Conversion System

The unit conversion system enables accurate cost calculations when materials use different units than patterns require.

### Supported Unit Categories

#### Length Units
- **Metric**: mm, cm, m, km
- **Imperial**: in, ft, yd
- **Aliases**: Various singular/plural forms

#### Area Units
- **Metric**: mm², cm², m², km²
- **Imperial**: in², ft², yd²
- **Aliases**: sq_mm, square_meter, etc.

#### Volume Units
- **Metric**: ml, cl, dl, l, m³
- **Imperial**: fl_oz, cup, pint, quart, gallon
- **Cubic**: in³, ft³, cm³

#### Weight Units
- **Metric**: mg, g, kg, ton
- **Imperial**: oz, lb, ton
- **Aliases**: Various forms

#### Count Units
- **Basic**: piece, item, unit, each
- **Groups**: dozen, pair, set

### Conversion Logic

```python
# Example: Pattern requires 2.5 feet of leather
# Material cost is $15.00 per meter
quantity_needed = 2.5
unit_needed = "feet"
material_cost_per_unit = 15.00
material_unit = "meter"

# System converts: 2.5 feet = 0.762 meters
# Final cost: 0.762 * $15.00 = $11.43
```

### Error Handling
1. **Incompatible Units**: Length vs Weight → Error with suggestions
2. **Unknown Units**: Custom units → Error with similar unit suggestions
3. **Conversion Failures**: Fallback to multiplier 1.0 with warning
4. **System Errors**: Import/runtime errors → Fallback with error logging

---

## Error Handling

### Exception Hierarchy

```
Exception
├── EntityNotFoundException     # Resource not found
├── ValidationException        # Input validation failed
├── BusinessRuleException     # Business logic violation
└── HideSyncException        # Internal system error
```

### API Error Responses

#### 400 Bad Request - Validation Error
```json
{
  "detail": {
    "name": ["Product name is required"],
    "sku": ["SKU must be unique"]
  }
}
```

#### 404 Not Found - Entity Not Found
```json
{
  "detail": "Product with ID 123 not found."
}
```

#### 409 Conflict - Business Rule Violation
```json
{
  "detail": "Cannot delete product with active sales"
}
```

#### 500 Internal Server Error - System Error
```json
{
  "detail": "An unexpected error occurred while processing the request."
}
```

### Logging Strategy

- **INFO**: Normal operations, successful transactions
- **WARNING**: Business rule violations, validation failures
- **ERROR**: System errors, database failures, integration issues
- **DEBUG**: Detailed operation traces, performance metrics

---

## Integration Points

### Inventory Service
- **Create**: Product creation triggers inventory creation
- **Update**: Inventory adjustments delegated to inventory service
- **Delete**: Product deletion triggers inventory deletion
- **Status**: Inventory status affects product availability

### Pattern Service
- **Cost Calculation**: Fetches material requirements from patterns
- **Relationships**: Products linked to manufacturing patterns

### Material Service
- **Cost Calculation**: Retrieves current material costs and units
- **Validation**: Validates material references in patterns

### Event Bus
- **Domain Events**: Publishes product lifecycle events
- **Integration**: Enables loose coupling with other domains

### Cache Service
- **Performance**: Caches frequently accessed product data
- **Invalidation**: Smart cache invalidation on updates

---

## Usage Examples

### Creating a Product with Auto-Generated SKU

```python
# Service layer
product_data = ProductCreate(
    name="Premium Leather Wallet",
    product_type="WALLET",
    description="Handcrafted with Italian leather",
    selling_price=89.99,
    quantity=25.0,
    storage_location="WAREHOUSE_A"
    # SKU omitted - will be auto-generated
)

product = product_service.create_product(product_data, user_id=1)
print(f"Created product with SKU: {product.sku}")
# Output: Created product with SKU: WAL-PREM-A1B2C3
```

### Advanced Product Search

```python
# Repository layer
filters = ProductFilter(
    searchQuery="leather",
    status=["in_stock", "low_stock"],
    productType=["WALLET", "BAG"],
    priceRange={"min": 50.0, "max": 200.0},
    storageLocation="WAREHOUSE_A"
)

results = product_repository.list_products_paginated(
    skip=0, 
    limit=20, 
    filters=filters
)

print(f"Found {results['total']} matching products")
```

### Cost Calculation with Unit Conversion

```python
# Automatically handles unit conversions
cost_breakdown = product_service.calculate_cost_breakdown(product_id=123)

print(f"Total cost: ${cost_breakdown['total_calculated_cost']}")
print(f"Material costs: ${cost_breakdown['material_costs']}")

# Check for any unit conversion issues
if cost_breakdown['errors']:
    print("Cost calculation warnings:")
    for error in cost_breakdown['errors']:
        print(f"  - {error}")
```

### Bulk Operations

```python
# Get all low-stock products
low_stock = product_service.get_low_stock_products()

for product in low_stock:
    print(f"{product['name']}: {product['quantity']} units")
    print(f"  Reorder point: {product['reorder_point']}")
    print(f"  Urgency: {product['percent_of_reorder']}%")
```

---

## Troubleshooting

### Common Issues

#### 1. SKU Generation Failures
**Problem**: `HideSyncException: Failed to generate a unique SKU due to collisions`

**Cause**: Too many products with similar names causing SKU collisions

**Solution**:
- Use more descriptive product names
- Consider manual SKU assignment for bulk imports
- Check for duplicate/similar product names

#### 2. Unit Conversion Errors
**Problem**: "Unit conversion failed" in cost calculation

**Cause**: Incompatible or unknown units between pattern and materials

**Solution**:
- Standardize units across patterns and materials
- Check unit spelling and format
- Use suggested compatible units from error messages

#### 3. Inventory Relationship Missing
**Problem**: Product created but inventory data missing in responses

**Cause**: Inventory relationship not loaded or creation failed

**Solution**:
- Check `InventoryService` is properly injected
- Verify database transaction completed successfully
- Use `load_inventory=True` in repository calls

#### 4. Cost Calculation Dependencies
**Problem**: "Required services for cost calculation are not configured"

**Cause**: `PatternService` or `MaterialService` not injected

**Solution**:
- Ensure services are properly configured in dependency injection
- Check service initialization in application startup
- Verify required services are available

### Performance Optimization

#### 1. Database Queries
- Use eager loading for inventory relationships
- Implement proper indexing on frequently queried fields
- Consider query result caching for expensive operations

#### 2. Cost Calculations
- Cache cost breakdown results when materials don't change frequently
- Batch process cost calculations for multiple products
- Consider async processing for expensive calculations

#### 3. API Response Times
- Implement response caching for frequently accessed products
- Use pagination for large result sets
- Consider field selection to reduce payload size

### Monitoring and Metrics

#### Key Metrics to Track
- Product creation/update/deletion rates
- Cost calculation frequency and duration
- Unit conversion success/failure rates
- API response times and error rates
- Cache hit/miss ratios

#### Log Analysis
- Monitor SKU collision rates
- Track unit conversion failures
- Identify slow-performing queries
- Analyze error patterns and frequencies

---

## Conclusion

The Product domain provides a comprehensive solution for product lifecycle management with advanced features like automatic cost calculation, intelligent unit conversion, and seamless inventory integration. The layered architecture ensures maintainability while the robust error handling and logging provide operational visibility.

For additional support or feature requests, please refer to the development team or create an issue in the project repository.