# HideSync Service Layer Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [Service Architecture Overview](#service-architecture-overview)
3. [Service Implementations](#service-implementations)
   - [PlatformIntegrationService](#platformintegrationservice)
   - [PatternService](#patternservice)
   - [ComponentService](#componentservice)
   - [ProductService](#productservice)
4. [Integration Points](#integration-points)
5. [Implementation Patterns](#implementation-patterns)
6. [Example Usage](#example-usage)

## Introduction

This documentation covers the newly implemented service layer components for the HideSync system, a comprehensive ERP solution designed for leathercraft businesses. The implemented services follow a clean architecture pattern with clear separation of concerns, domain-driven design principles, and robust error handling.

Each service implementation adheres to the following principles:
- Transaction management for data consistency
- Domain event publication for loose coupling
- Validation using a common framework
- Caching for performance optimization
- Comprehensive error handling

## Service Architecture Overview

The HideSync service layer sits between the data access layer (repositories) and the presentation layer (API controllers). It encapsulates all business logic and domain rules, ensuring that these rules aren't scattered throughout the application.

Key architectural components include:

- **BaseService**: A foundation class providing common functionality used across all services.
- **Domain Events**: A system for loosely coupled communication between services.
- **Validation Framework**: Ensures data integrity through consistent validation.
- **Transaction Management**: Guarantees atomic operations and data consistency.
- **Service Dependencies**: Services can depend on other services for complex operations.

## Service Implementations

### PlatformIntegrationService

**File:** `services/platform_integration_service.py`

#### Overview
The PlatformIntegrationService manages connections with external e-commerce and marketplace platforms such as Etsy, Shopify, and WooCommerce. It handles authentication, data synchronization, webhook processing, and connection management.

#### Key Components

**Domain Events:**
- `PlatformConnected` - Emitted when a platform connection is established
- `PlatformDisconnected` - Emitted when a platform connection is removed
- `PlatformSyncStarted` - Emitted when a sync operation begins
- `PlatformSyncCompleted` - Emitted when a sync operation completes successfully
- `PlatformSyncFailed` - Emitted when a sync operation fails

**Primary Methods:**
- `create_integration(data)` - Creates a new platform integration with secure credential storage
- `update_integration(integration_id, data)` - Updates an existing integration
- `delete_integration(integration_id)` - Removes an integration
- `sync_platform(integration_id, direction, entity_types)` - Synchronizes data with a platform
- `verify_connection(integration_id)` - Verifies connection status with a platform
- `process_webhook(platform, shop_identifier, data)` - Processes incoming webhooks from platforms
- `get_integration_with_details(integration_id)` - Gets detailed integration information

**Enums:**
- `SyncDirection` - Describes sync direction (IMPORT, EXPORT, BIDIRECTIONAL)
- `SyncEntityType` - Types of entities that can be synchronized (PRODUCT, ORDER, CUSTOMER, INVENTORY)

**Key Features:**
- Secure credential storage with encryption
- Adapter-based platform support for extensibility
- Bidirectional data synchronization
- Webhook processing for real-time updates
- Detailed synchronization event logging

### PatternService

**File:** `services/pattern_service.py`

#### Overview
The PatternService manages leatherworking patterns in the HideSync system. It handles pattern creation, versioning, component association, and file management for SVG/PDF pattern files and thumbnails.

#### Key Components

**Domain Events:**
- `PatternCreated` - Emitted when a new pattern is created
- `PatternUpdated` - Emitted when a pattern is updated
- `PatternDeleted` - Emitted when a pattern is deleted
- `PatternComponentAdded` - Emitted when a component is added to a pattern
- `TemplateCreated` - Emitted when a project template is created

**Primary Methods:**
- `create_pattern(data, file_data)` - Creates a new pattern with optional file data
- `update_pattern(pattern_id, data, file_data, increment_version)` - Updates an existing pattern
- `clone_pattern(pattern_id, new_name, custom_data)` - Creates a new pattern based on an existing one
- `delete_pattern(pattern_id)` - Deletes a pattern
- `get_pattern_with_details(pattern_id)` - Gets a pattern with comprehensive details
- `upload_pattern_file(pattern_id, file_data, file_name, content_type)` - Uploads a pattern file
- `upload_pattern_thumbnail(pattern_id, image_data, file_name, content_type)` - Uploads a pattern thumbnail
- `create_project_template(data)` - Creates a project template from a pattern

**Key Features:**
- Pattern versioning with semantic versioning
- File management for pattern files and thumbnails
- Component association and management
- Search and filtering by project type, skill level, etc.
- Public/private visibility control
- Pattern cloning and customization

### ComponentService

**File:** `services/component_service.py`

#### Overview
The ComponentService manages leathercraft components, which are the building blocks of patterns and projects. It handles component creation, material requirements, positioning, and relationship management.

#### Key Components

**Domain Events:**
- `ComponentCreated` - Emitted when a new component is created
- `ComponentUpdated` - Emitted when a component is updated
- `ComponentDeleted` - Emitted when a component is deleted
- `MaterialRequirementAdded` - Emitted when a material requirement is added
- `MaterialRequirementRemoved` - Emitted when a material requirement is removed

**Primary Methods:**
- `create_component(data)` - Creates a new component
- `update_component(component_id, data)` - Updates an existing component
- `delete_component(component_id)` - Deletes a component
- `get_component_with_details(component_id)` - Gets detailed component information
- `clone_component(component_id, override_data)` - Creates a new component based on an existing one
- `add_material_requirement(component_id, data)` - Adds a material requirement to a component
- `remove_material_requirement(requirement_id)` - Removes a material requirement
- `calculate_material_requirements(pattern_id)` - Calculates total material needs for a pattern

**Key Features:**
- Material requirement specification and management
- Component positioning with JSON attributes
- Relationship management with patterns
- Component duplication and modification
- Material calculation for patterns

### ProductService

**File:** `services/product_service.py`

#### Overview
The ProductService manages leathercraft products, which represent sellable items in the HideSync system. It handles product creation, catalog management, pricing, and inventory tracking.

#### Key Components

**Domain Events:**
- `ProductCreated` - Emitted when a new product is created
- `ProductUpdated` - Emitted when a product is updated
- `ProductDeleted` - Emitted when a product is deleted
- `ProductInventoryChanged` - Emitted when a product's inventory level changes

**Primary Methods:**
- `create_product(data)` - Creates a new product
- `update_product(product_id, data)` - Updates an existing product
- `delete_product(product_id)` - Deletes a product
- `get_product_with_details(product_id)` - Gets detailed product information
- `adjust_inventory(product_id, quantity_change, reason, reference_id)` - Adjusts product inventory
- `get_low_stock_products(threshold_percentage)` - Gets products below reorder threshold
- `calculate_cost_breakdown(product_id)` - Calculates detailed cost breakdown for a product

**Key Features:**
- SKU generation and management
- Pricing and cost calculation
- Inventory tracking with status updates
- Pattern and material association
- Search and filtering by various criteria
- Sales performance tracking

## Integration Points

The implemented services integrate with each other and with other services in the HideSync system:

### PlatformIntegrationService Integrations
- **SaleService** - For importing and synchronizing orders
- **CustomerService** - For importing and synchronizing customers
- **ProductService** - For importing and synchronizing products
- **InventoryService** - For importing and synchronizing inventory

### PatternService Integrations
- **ComponentService** - For managing pattern components
- **FileStorageService** - For storing pattern files and thumbnails
- **ProductService** - For products based on patterns
- **ProjectService** - For creating projects from patterns

### ComponentService Integrations
- **PatternService** - For pattern relationships
- **MaterialService** - For material requirements
- **ProjectService** - For project components

### ProductService Integrations
- **PatternService** - For products based on patterns
- **InventoryService** - For tracking product inventory
- **SaleService** - For tracking product sales
- **MaterialService** - For calculating product costs

## Implementation Patterns

### Transaction Management

All operations that modify data are wrapped in transactions using the `transaction()` context manager from the `BaseService`. This ensures that operations are atomic and can be rolled back in case of errors:

```python
with self.transaction():
    # Operations that modify data
    # If any operation fails, all changes are rolled back
```

### Domain Events

Services publish domain events to notify other parts of the system about important state changes. This enables loose coupling between services:

```python
if self.event_bus:
    self.event_bus.publish(ProductCreated(
        product_id=product.id,
        name=product.name,
        product_type=product.productType,
        user_id=user_id
    ))
```

### Validation

Input validation is performed using the validation framework to ensure data integrity:

```python
@validate_input(validate_product)
def create_product(self, data: Dict[str, Any]) -> Product:
    # Method only executed if validation passes
```

### Caching

Services use the cache service for performance optimization, with proper cache invalidation on data changes:

```python
# Check cache first
if self.cache_service:
    cache_key = f"Product:detail:{product_id}"
    cached = self.cache_service.get(cache_key)
    if cached:
        return cached

# If not in cache, get data and store in cache
# ...

# Invalidate cache on updates
if self.cache_service:
    self.cache_service.invalidate(f"Product:{product_id}")
    self.cache_service.invalidate(f"Product:detail:{product_id}")
```

### Error Handling

Services use specific exception types for different error scenarios, with detailed error messages for troubleshooting:

```python
if not product:
    from app.core.exceptions import EntityNotFoundException
    raise EntityNotFoundException("Product", product_id)
```

## Example Usage

### PlatformIntegrationService

```python
# Create a new Etsy integration
integration_data = {
    "platform": "etsy",
    "shop_name": "MyLeatherShop",
    "credentials": {
        "api_key": "your-api-key",
        "api_secret": "your-api-secret",
        "access_token": "your-access-token",
        "refresh_token": "your-refresh-token"
    },
    "settings": {
        "auto_import_orders": True,
        "sync_inventory": True
    }
}

integration = platform_integration_service.create_integration(integration_data)

# Synchronize orders from Etsy
sync_result = platform_integration_service.sync_platform(
    integration_id=integration.id,
    direction=SyncDirection.IMPORT,
    entity_types=[SyncEntityType.ORDER]
)
```

### PatternService

```python
# Create a new pattern
pattern_data = {
    "name": "Classic Wallet",
    "description": "A traditional bifold wallet design",
    "projectType": "WALLET",
    "skillLevel": "INTERMEDIATE",
    "fileType": "SVG"
}

# Read pattern file
with open("wallet_pattern.svg", "rb") as f:
    file_data = f.read()

pattern = pattern_service.create_pattern(pattern_data, file_data)

# Create a project template from the pattern
template_data = {
    "name": "Classic Wallet Project",
    "projectType": "WALLET",
    "skillLevel": "INTERMEDIATE",
    "patternId": pattern.id,
    "estimatedDuration": 4,
    "estimatedCost": 25.0,
    "components": [
        {
            "name": "Exterior Panel",
            "quantity": 1
        },
        {
            "name": "Card Slots",
            "quantity": 4
        }
    ]
}

template = pattern_service.create_project_template(template_data)
```

### ComponentService

```python
# Create a new component
component_data = {
    "name": "Wallet Exterior",
    "componentType": "PANEL",
    "patternId": pattern_id,
    "description": "Main exterior panel for wallet",
    "pathData": "M0,0 L200,0 L200,100 L0,100 Z"
}

component = component_service.create_component(component_data)

# Add material requirement
requirement_data = {
    "material_id": leather_id,
    "materialType": "LEATHER",
    "quantity": 0.5,
    "unit": "SQUARE_FOOT"
}

component_service.add_material_requirement(component.id, requirement_data)

# Calculate material requirements for a pattern
material_requirements = component_service.calculate_material_requirements(pattern_id)
```

### ProductService

```python
# Create a new product
product_data = {
    "name": "Handcrafted Bifold Wallet",
    "productType": "WALLET",
    "description": "A beautiful handcrafted leather wallet",
    "materials": ["Full Grain Leather", "Waxed Thread"],
    "color": "Tan",
    "patternId": pattern_id,
    "quantity": 5,
    "reorderPoint": 2,
    "sellingPrice": 99.95
}

product = product_service.create_product(product_data)

# Adjust inventory
product_service.adjust_inventory(
    product_id=product.id,
    quantity_change=-1,
    reason="Sale",
    reference_id="sale-123"
)

# Calculate cost breakdown
cost_breakdown = product_service.calculate_cost_breakdown(product.id)
```