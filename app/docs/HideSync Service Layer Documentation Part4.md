# HideSync Service Documentation

This document provides comprehensive information about the services implemented for the HideSync system. Each service follows clean architecture principles with a clear separation of concerns, consistent error handling, and integration with the event system.

## Table of Contents
1. [TimelineTaskService](#timelinetaskservice)
2. [RecurringProjectService](#recurringprojectservice) 
3. [NotificationService](#notificationservice)
4. [ReportService](#reportservice)

---

## TimelineTaskService

### Purpose
The TimelineTaskService manages project timelines and tasks, enabling craftspeople to plan their work, track progress, and meet deadlines. Timeline tasks represent individual work items within a project, with start and end dates, potential dependencies, and progression tracking.

### Key Features
- Task creation, assignment, and management
- Scheduling with start and end dates
- Task dependency and critical path management
- Progress tracking and status updates
- Timeline visualization data preparation
- Due date monitoring and notifications
- Integrated with project management

### Primary Methods

| Method | Description |
| ------ | ----------- |
| `create_task(data)` | Creates a new timeline task with specified parameters |
| `update_task(task_id, data)` | Updates an existing task's properties |
| `delete_task(task_id)` | Deletes a task if not on critical path and has no dependents |
| `update_task_progress(task_id, progress)` | Updates task progress percentage and potentially status |
| `update_task_status(task_id, status)` | Updates a task's status |
| `add_dependency(task_id, dependency_id)` | Adds a dependency relationship between tasks |
| `remove_dependency(task_id, dependency_id)` | Removes a dependency relationship |
| `get_tasks_by_project(project_id)` | Gets all tasks for a specific project |
| `get_task_with_dependencies(task_id)` | Gets a task with its dependencies and dependent tasks |
| `update_project_timeline(project_id)` | Recalculates timeline, critical path, and dates |
| `get_tasks_by_status(project_id, status)` | Gets project tasks with a specific status |
| `get_overdue_tasks(project_id)` | Gets tasks past due date but not completed |
| `get_upcoming_tasks(days, project_id)` | Gets tasks due in the specified timeframe |
| `generate_timeline_visualization_data(project_id)` | Prepares data for timeline visualization |
| `check_due_tasks(days_threshold)` | Checks for tasks due soon or overdue to generate notifications |

### Domain Events
- `TaskCreated`: Emitted when a task is created
- `TaskUpdated`: Emitted when a task is updated
- `TaskDeleted`: Emitted when a task is deleted
- `TaskStatusChanged`: Emitted when a task's status changes
- `TaskProgressUpdated`: Emitted when a task's progress is updated
- `TaskDueSoon`: Emitted when a task is approaching its due date
- `TaskOverdue`: Emitted when a task is past its due date

### Usage Example
```python
# Create a task
task_data = {
    "project_id": "123",
    "name": "Create leather patterns",
    "startDate": "2025-04-01",
    "endDate": "2025-04-05",
    "status": "NOT_STARTED",
    "assignedTo": "craftsperson@example.com"
}
task = timeline_task_service.create_task(task_data)

# Update task progress
updated_task = timeline_task_service.update_task_progress(task.id, 50)

# Add a dependency
timeline_task_service.add_dependency("task-2", "task-1")  # task-2 depends on task-1

# Get project timeline
timeline = timeline_task_service.generate_timeline_visualization_data("project-123")
```

---

## RecurringProjectService

### Purpose
The RecurringProjectService manages recurring or templated projects, allowing craftspeople to create repeating production schedules. This service enables efficient management of cyclical workflows for businesses with regular production cycles, subscription-based offerings, or repeated custom orders.

### Key Features
- Recurring project template creation and management
- Recurrence pattern configuration (daily, weekly, monthly, quarterly, yearly)
- Automatic project generation based on schedules
- Schedule management and adjustments
- Holiday and business hour awareness
- Integration with project management

### Primary Methods

| Method | Description |
| ------ | ----------- |
| `create_recurring_project(data)` | Creates a new recurring project with a recurrence pattern |
| `update_recurring_project(recurring_project_id, data)` | Updates an existing recurring project |
| `update_recurrence_pattern(pattern_id, data)` | Updates a recurrence pattern's configuration |
| `delete_recurring_project(recurring_project_id, delete_generated)` | Deletes a recurring project and optionally its generated instances |
| `get_recurring_project_with_details(recurring_project_id)` | Gets a recurring project with its pattern and generated projects |
| `get_active_recurring_projects()` | Gets all active recurring projects |
| `get_projects_due_for_generation(days_ahead)` | Gets recurring projects due for generation |
| `generate_project(recurring_project_id, scheduled_date)` | Generates a project instance from a recurring project |
| `run_scheduled_generation(days_ahead)` | Runs scheduled generation for all active recurring projects |
| `skip_occurrence(recurring_project_id, reason)` | Skips the next occurrence of a recurring project |
| `activate_recurring_project(recurring_project_id)` | Activates a recurring project |
| `deactivate_recurring_project(recurring_project_id)` | Deactivates a recurring project |
| `get_occurrences_calendar(recurring_project_id, start_date, end_date)` | Gets a calendar of occurrences for a recurring project |

### Domain Events
- `RecurringProjectCreated`: Emitted when a recurring project is created
- `RecurringProjectUpdated`: Emitted when a recurring project is updated
- `RecurringProjectDeleted`: Emitted when a recurring project is deleted
- `RecurrencePatternCreated`: Emitted when a recurrence pattern is created
- `RecurrencePatternUpdated`: Emitted when a recurrence pattern is updated
- `ProjectGenerated`: Emitted when a project is generated from a recurring project
- `GenerationFailed`: Emitted when project generation fails

### Usage Example
```python
# Create a recurring project
project_data = {
    "templateId": "template-123",
    "name": "Monthly Leather Workshop",
    "projectType": "WORKSHOP",
    "skillLevel": "INTERMEDIATE",
    "recurrence_pattern": {
        "frequency": "monthly",
        "interval": 1,
        "startDate": "2025-04-01",
        "dayOfMonth": 15
    }
}
recurring_project = recurring_project_service.create_recurring_project(project_data)

# Generate a project instance
project = recurring_project_service.generate_project(recurring_project["id"])

# Get upcoming occurrences
calendar = recurring_project_service.get_occurrences_calendar(
    recurring_project["id"], 
    datetime.now(), 
    datetime.now() + timedelta(days=90)
)
```

---

## NotificationService

### Purpose
The NotificationService manages system notifications across the HideSync application, ensuring that users receive timely information about important events, alerts, and system updates. This service enables effective communication about project statuses, inventory alerts, upcoming deadlines, and system events.

### Key Features
- Notification creation and management
- Multiple notification types (system, project, inventory, etc.)
- Priority levels for importance indication
- Delivery through multiple channels (in-app, email, SMS)
- User preference management
- Notification grouping and batching
- Read/unread status tracking
- Notification retention and archiving

### Primary Methods

| Method | Description |
| ------ | ----------- |
| `create_notification(data)` | Creates a new notification with delivery through specified channels |
| `create_bulk_notifications(template, user_ids)` | Creates notifications for multiple users based on a template |
| `get_user_notifications(user_id, include_read, limit, offset)` | Gets notifications for a specific user |
| `mark_as_read(notification_id)` | Marks a notification as read |
| `mark_all_as_read(user_id)` | Marks all of a user's notifications as read |
| `archive_notification(notification_id)` | Archives a notification |
| `delete_notification(notification_id)` | Deletes a notification |
| `get_notification_stats(user_id)` | Gets notification statistics for a user |
| `get_user_preferences(user_id)` | Gets notification preferences for a user |
| `update_user_preferences(user_id, preferences)` | Updates notification preferences for a user |
| `clean_old_notifications(days_threshold)` | Cleans up old notifications |

### Domain Events
- `NotificationCreated`: Emitted when a notification is created
- `NotificationSent`: Emitted when a notification is sent through a delivery channel
- `NotificationRead`: Emitted when a notification is marked as read
- `NotificationArchived`: Emitted when a notification is archived

### Usage Example
```python
# Create a notification
notification_data = {
    "type": "PROJECT_DUE_SOON",
    "title": "Project Due Tomorrow",
    "message": "Your custom wallet project is due tomorrow.",
    "user_id": "user-123",
    "priority": "HIGH",
    "link": "/projects/proj-456",
    "delivery_channels": ["in_app", "email"]
}
notification = notification_service.create_notification(notification_data)

# Mark as read
notification_service.mark_as_read(notification["id"])

# Get user notifications
notifications = notification_service.get_user_notifications("user-123", include_read=False)

# Update preferences
preferences = {
    "delivery_channels": {
        "in_app": True,
        "email": True,
        "sms": False
    },
    "notification_types": {
        "project_updates": True,
        "inventory_alerts": True
    }
}
notification_service.update_user_preferences("user-123", preferences)
```

---

## ReportService

### Purpose
The ReportService generates comprehensive reports and analytics across different areas of the HideSync system. It provides critical business intelligence to help craftspeople make informed decisions about their operations, identify trends, and optimize their workflows.

### Key Features
- Standard report templates for common business needs
- Custom report creation with configurable parameters
- Multiple output formats (PDF, CSV, Excel, JSON, HTML)
- Scheduled report generation
- Data visualization preparation
- Historical report storage and retrieval
- Filtering and sorting capabilities
- Aggregation and summary statistics

### Primary Methods

| Method | Description |
| ------ | ----------- |
| `generate_report(report_type, parameters, format, include_metadata)` | Generates a report with specified parameters and format |
| `get_report(report_id, include_data)` | Gets a previously generated report |
| `download_report(report_id)` | Downloads a report file |
| `get_available_reports()` | Gets list of available report types |
| `get_recent_reports(limit)` | Gets list of recently generated reports |
| `schedule_report(report_type, parameters, schedule_settings)` | Schedules a report for automatic generation |
| `run_scheduled_reports()` | Runs scheduled reports that are due |

### Standard Report Types
- `inventory_status`: Current inventory levels, low stock alerts, and valuation
- `sales_analysis`: Sales performance, trends, and product popularity
- `project_performance`: Project timelines, status distribution, and completion metrics
- `materials_usage`: Material consumption, waste tracking, and cost analysis
- `financial_summary`: Revenue, expenses, profit margins, and financial trends
- `customer_analysis`: Customer segmentation, ordering patterns, and lifetime value
- `production_efficiency`: Production time analysis, bottlenecks, and efficiency metrics
- `supplier_performance`: Supplier reliability, pricing trends, and delivery performance
- `custom`: User-defined custom reports

### Domain Events
- `ReportGenerated`: Emitted when a report is generated
- `ReportScheduled`: Emitted when a report is scheduled

### Usage Example
```python
# Generate an inventory status report
report = report_service.generate_report(
    report_type="inventory_status",
    parameters={
        "low_stock_only": True,
        "material_type": "LEATHER"
    },
    format="excel"
)

# Download the report
file_data, filename, content_type = report_service.download_report(report["metadata"]["id"])

# Schedule a weekly sales report
schedule = report_service.schedule_report(
    report_type="sales_analysis",
    parameters={
        "group_by": "product"
    },
    schedule_settings={
        "recurrence": "weekly",
        "day_of_week": 1,  # Monday
        "format": "pdf",
        "recipients": ["manager@example.com"]
    }
)
```

---

## Integration Between Services

The services in HideSync are designed to work together seamlessly through well-defined interfaces and the event system:

1. **TimelineTaskService** integrates with:
   - ProjectService for project data and updates
   - NotificationService for task reminders and overdue alerts

2. **RecurringProjectService** integrates with:
   - ProjectService for creating project instances
   - TemplateService for project templates
   - TimelineTaskService indirectly through generated projects

3. **NotificationService** integrates with:
   - All services that generate events requiring user notifications
   - EmailService and SMSService for external communication
   - UserService for preferences and contact information

4. **ReportService** integrates with:
   - Nearly all other services to gather data for reports
   - FileStorageService for storing generated reports
   - NotificationService for scheduled report delivery

## Best Practices

1. **Transaction Management**
   - Always use the `transaction()` context manager for operations that modify data
   - Group related operations in a single transaction for atomicity

2. **Event Publishing**
   - Publish domain events for significant state changes
   - Keep event payloads focused and relevant
   - Don't rely on event handlers for critical business logic

3. **Validation**
   - Use the validation framework for input validation
   - Validate early and fail fast
   - Use specific validation errors for better error messages

4. **Error Handling**
   - Use appropriate domain-specific exceptions
   - Include enough context in exceptions for debugging
   - Don't expose sensitive information in error messages

5. **Caching**
   - Use caching for frequently accessed, rarely changed data
   - Invalidate cache entries when entities change
   - Be mindful of cache TTL for different types of data

6. **Security**
   - Always check user permissions before performing operations
   - Don't trust client-provided IDs without verification
   - Sanitize and validate all user input

7. **Performance**
   - Use pagination for large result sets
   - Optimize database queries for performance-critical operations
   - Batch operations when possible for efficiency