# HideSync Events System Documentation

## 📋 **Overview**

The HideSync Events System provides a robust, type-safe, and async-capable event bus for handling domain events throughout the application. It supports both synchronous and asynchronous event handling with comprehensive error management and logging.

## 🏗️ **Architecture**

### **Core Components**

1. **DomainEvent**: Base class for all events with automatic ID generation and timestamp
2. **EventBus**: Central hub for publishing and subscribing to events  
3. **Event Categories**: Organized event types for different system domains
4. **Global Event Bus**: Singleton instance for application-wide event handling

### **Key Features**

- ✅ **Type Safety**: Full TypeScript-style type hints and event class hierarchy
- ✅ **Async Support**: Both sync and async event handlers with automatic task management
- ✅ **Error Handling**: Comprehensive exception catching and logging
- ✅ **Thread Safety**: Async locks for concurrent access protection
- ✅ **Performance**: Efficient subscriber management and task execution

---

## 📊 **Event Categories**

### **1. Core Entity Events**

These events track basic CRUD operations across all entities:

```python
# Entity creation
EntityCreatedEvent(entity_id=123, entity_type="Workflow", user_id=456)

# Entity updates with change tracking
EntityUpdatedEvent(
    entity_id=123, 
    entity_type="Workflow", 
    changes={"name": "New Name", "status": "active"},
    user_id=456
)

# Entity deletion
EntityDeletedEvent(entity_id=123, entity_type="Workflow", user_id=456)
```

**Usage**: Universal tracking of entity lifecycle across all domain models.

### **2. Tool Management Events**

Events specific to tool lifecycle and maintenance:

```python
# Tool creation and status changes
ToolCreated(tool_id=1, name="Table Saw", category="Power Tools", user_id=123)
ToolStatusChanged(tool_id=1, previous_status="available", new_status="maintenance")

# Maintenance lifecycle
ToolMaintenanceScheduled(maintenance_id=1, tool_id=1, maintenance_type="routine")
ToolMaintenanceCompleted(maintenance_id=1, tool_id=1, completion_date="2024-01-15")

# Check-out/check-in operations
ToolCheckedOut(checkout_id=1, tool_id=1, checked_out_by="John Doe", due_date="2024-01-20")
ToolReturned(checkout_id=1, tool_id=1, has_issues=False)
```

**Usage**: Tool availability tracking, maintenance scheduling, usage analytics.

### **3. Workflow Management Events**

Events for workflow definition and template management:

```python
# Workflow lifecycle
WorkflowCreatedEvent(workflow_id=1, workflow_name="Leather Wallet", is_template=True)
WorkflowUpdatedEvent(workflow_id=1, changes={"description": "Updated instructions"})
WorkflowPublishedEvent(workflow_id=1, visibility="public")
WorkflowDeletedEvent(workflow_id=1, workflow_name="Old Workflow")
```

**Usage**: Template management, workflow versioning, publication tracking.

### **4. Workflow Execution Events**

Events for runtime workflow execution:

```python
# Execution lifecycle
WorkflowStartedEvent(
    workflow_id=1, 
    execution_id=100, 
    workflow_name="Leather Wallet",
    selected_outcome_id=5
)

WorkflowCompletedEvent(
    workflow_id=1, 
    execution_id=100, 
    outcome_id=5,
    total_duration=240.5  # minutes
)

# Execution control
WorkflowPausedEvent(execution_id=100, reason="Material shortage")
WorkflowResumedEvent(execution_id=100)
WorkflowCancelledEvent(execution_id=100, reason="User request")
```

**Usage**: Execution tracking, progress monitoring, completion analytics.

### **5. Workflow Step Events**

Events for individual step execution:

```python
# Step execution
WorkflowStepStartedEvent(
    workflow_id=1, 
    execution_id=100, 
    step_id=10,
    step_name="Cut Leather Pieces",
    step_type="tool"
)

WorkflowStepCompletedEvent(
    workflow_id=1,
    execution_id=100,
    step_id=10,
    actual_duration=15.5  # minutes
)

# Decision making
WorkflowDecisionMadeEvent(
    execution_id=100,
    step_id=15,
    decision_option_id=3,
    decision_text="Use hand stitching method"
)

# Navigation tracking
WorkflowNavigationEvent(
    execution_id=100,
    from_step_id=10,
    to_step_id=11,
    navigation_type="sequential"
)
```

