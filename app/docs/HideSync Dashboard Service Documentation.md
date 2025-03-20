# HideSync Dashboard Service Documentation

## Overview

The Dashboard Service is a core component of the HideSync system that aggregates data from multiple services to provide a comprehensive view of business operations, inventory status, project progress, and customer relationships. It's designed to efficiently process and deliver the information needed for effective decision-making and business monitoring.

This service combines data from various domain services including Project, Material, Sale, Purchase, and Customer to create consolidated summaries and detailed overviews. It also integrates with the metrics system to expose performance data and track business KPIs.

## Key Features

- **Aggregated summaries** from multiple business domains
- **Detailed domain-specific overviews** for deep analysis
- **Performance metrics collection** for system monitoring
- **Intelligent caching** to minimize database load
- **Error resilience** with partial data returns and detailed error tracking
- **Business KPI tracking** through integrated metrics gauges

## Service Methods

### Core Methods

#### `get_dashboard_summary(use_cache=True)`

Provides a comprehensive summary of the entire system's state, aggregating data from all major domains.

**Parameters:**
- `use_cache` (bool): Whether to use cached data if available (default: True)

**Returns:**
- Dictionary containing summaries for projects, materials, sales, purchases, customers, and recent activity.

**Example Response:**
```python
{
    "timestamp": "2025-03-20T14:30:45.123456",
    "projects": {
        "active_projects": 15,
        "planning_projects": 8,
        "completed_projects": 42,
        "total_projects": 65,
        "completion_rate": 64.6,
        "upcoming_deadlines": [...]
    },
    "materials": {
        "materials_to_reorder": 6,
        "low_stock_materials": [...],
        "material_counts": {...},
        "material_stock_summary": [...]
    },
    "sales": {...},
    "purchases": {...},
    "customers": {...},
    "recent_activity": [...]
}
```

#### `get_performance_metrics()`

Retrieves system performance metrics for administrative monitoring.

**Returns:**
- Dictionary containing HTTP, database, application, and service metrics.

**Example Response:**
```python
{
    "timestamp": "2025-03-20T14:30:45.123456",
    "http": {
        "http.requests.total": 1542,
        "http.requests.duration": {...},
        "http.requests.status.2xx": 1498,
        "http.requests.status.4xx": 42,
        "http.requests.status.5xx": 2
    },
    "database": {
        "db.queries.total": 8902,
        "db.queries.duration": {...},
        "db.errors": 3,
        "db.connections.active": 5
    },
    "application": {...},
    "services": {...}
}
```

### Detailed Overview Methods

#### `get_projects_overview()`

Provides comprehensive data about projects for dashboard visualization.

**Returns:**
- Dictionary containing project statistics, status counts, upcoming deadlines, recently completed projects, and projects by type.

#### `get_inventory_overview()`

Delivers detailed information about inventory status and material usage.

**Returns:**
- Dictionary containing materials to reorder, low stock materials, material counts by type and status, most used materials, recently received materials, and stock distribution.

#### `get_sales_overview()`

Provides sales analysis data for dashboards and reporting.

**Returns:**
- Dictionary containing order counts, status distributions, payment information, sales trends, and top products.

#### `get_customers_overview()`

Delivers customer analytics and segmentation data.

**Returns:**
- Dictionary containing customer counts, status distribution, tier distribution, recently active customers, new customers, and growth patterns.

## Usage Examples

### Basic Dashboard Summary

```python
# Get dashboard service from service factory
dashboard_service = service_factory.get_dashboard_service()

# Get dashboard summary
summary = dashboard_service.get_dashboard_summary()

# Access specific sections
active_projects = summary["projects"]["active_projects"]
materials_to_reorder = summary["materials"]["materials_to_reorder"]
pending_orders = summary["sales"]["pending_orders"]
```

### Using Specific Overviews

```python
# Get detailed inventory information
inventory_data = dashboard_service.get_inventory_overview()

# Get customer analytics
customers_data = dashboard_service.get_customers_overview()

# Use data for visualization or analysis
low_stock_items = inventory_data["low_stock_materials"]
customer_growth = customers_data["customer_growth"]
```

### Bypassing Cache for Fresh Data

```python
# Force fresh data (bypass cache) for real-time dashboard
fresh_summary = dashboard_service.get_dashboard_summary(use_cache=False)
```

### Getting Performance Metrics

```python
# Get system performance data for admin panel
performance_data = dashboard_service.get_performance_metrics()

# Check database metrics
db_query_count = performance_data["database"]["db.queries.total"]
db_errors = performance_data["database"]["db.errors"]
```

## Exposed Metrics

The Dashboard Service exposes the following metrics that can be used for monitoring and alerting:

