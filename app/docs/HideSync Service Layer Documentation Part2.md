# HideSync Service Layer Implementation Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [Service Implementations](#service-implementations)
   - [SaleService](#saleservice)
   - [SupplierService](#supplierservice)
   - [StorageLocationService](#storagelocationservice)
   - [InventoryService](#inventoryservice)
3. [Supporting Models](#supporting-models)
   - [SupplierHistory](#supplierhistory)
   - [SupplierRating](#supplierrating)
4. [Supporting Repositories](#supporting-repositories)
   - [SupplierHistoryRepository](#supplierhistoryrepository)
   - [SupplierRatingRepository](#supplierratingrepository)
5. [Integration Points](#integration-points)
6. [Design Patterns and Considerations](#design-patterns-and-considerations)

## Introduction

This documentation describes the implementation of several key service components for the HideSync system, a comprehensive ERP solution designed for leathercraft businesses. The implemented services follow a clean architecture pattern with clear separation of concerns, domain-driven design principles, and robust error handling.

Each service implementation adheres to the following principles:
- Transaction management for data consistency
- Domain event publication for loose coupling
- Validation using a common framework
- Caching for performance optimization
- Comprehensive error handling

## Service Implementations

### SaleService

**File:** `sale_service.py`

#### Overview
The SaleService manages the entire sales process in the HideSync system. It handles order creation, payment processing, fulfillment, and reporting. It serves as the central component for all sales-related business logic.

#### Key Components

**Domain Events:**
- `SaleCreated` - Emitted when a new sale is created
- `SaleStatusChanged` - Emitted when a sale's status changes
- `PaymentStatusChanged` - Emitted when payment status changes
- `SaleItemAdded` - Emitted when an item is added to a sale
- `FulfillmentStatusChanged` - Emitted when fulfillment status changes

**Primary Methods:**
- `create_sale(data)` - Creates a new sale with validation and initial status
- `add_sale_item(sale_id, item_data)` - Adds an item to an existing sale
- `update_sale_status(sale_id, new_status, comments)` - Updates the status of a sale with workflow validation
- `update_payment_status(sale_id, new_status, amount, transaction_id, payment_method)` - Processes payments and payment status changes
- `update_fulfillment_status(sale_id, new_status, tracking_number, shipping_provider)` - Updates the fulfillment status
- `fulfill_sale(sale_id, tracking_number, shipping_provider)` - Convenience method to mark a sale as fulfilled
- `get_sale_with_items(sale_id)` - Gets a sale with its items and related data
- `get_sales_metrics(start_date, end_date)` - Calculates sales metrics for a date range

**Helper Methods:**
- `_calculate_totals(sale_data, items_data)` - Calculates sale totals based on items
- `_update_sale_totals(sale_id)` - Updates totals when items change
- `_validate_status_transition(current_status, new_status)` - Validates status workflow changes
- `_record_status_change()` - Records status changes for audit
- `_record_payment_transaction()` - Records payment transactions
- `_allocate_inventory_for_sale()` - Allocates inventory for a sale
- `_create_project_for_sale()` - Creates a project for custom orders

#### Usage Example

```python
# Create a new sale
sale_data = {
    "customer_id": 123,
    "items": [
        {
            "product_id": 456,
            "quantity": 1,
            "price": 149.99,
            "name": "Custom Wallet"
        }
    ]
}

sale = sale_service.create_sale(sale_data)

# Update payment status for deposit
sale_service.update_payment_status(
    sale_id=sale.id,
    new_status="DEPOSIT_PAID",
    amount=75.00,
    payment_method="CREDIT_CARD"
)

# Mark as shipped
sale_service.update_fulfillment_status(
    sale_id=sale.id,
    new_status="SHIPPED",
    tracking_number="1Z999AA10123456784",
    shipping_provider="UPS"
)
```

### SupplierService

**File:** `supplier_service.py`

#### Overview
The SupplierService manages supplier relationships in the HideSync system. It handles supplier information, ratings, status changes, and provides analytics on supplier performance. This service is essential for material sourcing and purchase management.

#### Key Components

**Domain Events:**
- `SupplierCreated` - Emitted when a new supplier is created
- `SupplierUpdated` - Emitted when supplier details are updated
- `SupplierStatusChanged` - Emitted when a supplier's status changes
- `SupplierRatingChanged` - Emitted when a supplier's rating is changed

**Primary Methods:**
- `create_supplier(data)` - Creates a new supplier with validation
- `update_supplier(supplier_id, data)` - Updates an existing supplier
- `change_supplier_status(supplier_id, new_status, reason)` - Changes supplier status with workflow validation
- `update_supplier_rating(supplier_id, rating, comments)` - Updates the supplier's rating
- `get_supplier_with_details(supplier_id)` - Gets a supplier with comprehensive details
- `search_suppliers(query, category, status, min_rating)` - Searches for suppliers by criteria
- `get_top_suppliers(category, limit, min_ratings)` - Gets top-rated suppliers
- `get_supplier_statistics()` - Gets statistical information about suppliers

**Helper Methods:**
- `_supplier_exists_by_name()` and `_supplier_exists_by_email()` - Check for duplicates
- `_validate_status_transition()` - Validates status workflow changes
- `_record_status_change()` - Records status changes using SupplierHistoryRepository
- `_record_rating_change()` - Records rating changes using SupplierRatingRepository
- `_get_purchase_history()` - Gets purchase history from PurchaseService
- `_calculate_purchase_metrics()` - Calculates metrics based on purchase history
- `_get_supplied_materials()` - Gets materials supplied by the supplier
- `_get_category_distribution()` and `_get_rating_distribution()` - Calculate distributions
- `_calculate_average_rating()` - Calculates the average rating across suppliers
- `_get_supplier_rating_metrics()` - Gets detailed rating metrics for a supplier

#### Usage Example

```python
# Create a new supplier
supplier_data = {
    "name": "Premium Leather Co.",
    "category": "LEATHER",
    "contact_name": "John Smith",
    "email": "john@premiumleather.com",
    "phone": "555-123-4567",
    "address": "123 Main St, Leather Town, LT 12345"
}

supplier = supplier_service.create_supplier(supplier_data)

# Update supplier status
supplier_service.change_supplier_status(
    supplier_id=supplier.id,
    new_status="PREFERRED",
    reason="Consistently high quality products"
)

# Rate the supplier
supplier_service.update_supplier_rating(
    supplier_id=supplier.id,
    rating=5,
    comments="Excellent leather quality and reliable delivery"
)

# Get detailed information
supplier_details = supplier_service.get_supplier_with_details(supplier.id)
```

### StorageLocationService

**File:** `storage_location_service.py`

#### Overview
The StorageLocationService manages storage locations in the HideSync system. It handles the creation and management of physical storage areas, material assignments to locations, and movement of materials between locations. This service is critical for organizing and tracking the physical inventory.

#### Key Components

**Domain Events:**
- `StorageLocationCreated` - Emitted when a new storage location is created
- `StorageAssignmentCreated` - Emitted when materials are assigned to a location
- `StorageMoveCreated` - Emitted when material is moved between locations
- `StorageSpaceUpdated` - Emitted when storage capacity or utilization is updated

**Primary Methods:**
- `create_storage_location(data)` - Creates a new storage location with validation
- `update_storage_location(location_id, data)` - Updates an existing storage location
- `get_storage_location_with_details(location_id)` - Gets a location with comprehensive details
- `assign_material_to_location(data)` - Assigns a material to a storage location
- `remove_material_from_location(assignment_id)` - Removes a material assignment
- `move_material_between_locations(data)` - Moves material from one location to another
- `get_storage_locations_by_type(location_type)` - Gets locations of a specific type
- `find_suitable_locations(material_type, quantity)` - Finds suitable locations for a material
- `get_storage_utilization_overview()` - Gets overview of storage utilization

**Helper Methods:**
- `_location_exists_by_name_and_section()` - Checks for duplicate locations
- `_create_cells_for_location()` - Creates cells within a storage location
- `_get_cells_for_location()` - Gets cells for a storage location
- `_get_assignments_for_location()` - Gets material assignments for a location
- `_get_recent_moves_for_location()` - Gets recent moves involving a location
- `_calculate_utilization_statistics()` - Calculates space utilization statistics
- `_get_material_assignment()` - Gets the assignment record for a material
- `_has_sufficient_capacity()` - Checks if a location has sufficient capacity

#### Usage Example

```python
# Create a new storage location
location_data = {
    "name": "Cabinet A",
    "type": "CABINET",
    "section": "MAIN_WORKSHOP",
    "description": "Main cabinet for leather storage",
    "capacity": 100,
    "dimensions": {
        "rows": 3,
        "columns": 4
    }
}

location = storage_location_service.create_storage_location(location_data)

# Assign material to location
assignment_data = {
    "material_id": 123,
    "material_type": "LEATHER",
    "storage_id": location.id,
    "quantity": 25.5,
    "notes": "Vegetable tanned leather"
}

assignment = storage_location_service.assign_material_to_location(assignment_data)

# Move material between locations
move_data = {
    "material_id": 123,
    "material_type": "LEATHER",
    "from_storage_id": location.id,
    "to_storage_id": "cabinet-b-id",
    "quantity": 10.0,
    "reason": "Reorganizing storage"
}

move = storage_location_service.move_material_between_locations(move_data)
```

### InventoryService

**File:** `inventory_service.py`

#### Overview
The InventoryService provides a unified view of inventory across all item types in the HideSync system. It manages inventory tracking, adjustments, transfers, and reporting. This service integrates with material, product, and tool services to provide a comprehensive inventory management solution.

#### Key Components

**Domain Events:**
- `InventoryAdjusted` - Emitted when inventory is adjusted
- `LowStockAlert` - Emitted when an item falls below its reorder point
- `InventoryTransferred` - Emitted when inventory is transferred between locations
- `InventoryReconciled` - Emitted when inventory is reconciled with physical count

**Primary Methods:**
- `get_inventory_status(item_type, item_id)` - Gets current inventory status for an item
- `adjust_inventory(item_type, item_id, quantity_change, adjustment_type, reason)` - Adjusts inventory with audit trail
- `transfer_inventory(item_type, item_id, quantity, from_location, to_location, reason)` - Transfers inventory between locations
- `get_low_stock_items(threshold_percentage, item_type)` - Gets items below reorder threshold
- `reconcile_inventory(item_type, item_id, actual_quantity, count_id, notes)` - Reconciles inventory with physical count
- `calculate_inventory_value(as_of_date)` - Calculates the total value of inventory
- `generate_inventory_report(report_type, filters)` - Generates various inventory reports
- `perform_inventory_audit(location_id, item_type)` - Prepares for inventory audit

**Helper Methods:**
- `_get_item_details()` - Gets details for an inventory item from its service
- `_determine_inventory_status()` - Determines status based on quantity and reorder point
- `_check_low_stock()` - Checks if inventory is below reorder point and emits alert
- `_update_item_inventory()` - Updates inventory in the corresponding item service
- `_get_recent_transactions()` - Gets recent transactions for an item
- `_calculate_inventory_metrics()` - Calculates metrics for an inventory item
- `_calculate_days_until_stockout()` - Calculates estimated days until stockout
- `_generate_summary_report()`, `_generate_detail_report()`, `_generate_movement_report()` - Generate different report types

#### Usage Example

```python
# Adjust inventory for a material
inventory_service.adjust_inventory(
    item_type="material",
    item_id=123,
    quantity_change=-2.5,
    adjustment_type="USAGE",
    reason="Used in project #456",
    reference_id="PROJECT-456"
)

# Transfer inventory between locations
inventory_service.transfer_inventory(
    item_type="material",
    item_id=123,
    quantity=5.0,
    from_location="cabinet-a-id",
    to_location="cabinet-b-id",
    reason="Reorganizing storage"
)

# Get low stock items
low_stock = inventory_service.get_low_stock_items(
    threshold_percentage=20.0,
    item_type="material"
)

# Generate inventory report
report = inventory_service.generate_inventory_report(
    report_type="valuation",
    filters={"as_of_date": "2025-03-15T00:00:00"}
)
```

## Supporting Models

### SupplierHistory

**File:** `supplier_history.py`

#### Overview
The SupplierHistory model tracks status changes for suppliers. It records each status change with details about who made the change, when it occurred, and the reason for the change.

#### Key Components

**Fields:**
- `id` - Primary key
- `supplier_id` - Foreign key to the supplier
- `previous_status` - Previous status value
- `new_status` - New status value
- `reason` - Reason for the status change
- `changed_by` - User ID who made the change
- `change_date` - Date and time of the change

**Relationships:**
- `supplier` - Relationship to the Supplier model

### SupplierRating

**File:** `supplier_rating.py`

#### Overview
The SupplierRating model tracks rating changes for suppliers. It records each rating change with the previous and new rating values, as well as optional comments explaining the rating.

#### Key Components

**Fields:**
- `id` - Primary key
- `supplier_id` - Foreign key to the supplier
- `previous_rating` - Previous rating value
- `new_rating` - New rating value
- `comments` - Optional comments explaining the rating
- `rated_by` - User ID who made the rating
- `rating_date` - Date and time of the rating

**Relationships:**
- `supplier` - Relationship to the Supplier model

## Supporting Repositories

### SupplierHistoryRepository

**File:** `supplier_history_repository.py`

#### Overview
The SupplierHistoryRepository provides data access methods for the SupplierHistory model. It extends the BaseRepository with supplier history-specific query methods.

#### Key Methods:
- `get_history_by_supplier(supplier_id, limit)` - Gets status history for a supplier
- `get_recent_history(days, limit)` - Gets recent status changes across all suppliers
- `get_status_changes_by_type(status, limit)` - Gets history records for a specific status change

### SupplierRatingRepository

**File:** `supplier_rating_repository.py`

#### Overview
The SupplierRatingRepository provides data access methods for the SupplierRating model. It extends the BaseRepository with supplier rating-specific query methods.

#### Key Methods:
- `get_ratings_by_supplier(supplier_id, limit)` - Gets rating history for a supplier
- `get_average_rating(supplier_id)` - Calculates the average rating for a supplier
- `get_rating_distribution(supplier_id)` - Gets distribution of ratings for a supplier
- `get_recent_ratings(days, limit)` - Gets recent ratings across all suppliers
- `get_top_rated_suppliers(min_ratings, limit)` - Gets top-rated suppliers

## Integration Points

The implemented services interact with each other and with other services in the HideSync system:

### SaleService Integrations
- **CustomerService** - For customer validation and history tracking
- **InventoryService** - For inventory allocation during sales
- **ProjectService** - For project creation for custom orders
- **ShipmentService** - For handling order fulfillment and shipping

### SupplierService Integrations
- **PurchaseService** - For tracking purchase history from suppliers
- **MaterialService** - For tracking materials provided by suppliers
- **SupplierHistoryRepository** - For storing supplier status history
- **SupplierRatingRepository** - For storing supplier rating history

### StorageLocationService Integrations
- **MaterialService** - For material details and updating storage locations
- **InventoryService** - For inventory tracking in storage locations
- **StorageCellRepository** - For managing cells within storage locations
- **StorageAssignmentRepository** - For tracking material assignments
- **StorageMoveRepository** - For tracking material movements

### InventoryService Integrations
- **MaterialService**, **ProductService**, **ToolService** - For item details
- **StorageService** - For storage location management
- **SupplierService** - For supplier information on reordering
- **InventoryTransactionRepository** - For tracking inventory transactions

## Design Patterns and Considerations

### Patterns Used

1. **Repository Pattern**
   - Abstracts data access operations
   - Provides type-safe queries and operations
   - Enables transaction management and concurrency control

2. **Service Layer Pattern**
   - Implements business logic and workflows
   - Coordinates operations across multiple repositories
   - Provides transactional boundaries

3. **Domain Events**
   - Decouples services through event-based communication
   - Enables asynchronous processing and integration
   - Supports audit trail and history tracking

4. **Unit of Work**
   - Manages transactions with the `transaction()` context manager
   - Ensures atomic operations and rollback on failure
   - Coordinates multiple repository operations

5. **Factory Pattern**
   - Used in item details retrieval and report generation
   - Creates appropriate instances based on type parameters
   - Encapsulates creation logic

### Implementation Considerations

1. **Transaction Management**
   - All operations that modify data are wrapped in transactions
   - Transactions span multiple repository operations when needed
   - Rollbacks occur automatically on exceptions

2. **Validation**
   - Input validation is performed before processing
   - Business rule validation ensures data integrity
   - Status transitions follow defined workflows

3. **Caching**
   - Cache keys are structured for efficient lookups
   - Cache invalidation occurs on data changes
   - TTL values prevent stale data

4. **Error Handling**
   - Specific exception types for different error scenarios
   - Detailed error messages for troubleshooting
   - Error translation for consistent API responses

5. **Security**
   - User context is captured for audit purposes
   - Security checks are performed before operations
   - Sensitive data handling follows best practices