**Usage**: Step-level analytics, time tracking, decision pattern analysis.

### **6. Resource Management Events**

Events for material and tool resource handling:

```python
# Resource reservations
WorkflowResourceReservedEvent(
    workflow_id=1,
    execution_id=100,
    resource_type="material",
    resource_id=50,
    resource_name="Leather - 4oz",
    quantity=2.5
)

WorkflowResourceReleasedEvent(
    execution_id=100,
    resource_type="tool",
    resource_id=25,
    resource_name="Stitching Awl"
)

# Resource availability issues
WorkflowResourceUnavailableEvent(
    workflow_id=1,
    resource_type="material",
    resource_id=50,
    required_quantity=5.0,
    available_quantity=2.0
)
```

**Usage**: Inventory management, resource planning, availability alerts.

### **7. Import/Export Events**

Events for workflow sharing and templates:

```python
# Workflow import/export
WorkflowImportedEvent(
    workflow_id=1,
    workflow_name="Imported Leather Wallet",
    source="preset_library",
    preset_name="basic_leather_project"
)

WorkflowExportedEvent(
    workflow_id=1,
    workflow_name="Custom Woodworking",
    export_format="json"
)
```

**Usage**: Template library management, sharing analytics, import tracking.

### **8. Analytics Events**

Events for progress and milestone tracking:

```python
# Milestone achievements
WorkflowMilestoneReachedEvent(
    workflow_id=1,
    execution_id=100,
    step_id=20,
    milestone_name="Pieces Cut",
    progress_percentage=25.0
)

# Progress updates
WorkflowProgressUpdateEvent(
    workflow_id=1,
    execution_id=100,
    total_steps=12,
    completed_steps=5,
    progress_percentage=41.7,
    estimated_remaining=120.0  # minutes
)
```

**Usage**: Progress dashboards, completion predictions, milestone notifications.

---

## 🚀 **Usage Examples**

### **Basic Event Publishing**

```python
from app.core.events import global_event_bus, WorkflowCreatedEvent

# Synchronous publishing
def create_workflow(workflow_data, user_id):
    workflow = create_workflow_in_db(workflow_data)
    
    # Publish event immediately
    event = WorkflowCreatedEvent(
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        is_template=workflow.is_template,
        user_id=user_id
    )
    global_event_bus.publish(event)
    
    return workflow

# Asynchronous publishing
async def create_workflow_async(workflow_data, user_id):
    workflow = await create_workflow_in_db_async(workflow_data)
    
    # Publish event asynchronously
    event = WorkflowCreatedEvent(
        workflow_id=workflow.id,
        workflow_name=workflow.name,
        user_id=user_id
    )
    await global_event_bus.publish_async(event)
    
    return workflow
```

### **Event Subscription**

```python
from app.core.events import global_event_bus, WorkflowStartedEvent

# Synchronous event handler
def handle_workflow_started(event: WorkflowStartedEvent):
    """Handle workflow start for resource allocation."""
    print(f"Workflow {event.workflow_name} started by user {event.user_id}")
    
    # Reserve required resources
    reserve_workflow_resources(event.workflow_id, event.execution_id)
    
    # Send notification
    send_workflow_notification(event.user_id, f"Started: {event.workflow_name}")

# Subscribe to events
global_event_bus.subscribe(WorkflowStartedEvent, handle_workflow_started)

# Asynchronous event handler
async def handle_workflow_started_async(event: WorkflowStartedEvent):
    """Async handler for workflow start."""
    await reserve_resources_async(event.workflow_id)
    await send_notification_async(event.user_id, event.workflow_name)

# Subscribe to async events
await global_event_bus.subscribe_async(WorkflowStartedEvent, handle_workflow_started_async)
```