### Business Metrics

- **`dashboard.active_projects`**: Gauge tracking the number of active projects
- **`dashboard.pending_orders`**: Gauge tracking the number of pending orders
- **`dashboard.low_stock_materials`**: Gauge tracking the number of materials with low stock
- **`dashboard.total_customers`**: Gauge tracking the total number of customers
- **`dashboard.monthly_revenue`**: Gauge tracking the monthly revenue amount

### Performance Metrics

- **`dashboard.requests.total`**: Counter tracking total dashboard data requests
- **`dashboard.generation_time`**: Timer measuring dashboard data generation time
- **`dashboard.errors.*`**: Counters tracking different error types by component

### Execution Time Metrics

- **`dashboard_summary`**: Execution time for the main dashboard summary
- **`projects_overview`**: Execution time for projects overview
- **`inventory_overview`**: Execution time for inventory overview
- **`sales_overview`**: Execution time for sales overview
- **`customers_overview`**: Execution time for customers overview
- **`performance_metrics`**: Execution time for retrieving performance metrics

## Performance Considerations

### Caching Strategy

The Dashboard Service uses an intelligent caching strategy to reduce database load while maintaining data freshness:

- Main dashboard summary data is cached for 5 minutes (TTL: 300 seconds)
- Detailed overviews are cached for 10 minutes (TTL: 600 seconds)
- Performance metrics are not cached to ensure real-time monitoring
- You can bypass caching by passing `use_cache=False` to methods

### Optimizations

- The service uses targeted database queries to minimize joins and processing
- Sub-summaries are processed in parallel where possible
- Error handling is designed to return partial data when some components fail
- Heavy computations are measured and optimized over time

## Best Practices

1. **Use the cache appropriately**
   - Keep the default caching for regular dashboard refreshes
   - Disable caching only for critical real-time needs
   - Consider staggered cache TTLs for different components

2. **Monitor dashboard metrics**
   - Track execution times to identify performance bottlenecks
   - Monitor error rates to identify failing components
   - Set alerts on business KPIs (like low stock materials)

3. **Handle errors gracefully in UI**
   - The service returns partial data with error indicators when components fail
   - Your UI should display available data while showing appropriate error messages

4. **Extend responsibly**
   - When adding new dashboard components, follow the established pattern
   - Add appropriate metrics for new functionality
   - Implement intelligent caching for new data sources

## Troubleshooting

### Common Issues

#### Slow Dashboard Generation

**Symptoms:**
- Dashboard takes several seconds to load
- `dashboard.generation_time` metrics show high values

**Solutions:**
- Check database query performance on individual services
- Verify that caching is working correctly
- Consider increasing cache TTLs for less frequently changing data
- Look for specific slow components in execution time metrics

#### Stale Data

**Symptoms:**
- Dashboard shows outdated information
- Changes in system aren't reflected in dashboard

**Solutions:**
- Verify cache service is functioning correctly
- Check if cache invalidation is happening properly on data changes
- Consider decreasing cache TTLs for critical data
- Use `use_cache=False` to verify fresh data behavior

#### Missing Data Sections

**Symptoms:**
- Some sections of dashboard are missing
- Error messages appear in specific components

**Solutions:**
- Check logs for specific error messages
- Verify that all required services are available
- Look at `dashboard.errors.*` metrics to identify failing components
- Check that service dependencies are correctly configured

## Integration with Other Services

The Dashboard Service integrates with the following services:

- **Project Service**: For project status, deadlines, and completion rates
- **Material Service**: For inventory levels, low stock alerts, and material usage
- **Sale Service**: For order status, revenue data, and product performance
- **Purchase Service**: For purchase orders, supplier deliveries, and spending
- **Customer Service**: For customer counts, activity, and segmentation
- **Cache Service**: For efficient data caching and performance
- **Metrics Service**: For performance monitoring and business KPI tracking

## Extending the Dashboard Service

When extending the Dashboard Service with new functionality:

1. Create a new method for detailed domain data (e.g., `get_suppliers_overview()`)
2. Update the `get_dashboard_summary()` method to include a summary of the new domain
3. Add appropriate caching with suitable TTLs
4. Create metrics to track business KPIs related to the new domain
5. Implement execution time tracking with the `@record_execution_time` decorator
6. Add proper error handling and logging
7. Update UI components to display the new data

## Conclusion

The Dashboard Service is a critical component of the HideSync system that provides business intelligence and system monitoring capabilities. By efficiently aggregating and processing data from multiple services, it enables effective decision-making while maintaining system performance. The integrated metrics system allows for ongoing monitoring and optimization of both business KPIs and technical performance.