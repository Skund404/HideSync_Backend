# HideSync Service Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [SearchService](#searchservice)
3. [ImportExportService](#importexportservice)
4. [CacheService](#cacheservice)
5. [Integration Between Services](#integration-between-services)
6. [Best Practices](#best-practices)

## Introduction

This document provides comprehensive documentation for the following services in the HideSync system:

1. **SearchService** - Advanced search functionality across entities
2. **ImportExportService** - Data import and export functionality
3. **CacheService** - Caching strategy implementation

These services have been implemented to enhance the HideSync system's capabilities and improve performance. They follow clean architecture principles with clear separation from the data access layer through repository interfaces, and integrate with other core services.

## SearchService

### Purpose

The SearchService provides advanced search functionality across multiple entity types in the HideSync system. It enables users to find information quickly through full-text search, filtering, and relevance-based ranking of results.

### Key Features

- **Full-text search** across multiple entity types
- **Contextual relevance ranking** to prioritize the most relevant results
- **Faceted search results** for drill-down capabilities
- **Filtering** to narrow down search results
- **Cross-entity search** with unified result format
- **Search result highlighting** to show matching terms in context
- **Type-ahead suggestions** for a better user experience
- **Recent and saved searches** for user convenience

### Core Methods

| Method | Description |
|--------|-------------|
| `search(query, entity_types, filters, page, page_size, sort_by, sort_dir, highlight)` | Perform search across specified entity types with filtering and pagination |
| `get_suggestions(query, limit)` | Get type-ahead search suggestions based on prefix |
| `get_recent_searches(user_id, limit)` | Get recent searches for a user |
| `save_search(query, entity_types, name, user_id)` | Save a search for later use |
| `get_saved_searches(user_id)` | Get saved searches for a user |
| `delete_saved_search(search_id, user_id)` | Delete a saved search |

### Search Implementation Details

The search service works by:

1. **Breaking down search queries** into terms and tokens
2. **Searching each relevant entity type** through their repositories
3. **Scoring results** based on relevance to the search query
4. **Aggregating results** across entity types
5. **Applying filters and sorting** based on user preferences
6. **Calculating facets** for result categorization
7. **Paginating the results** for better performance

### Usage Examples

#### Basic Search

```python
# Initialize service
search_service = ServiceFactory(session).get_search_service()

# Perform a basic search
results = search_service.search(
    query="leather wallet",
    entity_types=["material", "project", "product"],
    page=1,
    page_size=20
)

# Access results
for item in results["results"]:
    print(f"{item['entity_type']}: {item.get('name')} - Score: {item.get('_score')}")

# Access facets
print(f"Found in: {results['facets']['entity_type']}")
```

#### Advanced Search with Filtering

```python
# Search with filters
filtered_results = search_service.search(
    query="wallet",
    entity_types=["project"],
    filters={
        "project": {
            "status": "IN_PROGRESS",
            "type": "WALLET"
        }
    },
    sort_by="due_date",
    sort_dir="asc",
    highlight=True
)

# Display highlighted results
for item in filtered_results["results"]:
    print(f"{item['name']} - Due: {item.get('due_date')}")
    if "highlights" in item:
        for field, excerpts in item["highlights"].items():
            print(f"  {field}: {excerpts[0]}")
```

#### Saved Searches

```python
# Save a search
saved = search_service.save_search(
    query="low stock leather",
    entity_types=["material"],
    name="Low Stock Leather Materials",
    user_id=current_user.id
)

# Get saved searches
saved_searches = search_service.get_saved_searches(current_user.id)
```

## ImportExportService

### Purpose

The ImportExportService provides comprehensive functionality for importing and exporting data in various formats to and from the HideSync system. It handles data validation, transformation, and batch processing for reliable data exchange.

### Key Features

- **Data import from multiple formats** (CSV, JSON, Excel)
- **Data export to multiple formats** (CSV, JSON, Excel)
- **Batch processing** with error handling for large datasets
- **Data validation and transformation** during import
- **Error reporting** with detailed feedback
- **Template generation** for imports
- **Field mapping** for flexible data integration
- **Progress tracking** for large imports

### Core Methods

| Method | Description |
|--------|-------------|
| `import_data(entity_type, file_data, file_format, options)` | Import data from a file |
| `export_data(entity_type, query_params, options)` | Export data to specified format |
| `generate_import_template(entity_type, format)` | Generate an import template with column headers |
| `save_export(data, filename, content_type)` | Save exported data as a file |

### Import Options

The `import_data` method accepts various options to customize the import process:

- `batch_size`: Number of records to process in each batch
- `update_existing`: Whether to update existing records (default: True)
- `identifier_field`: Field to use for identifying existing records (default: 'id')
- `skip_validation`: Whether to skip validation (default: False)
- `date_format`: Format string for date parsing (default: '%Y-%m-%d')
- `field_mapping`: Dictionary mapping source field names to destination field names
- `enum_fields`: Dictionary mapping field names to enum types
- `date_fields`: List of field names to parse as dates
- `numeric_fields`: List of field names to parse as numbers
- `bool_fields`: List of field names to parse as booleans

### Usage Examples

#### Importing Materials from CSV

```python
# Initialize service
import_export_service = ServiceFactory(session).get_import_export_service()

# Import materials from CSV
with open('materials.csv', 'rb') as file:
    result = import_export_service.import_data(
        entity_type="material",
        file_data=file,
        file_format="csv",
        options={
            "date_fields": ["purchase_date", "expiration_date"],
            "numeric_fields": ["quantity", "cost", "reorder_point"],
            "field_mapping": {
                "Material Name": "name",
                "Material Type": "material_type",
                "Quantity": "quantity"
            }
        }
    )

# Process result
print(f"Imported {result['successful_rows']} of {result['total_rows']} rows")
print(f"Created: {result['created_count']}, Updated: {result['updated_count']}")

# Check for errors
if result['errors']:
    for error in result['errors']:
        print(f"Error in row {error['row']}: {error['error']}")
```

#### Exporting Customers to JSON

```python
# Set export options
options = ExportOptions(
    format="json",
    excluded_fields=["password", "payment_info", "internal_notes"],
    date_format="%Y-%m-%d"
)

# Export active customers
export_data = import_export_service.export_data(
    entity_type="customer",
    query_params={
        "status": "ACTIVE",
        "created_at_gte": datetime(2023, 1, 1)
    },
    options=options
)

# Save export
if file_service:
    file_metadata = import_export_service.save_export(
        data=json.dumps(export_data),
        filename="active_customers.json",
        content_type="application/json"
    )
    
    print(f"Export saved as {file_metadata['id']}")
```

#### Generating an Import Template

```python
# Generate a template for project imports
template = import_export_service.generate_import_template(
    entity_type="project",
    format="excel"
)

# Save template to file
with open('project_import_template.xlsx', 'wb') as f:
    f.write(template)
```

## CacheService

### Purpose

The CacheService provides a flexible caching infrastructure to improve performance by reducing database queries and computational overhead. It implements multiple caching strategies and backends with consistent key management and expiration.

### Key Features

- **Multiple backend support** (in-memory and Redis)
- **Namespaced cache keys** for organized cache management
- **Time-to-live (TTL)** support for automatic cache expiration
- **Cache invalidation** including key and pattern-based invalidation
- **Cache warming** for predictable performance
- **Cache statistics and monitoring** for optimization
- **Function result caching** through decorators
- **Thread-safe operations**

### Core Methods

| Method | Description |
|--------|-------------|
| `get(key, default)` | Get value from cache |
| `set(key, value, ttl)` | Set value in cache |
| `invalidate(key)` | Invalidate a cache key |
| `invalidate_pattern(pattern)` | Invalidate all keys matching a pattern |
| `get_or_set(key, getter_func, ttl)` | Get value from cache or set it if not present |
| `mget(keys, default)` | Get multiple values from cache |
| `mset(mapping, ttl)` | Set multiple values in cache |
| `exists(key)` | Check if key exists in cache |
| `get_stats()` | Get cache statistics |
| `clear()` | Clear all cached items |
| `warm_cache(keys_values, ttl)` | Warm cache with provided keys and getter functions |

### Cache Backends

The service supports two cache backends:

1. **Memory Cache**: In-memory cache implementation for single-instance deployments
2. **Redis Cache**: Redis-based implementation for distributed deployments

### Usage Examples

#### Basic Caching

```python
# Initialize cache service
cache_service = CacheService(
    config={"default_ttl": 3600, "max_size": 5000},
    backend_type="memory", 
    namespace="hidesync"
)

# Store value in cache
cache_service.set("customer:profile:123", customer_profile, ttl=1800)  # 30 minutes

# Retrieve value from cache
profile = cache_service.get("customer:profile:123")
if profile is None:
    # Cache miss - fetch from database
    profile = customer_service.get_profile(123)
    cache_service.set("customer:profile:123", profile)
```

#### Using the Cached Decorator

```python
from services.cache_service import cached

class MaterialService(BaseService[Material]):
    
    def __init__(self, session, repository=None, cache_service=None):
        super().__init__(session, repository)
        self.cache_service = cache_service
    
    @cached("materials", ttl=1800)
    def get_low_stock_materials(self, threshold_percentage=20.0):
        """This result will be cached for 30 minutes."""
        return self.repository.get_low_stock(threshold_percentage)
```

#### Cache Invalidation

```python
# Invalidate a specific key
cache_service.invalidate("material:123")

# Invalidate all keys matching a pattern
count = cache_service.invalidate_pattern("material:*")
print(f"Invalidated {count} cache entries")
```

#### Cache Warming

```python
# Define data getters
cache_warmers = {
    "dashboard:summary": dashboard_service.get_summary,
    "materials:low_stock": lambda: material_service.get_low_stock_materials(20.0),
    "projects:active": lambda: project_service.list(status="IN_PROGRESS")
}

# Warm the cache
cache_service.warm_cache(cache_warmers)
```

#### Cache Statistics

```python
# Get cache statistics
stats = cache_service.get_stats()

print(f"Cache size: {stats['size']} items")
print(f"Hit rate: {stats['hit_rate'] * 100:.2f}%")
print(f"Memory usage: {stats['memory_usage_mb']:.2f} MB")
```

## Integration Between Services

The services in HideSync are designed to work together seamlessly through well-defined interfaces:

1. **SearchService** integrates with:
   - All entity repositories for data access
   - CacheService for caching frequent searches
   - Security context for user-specific searches and history
   
2. **ImportExportService** integrates with:
   - Service factory to access entity-specific services
   - File storage service for saving exports
   - Event bus for publishing import/export events
   
3. **CacheService** integrates with:
   - All other services that need performance optimization
   - Can be injected into any service that needs caching
   - Available as a standalone service and through decorators

### Example Integration: Dashboard with Search and Cache

```python
class DashboardService:
    def __init__(self, session, cache_service=None, search_service=None):
        self.session = session
        self.cache_service = cache_service
        self.search_service = search_service
        
    def get_dashboard_summary(self):
        """Get comprehensive dashboard summary data."""
        # Try cache first
        if self.cache_service:
            cached = self.cache_service.get("dashboard_summary")
            if cached:
                return cached
                
        # Build dashboard data
        summary = {
            "timestamp": datetime.now().isoformat(),
            "projects": self._get_project_summary(),
            "materials": self._get_material_summary(),
            "sales": self._get_sales_summary(),
            "recent_activity": self._get_recent_activity()
        }
        
        # Cache the result
        if self.cache_service:
            self.cache_service.set("dashboard_summary", summary, ttl=300)  # 5 minutes TTL
            
        return summary
        
    def search_dashboard_entities(self, query):
        """Search across dashboard-relevant entities."""
        if not self.search_service:
            return {"error": "Search service not available"}
            
        return self.search_service.search(
            query=query,
            entity_types=["project", "material", "customer", "sale"],
            page=1,
            page_size=10,
            highlight=True
        )
```

## Best Practices

### SearchService Best Practices

1. **Limit search scope** to relevant entities when possible
2. **Use filters** to narrow down results for better performance
3. **Cache frequent searches** to improve response time
4. **Consider pagination** for large result sets
5. **Use facets** to help users narrow down search results
6. **Implement suggestions** for a better user experience
7. **Index only searchable fields** to improve performance

### ImportExportService Best Practices

1. **Process in batches** for large imports
2. **Use transactions** to ensure data integrity
3. **Validate data** before importing
4. **Provide clear error messages** for failed imports
5. **Map fields explicitly** to handle different schemas
6. **Include headers** in exports for clarity
7. **Test with sample data** before production imports
8. **Limit export scope** to avoid large memory usage

### CacheService Best Practices

1. **Use appropriate TTL values** for different types of data
2. **Cache expensive operations** like complex queries and calculations
3. **Invalidate cache** when underlying data changes
4. **Use namespaces** to organize cache keys
5. **Don't cache sensitive data** without proper encryption
6. **Monitor cache usage** to optimize memory usage
7. **Implement cache warming** for critical data
8. **Use pattern-based invalidation** for related data

### General Best Practices

1. **Error handling** - Provide meaningful error messages
2. **Logging** - Log important operations and errors
3. **Security** - Respect user permissions for all operations
4. **Performance** - Monitor and optimize performance
5. **Testing** - Write comprehensive tests for all services
6. **Documentation** - Keep service documentation up-to-date
7. **Dependency injection** - Use for flexible service configuration

By following these guidelines and using the services as documented, developers can create efficient, scalable, and maintainable applications with the HideSync system.