### **Multiple Event Handlers**

```python
# Multiple handlers for the same event
def log_workflow_creation(event: WorkflowCreatedEvent):
    """Log workflow creation for audit."""
    logger.info(f"Workflow created: {event.workflow_name} by user {event.user_id}")

def update_analytics(event: WorkflowCreatedEvent):
    """Update workflow creation analytics."""
    increment_workflow_counter(event.user_id, event.is_template)

def send_creation_notification(event: WorkflowCreatedEvent):
    """Send creation notification."""
    if event.is_template:
        notify_template_created(event.workflow_name, event.user_id)

# Subscribe all handlers
global_event_bus.subscribe(WorkflowCreatedEvent, log_workflow_creation)
global_event_bus.subscribe(WorkflowCreatedEvent, update_analytics)
global_event_bus.subscribe(WorkflowCreatedEvent, send_creation_notification)
```

### **Service Integration Example**

```python
class WorkflowService:
    def __init__(self, session: Session):
        self.db_session = session
        
    def create_workflow(self, workflow_data: Dict[str, Any], user_id: int) -> Workflow:
        try:
            # Create workflow in database
            workflow = self._create_workflow_in_db(workflow_data, user_id)
            
            # Publish creation event
            event = WorkflowCreatedEvent(
                workflow_id=workflow.id,
                workflow_name=workflow.name,
                is_template=workflow.is_template,
                user_id=user_id
            )
            global_event_bus.publish(event)
            
            return workflow
            
        except Exception as e:
            # Publish error event if needed
            logger.error(f"Failed to create workflow: {e}")
            raise
    
    def start_execution(self, workflow_id: int, user_id: int) -> WorkflowExecution:
        execution = self._start_execution_in_db(workflow_id, user_id)
        
        # Publish execution started event
        event = WorkflowStartedEvent(
            workflow_id=workflow_id,
            execution_id=execution.id,
            workflow_name=execution.workflow.name,
            user_id=user_id
        )
        global_event_bus.publish(event)
        
        return execution
```

---

## ⚡ **Event Handler Patterns**

### **1. Resource Management Handler**

```python
def handle_resource_events():
    """Set up resource management event handlers."""
    
    @global_event_bus.subscribe
    def reserve_resources(event: WorkflowStartedEvent):
        """Reserve resources when workflow starts."""
        workflow = get_workflow(event.workflow_id)
        for step in workflow.steps:
            for resource in step.resources:
                if resource.resource_type == 'material':
                    reserve_material(resource.dynamic_material_id, resource.quantity)
                elif resource.resource_type == 'tool':
                    schedule_tool_usage(resource.tool_id, step.estimated_duration)
    
    @global_event_bus.subscribe
    def release_resources(event: WorkflowCompletedEvent):
        """Release resources when workflow completes."""
        release_all_resources(event.execution_id)
```

### **2. Analytics Handler**

```python
class WorkflowAnalyticsHandler:
    def __init__(self):
        self.setup_handlers()
    
    def setup_handlers(self):
        global_event_bus.subscribe(WorkflowStartedEvent, self.track_start)
        global_event_bus.subscribe(WorkflowCompletedEvent, self.track_completion)
        global_event_bus.subscribe(WorkflowStepCompletedEvent, self.track_step_time)
    
    def track_start(self, event: WorkflowStartedEvent):
        """Track workflow start metrics."""
        self.record_metric('workflow_started', {
            'workflow_id': event.workflow_id,
            'user_id': event.user_id,
            'timestamp': event.timestamp
        })
    
    def track_completion(self, event: WorkflowCompletedEvent):
        """Track workflow completion metrics."""
        self.record_metric('workflow_completed', {
            'workflow_id': event.workflow_id,
            'duration': event.total_duration,
            'outcome_id': event.outcome_id
        })
    
    def track_step_time(self, event: WorkflowStepCompletedEvent):
        """Track step completion times for optimization."""
        self.record_metric('step_duration', {
            'step_id': event.step_id,
            'step_type': event.step_type,
            'actual_duration': event.actual_duration
        })
```

### **3. Notification Handler**

```python
async def setup_notification_handlers():
    """Set up notification event handlers."""
    
    async def notify_workflow_start(event: WorkflowStartedEvent):
        """Send notification when workflow starts."""
        message = f"Started workflow: {event.workflow_name}"
        await send_user_notification(event.user_id, message)
    
    async def notify_milestone_reached(event: WorkflowMilestoneReachedEvent):
        """Send notification when milestone reached."""
        message = f"Milestone reached: {event.milestone_name} ({event.progress_percentage}%)"
        await send_user_notification(event.user_id, message)
    
    async def notify_resource_unavailable(event: WorkflowResourceUnavailableEvent):
        """Send alert when resources unavailable."""
        message = f"Resource unavailable: {event.resource_name}"
        await send_urgent_notification(event.user_id, message)
    
    # Subscribe to async events
    await global_event_bus.subscribe_async(WorkflowStartedEvent, notify_workflow_start)
    await global_event_bus.subscribe_async(WorkflowMilestoneReachedEvent, notify_milestone_reached)
    await global_event_bus.subscribe_async(WorkflowResourceUnavailableEvent, notify_resource_unavailable)
```

---

## 🔧 **Best Practices**

### **1. Event Design Principles**

```python
# ✅ GOOD: Specific, actionable events
WorkflowStepCompletedEvent(
    workflow_id=1,
    execution_id=100,
    step_id=15,
    step_name="Cut Leather Pieces",
    step_type="tool",
    actual_duration=12.5,
    user_id=123
)

# ❌ BAD: Generic, unclear events
GenericWorkflowEvent(action="something_happened", data={"stuff": "things"})

# ✅ GOOD: Include relevant context
WorkflowResourceReservedEvent(
    workflow_id=1,
    execution_id=100,
    resource_type="material",
    resource_id=50,
    resource_name="Vegetable Tanned Leather",  # Human-readable name
    quantity=2.5,
    user_id=123
)

# ❌ BAD: Missing context
ResourceEvent(resource_id=50, quantity=2.5)
```

### **2. Handler Design**

```python
# ✅ GOOD: Fast, focused handlers
def handle_workflow_started(event: WorkflowStartedEvent):
    """Quick handler that delegates heavy work."""
    # Log immediately
    logger.info(f"Workflow {event.workflow_id} started")
    
    # Queue heavy work for background processing
    background_tasks.add_task(reserve_resources, event.workflow_id, event.execution_id)

# ❌ BAD: Slow, blocking handlers
def handle_workflow_started_slow(event: WorkflowStartedEvent):
    """Slow handler that blocks event processing."""
    # This will block other event handlers
    complex_calculation_that_takes_minutes()
    slow_database_operations()
    external_api_calls_with_retries()

# ✅ GOOD: Error-safe handlers
def handle_step_completed(event: WorkflowStepCompletedEvent):
    """Handler with proper error handling."""
    try:
        update_progress_tracking(event.execution_id, event.step_id)
        calculate_next_steps(event.execution_id)
    except Exception as e:
        # Log error but don't re-raise (events system will log)
        logger.error(f"Error updating progress for step {event.step_id}: {e}")
        # Continue processing - don't block other handlers

# ❌ BAD: Error-prone handlers
def handle_step_completed_unsafe(event: WorkflowStepCompletedEvent):
    """Handler that can crash other handlers."""
    # This will stop all subsequent handlers if it fails
    risky_operation_without_error_handling()
    raise Exception("Oops!")  # This stops event processing
```

### **3. Performance Considerations**

```python
# ✅ GOOD: Efficient async handlers
async def handle_multiple_operations(event: WorkflowCompletedEvent):
    """Efficiently handle multiple async operations."""
    # Run independent operations concurrently
    await asyncio.gather(
        update_analytics_async(event.workflow_id),
        send_completion_notification_async(event.user_id),
        cleanup_resources_async(event.execution_id),
        return_exceptions=True  # Don't fail if one operation fails
    )

# ✅ GOOD: Batch processing for high-frequency events
class StepProgressBatcher:
    def __init__(self):
        self.batch = []
        self.batch_size = 10
        
    async def handle_step_progress(self, event: WorkflowProgressUpdateEvent):
        """Batch progress updates for efficiency."""
        self.batch.append(event)
        
        if len(self.batch) >= self.batch_size:
            await self.flush_batch()
    
    async def flush_batch(self):
        """Process batched progress updates."""
        if self.batch:
            await batch_update_progress(self.batch)
            self.batch.clear()
```

---

## 🔍 **Debugging and Monitoring**

### **1. Event Logging**

```python
import logging

# Configure event-specific logger
event_logger = logging.getLogger('hidesync.events')
event_logger.setLevel(logging.DEBUG)

# Custom event handler for debugging
def debug_event_handler(event: DomainEvent):
    """Log all events for debugging."""
    event_logger.debug(f"Event: {type(event).__name__} - {event.to_dict()}")

# Subscribe debug handler to all events (use sparingly!)
for event_class in [WorkflowCreatedEvent, WorkflowStartedEvent, WorkflowStepCompletedEvent]:
    global_event_bus.subscribe(event_class, debug_event_handler)
```

### **2. Performance Monitoring**

```python
import time
from functools import wraps

def monitor_handler_performance(handler_func):
    """Decorator to monitor event handler performance."""
    @wraps(handler_func)
    def wrapper(event: DomainEvent):
        start_time = time.time()
        try:
            result = handler_func(event)
            duration = time.time() - start_time
            
            if duration > 1.0:  # Log slow handlers
                logger.warning(
                    f"Slow handler {handler_func.__name__} took {duration:.2f}s "
                    f"for {type(event).__name__}"
                )
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Handler {handler_func.__name__} failed after {duration:.2f}s "
                f"for {type(event).__name__}: {e}"
            )
            raise
    return wrapper

# Usage
@monitor_handler_performance
def handle_workflow_creation(event: WorkflowCreatedEvent):
    """Monitored workflow creation handler."""
    # Handler implementation
    pass
```

### **3. Event Metrics**

```python
from collections import defaultdict, Counter
from datetime import datetime, timedelta

class EventMetrics:
    """Track event system metrics."""
    
    def __init__(self):
        self.event_counts = Counter()
        self.handler_errors = Counter()
        self.handler_durations = defaultdict(list)
        
    def track_event(self, event: DomainEvent):
        """Track event publication."""
        event_type = type(event).__name__
        self.event_counts[event_type] += 1
        
    def track_handler_error(self, handler_name: str, event_type: str):
        """Track handler errors."""
        self.handler_errors[f"{handler_name}:{event_type}"] += 1
        
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            'total_events': sum(self.event_counts.values()),
            'event_types': dict(self.event_counts),
            'handler_errors': dict(self.handler_errors),
            'most_common_events': self.event_counts.most_common(10)
        }

# Set up metrics tracking
metrics = EventMetrics()

def track_all_events(event: DomainEvent):
    """Track metrics for all events."""
    metrics.track_event(event)

# Subscribe metrics tracker to common events
for event_type in [WorkflowCreatedEvent, WorkflowStartedEvent, WorkflowCompletedEvent]:
    global_event_bus.subscribe(event_type, track_all_events)
```

---

## 🚨 **Troubleshooting Guide**

### **Common Issues and Solutions**

#### **1. Events Not Being Handled**

```python
# Problem: Handler not receiving events
# Solution: Check subscription

# ❌ Common mistake
global_event_bus.subscribe("WorkflowCreatedEvent", handler)  # String instead of class

# ✅ Correct way
global_event_bus.subscribe(WorkflowCreatedEvent, handler)  # Event class

# Debugging: List all subscribers
def debug_subscribers():
    for event_type, handlers in global_event_bus.subscribers.items():
        print(f"{event_type}: {len(handlers)} handlers")
        for handler in handlers:
            print(f"  - {handler.__name__}")
```

#### **2. Async/Sync Handler Issues**

```python
# Problem: Async handler called synchronously
# Solution: Use publish_async for async handlers

# ❌ This will log warnings
async def async_handler(event: WorkflowStartedEvent):
    await do_async_work()

global_event_bus.subscribe(WorkflowStartedEvent, async_handler)
global_event_bus.publish(event)  # Sync publish with async handler

# ✅ Correct approach
await global_event_bus.publish_async(event)  # Async publish for async handlers
```

#### **3. Handler Exceptions Stopping Processing**

```python
# Problem: One handler exception stops others
# Solution: Events system automatically catches exceptions

def failing_handler(event: WorkflowCreatedEvent):
    raise Exception("This won't stop other handlers")

def working_handler(event: WorkflowCreatedEvent):
    print("This will still run even if failing_handler crashes")

# Both handlers will be attempted, errors logged automatically
global_event_bus.subscribe(WorkflowCreatedEvent, failing_handler)
global_event_bus.subscribe(WorkflowCreatedEvent, working_handler)
```

#### **4. Memory Leaks from Uncleaned Subscriptions**

```python
# Problem: Handlers not being cleaned up
# Solution: Explicit unsubscription

class TemporaryEventHandler:
    def __init__(self):
        global_event_bus.subscribe(WorkflowCreatedEvent, self.handle_creation)
    
    def handle_creation(self, event: WorkflowCreatedEvent):
        # Handle event
        pass
    
    def cleanup(self):
        """Clean up subscriptions."""
        global_event_bus.unsubscribe(WorkflowCreatedEvent, self.handle_creation)

# Always call cleanup when done
handler = TemporaryEventHandler()
# ... use handler ...
handler.cleanup()  # Important!
```

---

## 📈 **Performance Optimization**

### **1. Event Batching**

```python
class EventBatcher:
    """Batch events for improved performance."""
    
    def __init__(self, batch_size: int = 50, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batches = defaultdict(list)
        self.last_flush = time.time()
    
    async def add_event(self, event: DomainEvent):
        """Add event to batch."""
        event_type = type(event).__name__
        self.batches[event_type].append(event)
        
        # Flush if batch is full or time expired
        if (len(self.batches[event_type]) >= self.batch_size or 
            time.time() - self.last_flush > self.flush_interval):
            await self.flush_batch(event_type)
    
    async def flush_batch(self, event_type: str):
        """Flush batch of events."""
        if event_type in self.batches:
            events = self.batches[event_type]
            self.batches[event_type] = []
            self.last_flush = time.time()
            
            # Process batch
            await self.process_event_batch(events)
    
    async def process_event_batch(self, events: List[DomainEvent]):
        """Process a batch of events efficiently."""
        # Group by operation type for efficient processing
        for event in events:
            await global_event_bus.publish_async(event)
```

### **2. Selective Event Processing**

```python
class SelectiveEventHandler:
    """Handle only relevant events for performance."""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        
    def handle_user_events_only(self, event: DomainEvent):
        """Only process events for specific user."""
        if hasattr(event, 'user_id') and event.user_id != self.user_id:
            return  # Skip events for other users
            
        # Process relevant events
        self.process_event(event)
    
    def process_event(self, event: DomainEvent):
        """Process the event."""
        # Implementation here
        pass
```

---

## 🎯 **Integration Examples**

### **FastAPI Integration**

```python
from fastapi import FastAPI
from app.core.events import setup_event_handlers, global_event_bus

app = FastAPI()

# Set up event handlers during startup
setup_event_handlers(app)

@app.on_event("startup")
async def configure_events():
    """Configure event handlers on startup."""
    # Import and set up your event handlers
    from app.services.workflow_event_handlers import setup_workflow_event_handlers
    from app.services.analytics_handlers import setup_analytics_handlers
    
    setup_workflow_event_handlers(get_db_session())
    setup_analytics_handlers()

@app.post("/workflows/")
async def create_workflow(workflow_data: WorkflowCreate):
    """API endpoint that publishes events."""
    # Create workflow
    workflow = await workflow_service.create_workflow(workflow_data)
    
    # Event is automatically published by the service
    # No need to manually publish here
    
    return workflow
```

### **Background Task Integration**

```python
from celery import Celery

celery_app = Celery('hidesync')

@global_event_bus.subscribe
def handle_resource_reservation(event: WorkflowResourceReservedEvent):
    """Queue background task for resource processing."""
    # Queue heavy work for background processing
    process_resource_reservation.delay(
        event.resource_id,
        event.quantity,
        event.execution_id
    )

@celery_app.task
def process_resource_reservation(resource_id: int, quantity: float, execution_id: int):
    """Background task for resource processing."""
    # Heavy processing here
    update_inventory_systems(resource_id, quantity)
    send_supplier_notifications(resource_id, quantity)
    update_cost_tracking(execution_id, resource_id, quantity)
```

---

## 📚 **Reference**

### **All Available Events**

| Category | Event Class | Purpose |
|----------|-------------|---------|
| **Core** | `EntityCreatedEvent` | Entity creation tracking |
| **Core** | `EntityUpdatedEvent` | Entity modification tracking |
| **Core** | `EntityDeletedEvent` | Entity deletion tracking |
| **Tools** | `ToolCreated` | Tool registration |
| **Tools** | `ToolStatusChanged` | Tool status updates |
| **Tools** | `ToolMaintenanceScheduled` | Maintenance planning |
| **Tools** | `ToolMaintenanceCompleted` | Maintenance completion |
| **Tools** | `ToolCheckedOut` | Tool checkout tracking |
| **Tools** | `ToolReturned` | Tool return tracking |
| **Workflows** | `WorkflowCreatedEvent` | Workflow creation |
| **Workflows** | `WorkflowUpdatedEvent` | Workflow modifications |
| **Workflows** | `WorkflowDeletedEvent` | Workflow deletion |
| **Workflows** | `WorkflowPublishedEvent` | Template publication |
| **Execution** | `WorkflowStartedEvent` | Execution start |
| **Execution** | `WorkflowCompletedEvent` | Execution completion |
| **Execution** | `WorkflowPausedEvent` | Execution pause |
| **Execution** | `WorkflowResumedEvent` | Execution resume |
| **Execution** | `WorkflowCancelledEvent` | Execution cancellation |
| **Steps** | `WorkflowStepStartedEvent` | Step start |
| **Steps** | `WorkflowStepCompletedEvent` | Step completion |
| **Steps** | `WorkflowDecisionMadeEvent` | Decision tracking |
| **Steps** | `WorkflowNavigationEvent` | Navigation tracking |
| **Resources** | `WorkflowResourceReservedEvent` | Resource reservation |
| **Resources** | `WorkflowResourceReleasedEvent` | Resource release |
| **Resources** | `WorkflowResourceUnavailableEvent` | Resource shortage |
| **Import/Export** | `WorkflowImportedEvent` | Template import |
| **Import/Export** | `WorkflowExportedEvent` | Template export |
| **Analytics** | `WorkflowMilestoneReachedEvent` | Milestone tracking |
| **Analytics** | `WorkflowProgressUpdateEvent` | Progress tracking |

### **EventBus Methods**

| Method | Purpose | Usage |
|--------|---------|-------|
| `publish(event)` | Sync event publishing | `global_event_bus.publish(event)` |
| `publish_async(event)` | Async event publishing | `await global_event_bus.publish_async(event)` |
| `subscribe(event_type, handler)` | Sync subscription | `global_event_bus.subscribe(EventClass, handler)` |
| `subscribe_async(event_type, handler)` | Async subscription | `await global_event_bus.subscribe_async(EventClass, handler)` |
| `unsubscribe(event_type, handler)` | Remove subscription | `global_event_bus.unsubscribe(EventClass, handler)` |
| `clear_subscriptions()` | Clear all subscriptions | `global_event_bus.clear_subscriptions()` |

---

This comprehensive events system provides the foundation for a reactive, event-driven architecture that scales with your HideSync application needs while maintaining type safety and performance.