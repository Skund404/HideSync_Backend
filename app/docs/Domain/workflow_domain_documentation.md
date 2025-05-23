# HideSync Workflow Management System Documentation

## 📋 **Table of Contents**

1. [System Overview](#-system-overview)
2. [Architecture](#-architecture)
3. [Database Schema](#-database-schema)
4. [API Reference](#-api-reference)
5. [Service Layer](#-service-layer)
6. [Repository Layer](#-repository-layer)
7. [Event Integration](#-event-integration)
8. [Import/Export System](#-importexport-system)
9. [Resource Management](#-resource-management)
10. [Interactive Navigation](#-interactive-navigation)
11. [Setup & Configuration](#-setup--configuration)
12. [Usage Examples](#-usage-examples)
13. [Best Practices](#-best-practices)
14. [Troubleshooting](#-troubleshooting)
15. [Extension Guide](#-extension-guide)

---

## 🎯 **System Overview**

### **Purpose**

The HideSync Workflow Management System provides a comprehensive platform for creating, managing, and executing structured workflows within the HideSync ecosystem. It extends HideSync's capabilities by enabling users to:

- **Create Templates**: Define reusable workflow templates for common projects
- **Execute Workflows**: Step-by-step guidance through complex processes
- **Track Progress**: Real-time progress monitoring and analytics
- **Manage Resources**: Integration with materials and tools inventory
- **Share Knowledge**: Import/export workflow presets for community sharing

### **Key Features**

| Feature | Description | Benefits |
|---------|-------------|----------|
| **Template System** | Create and share workflow templates | Standardize processes, reduce errors |
| **Multiple Outcomes** | Support different end results from single workflow | Flexibility for varying skill levels |
| **Interactive Navigation** | Text-adventure style step guidance | Intuitive user experience |
| **Resource Integration** | Seamless connection with inventory systems | Automated resource planning |
| **Event-Driven Architecture** | Real-time notifications and analytics | Responsive user experience |
| **JSON Import/Export** | Share workflows as portable presets | Community collaboration |
| **Progress Tracking** | Detailed execution analytics | Performance optimization |
| **Multilingual Support** | Built-in internationalization | Global accessibility |

### **Target Users**

- **Makers & Craftspeople**: Step-by-step project guidance
- **Educators**: Structured learning curricula 
- **Workshop Managers**: Standardized processes and procedures
- **Community Contributors**: Sharing expertise through templates

---

## 🏗️ **Architecture**

### **System Architecture Overview**

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Layer                          │
├─────────────────────────────────────────────────────────────┤
│                     API Layer                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Workflows     │  │   Executions    │  │   Resources  │ │
│  │   Endpoints     │  │   Endpoints     │  │   Endpoints  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                   Service Layer                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Workflow      │  │   Execution     │  │   Navigation │ │
│  │   Service       │  │   Service       │  │   Service    │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │  Import/Export  │  │   Resource      │  │   Event      │ │
│  │   Service       │  │   Service       │  │   Handlers   │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                 Repository Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Workflow      │  │   Execution     │  │     Step     │ │
│  │  Repository     │  │  Repository     │  │  Repository  │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                   Database Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Workflow      │  │   Execution     │  │   Resource   │ │
│  │    Models       │  │    Models       │  │    Models    │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                Integration Layer                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │
│  │   Material      │  │     Tool        │  │    Event     │ │
│  │  Integration    │  │  Integration    │  │     Bus      │ │
│  └─────────────────┘  └─────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### **Core Components**

#### **1. Database Models**
- **12 Core Tables**: Comprehensive workflow data modeling
- **4 Enum Tables**: Dynamic enum support for workflow types
- **Foreign Key Relationships**: Ensures data integrity
- **Performance Indexes**: Optimized for common query patterns

#### **2. Repository Layer**
- **WorkflowRepository**: Core workflow CRUD operations
- **WorkflowStepRepository**: Step management and connections
- **WorkflowExecutionRepository**: Runtime execution tracking
- **Repository Factory**: Centralized repository creation with dependency injection

#### **3. Service Layer**
- **WorkflowService**: Core business logic and validation
- **WorkflowExecutionService**: Execution engine and flow control
- **WorkflowNavigationService**: Interactive guidance and text-adventure features
- **WorkflowImportExportService**: JSON preset management
- **WorkflowResourceService**: Material and tool integration

#### **4. API Layer**
- **15+ REST Endpoints**: Complete CRUD operations plus advanced features
- **OpenAPI Documentation**: Auto-generated API documentation
- **Request/Response Validation**: Pydantic schema validation
- **Error Handling**: Consistent HTTP status codes and error messages

### **Design Patterns Used**

| Pattern | Implementation | Benefits |
|---------|----------------|----------|
| **Repository Pattern** | Abstracted data access | Testability, loose coupling |
| **Service Layer** | Business logic encapsulation | Separation of concerns |
| **Dependency Injection** | Constructor injection via factory | Flexible, testable architecture |
| **Event-Driven Architecture** | Domain events for side effects | Decoupled, reactive system |
| **Factory Pattern** | Repository and service creation | Consistent object creation |
| **Strategy Pattern** | Step type handling | Extensible step behaviors |

---

## 🗄️ **Database Schema**

### **Core Tables Overview**

#### **1. Workflow Management Tables**

```sql
-- Main workflow definition
workflows
├── id (PK)
├── name
├── description
├── status (enum)
├── created_by (FK → users)
├── is_template
├── project_id (FK → projects)
├── theme_id (FK → workflow_themes)
├── visibility (private/public/shared)
├── has_multiple_outcomes
├── estimated_duration
└── difficulty_level

-- Workflow steps
workflow_steps
├── id (PK)
├── workflow_id (FK → workflows)
├── name
├── description
├── instructions
├── display_order
├── step_type (enum)
├── estimated_duration
├── parent_step_id (FK → workflow_steps)
├── is_milestone
├── ui_position_x/y
├── is_decision_point
├── is_outcome
└── condition_logic (JSON)

-- Step connections (workflow flow)
workflow_step_connections
├── id (PK)
├── source_step_id (FK → workflow_steps)
├── target_step_id (FK → workflow_steps)
├── connection_type (enum)
├── condition (JSON)
├── display_order
└── is_default
```

#### **2. Resource Management Tables**

```sql
-- Step resources
workflow_step_resources
├── id (PK)
├── step_id (FK → workflow_steps)
├── resource_type (material/tool/documentation)
├── dynamic_material_id (FK → dynamic_materials)
├── tool_id (FK → tools)
├── documentation_id (FK → documentation)
├── quantity
├── unit
├── notes
└── is_optional

-- Workflow outcomes
workflow_outcomes
├── id (PK)
├── workflow_id (FK → workflows)
├── name
├── description
├── display_order
├── is_default
└── success_criteria (JSON)

-- Decision options
workflow_decision_options
├── id (PK)
├── step_id (FK → workflow_steps)
├── option_text
├── result_action (JSON)
├── display_order
└── is_default
```

#### **3. Execution Tracking Tables**

```sql
-- Workflow executions
workflow_executions
├── id (PK)
├── workflow_id (FK → workflows)
├── started_by (FK → users)
├── status (enum)
├── started_at
├── completed_at
├── selected_outcome_id (FK → workflow_outcomes)
├── current_step_id (FK → workflow_steps)
├── execution_data (JSON)
└── total_duration

-- Step execution tracking
workflow_step_executions
├── id (PK)
├── execution_id (FK → workflow_executions)
├── step_id (FK → workflow_steps)
├── status (enum)
├── started_at
├── completed_at
├── actual_duration
├── step_data (JSON)
└── notes

-- Navigation history
workflow_navigation_history
├── id (PK)
├── execution_id (FK → workflow_executions)
├── step_id (FK → workflow_steps)
├── action_type
├── action_data (JSON)
└── timestamp
```

#### **4. Internationalization Tables**

```sql
-- Workflow translations
workflow_translations
├── id (PK)
├── workflow_id (FK → workflows)
├── locale
├── field_name
└── translated_value

-- Step translations
workflow_step_translations
├── id (PK)
├── step_id (FK → workflow_steps)
├── locale
├── field_name
└── translated_value
```

#### **5. Advanced Features Tables**

```sql
-- Workflow themes
workflow_themes
├── id (PK)
├── name
├── description
├── color_scheme (JSON)
├── icon_set
├── is_system
└── created_at

-- Predefined paths
workflow_paths
├── id (PK)
├── workflow_id (FK → workflows)
├── name
├── description
├── is_default
├── difficulty_level
└── estimated_duration

-- Path steps
workflow_path_steps
├── id (PK)
├── path_id (FK → workflow_paths)
├── step_id (FK → workflow_steps)
├── step_order
├── is_optional
└── skip_condition (JSON)
```

### **Enum Tables**

The system uses dynamic enums for flexibility:

```sql
-- Step types
enum_value_workflow_step_type
├── instruction
├── material
├── tool
├── time
├── decision
├── milestone
├── outcome
├── quality_check
└── documentation

-- Workflow statuses
enum_value_workflow_status
├── draft
├── active
├── published
├── archived
└── deprecated

-- Connection types
enum_value_workflow_connection_type
├── sequential
├── conditional
├── parallel
├── choice
├── fallback
└── loop

-- Execution statuses
enum_value_workflow_execution_status
├── active
├── paused
├── completed
├── failed
├── cancelled
└── timeout
```

### **Key Relationships**

```
workflows (1) ──→ (many) workflow_steps
         (1) ──→ (many) workflow_executions
         (1) ──→ (many) workflow_outcomes

workflow_steps (1) ──→ (many) workflow_step_resources
              (1) ──→ (many) workflow_decision_options
              (1) ──→ (many) workflow_step_connections (as source)
              (1) ──→ (many) workflow_step_connections (as target)

workflow_executions (1) ──→ (many) workflow_step_executions
                    (1) ──→ (many) workflow_navigation_history

workflow_step_resources ──→ dynamic_materials
                       ──→ tools
                       ──→ documentation
```

### **Performance Optimizations**

#### **Strategic Indexes**

```sql
-- Workflow indexes
CREATE INDEX idx_workflow_status_template ON workflows(status, is_template);
CREATE INDEX idx_workflow_created_by ON workflows(created_by);
CREATE INDEX idx_workflow_project ON workflows(project_id);

-- Step indexes
CREATE INDEX idx_workflow_step_workflow_order ON workflow_steps(workflow_id, display_order);
CREATE INDEX idx_workflow_step_type ON workflow_steps(step_type);

-- Execution indexes
CREATE INDEX idx_workflow_execution_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_execution_user ON workflow_executions(started_by);
CREATE INDEX idx_workflow_execution_status ON workflow_executions(status);

-- Navigation indexes
CREATE INDEX idx_workflow_navigation_execution ON workflow_navigation_history(execution_id);
CREATE INDEX idx_workflow_navigation_timestamp ON workflow_navigation_history(timestamp);
```

#### **Query Optimization Patterns**

- **Eager Loading**: Relationships loaded efficiently with `selectinload()` and `joinedload()`
- **Pagination**: All list endpoints support limit/offset pagination
- **Filtering**: Indexed columns used for common filter operations
- **Aggregate Queries**: Optimized for statistics and analytics

---

## 🌐 **API Reference**

### **Base URL Structure**

```
Base URL: /api/v1/workflows/
Authentication: Bearer token required for all endpoints
Content-Type: application/json
```

### **Core Workflow Endpoints**

#### **1. List Workflows**

```http
GET /api/v1/workflows/
```

**Query Parameters:**
- `search` (string): Search term for name/description
- `status` (string): Filter by workflow status
- `is_template` (boolean): Filter by template status
- `difficulty_level` (string): Filter by difficulty
- `project_id` (integer): Filter by project
- `limit` (integer, 1-100): Number of items to return (default: 50)
- `offset` (integer): Number of items to skip (default: 0)
- `order_by` (string): Field to order by (default: updated_at)
- `order_dir` (string): Order direction - asc/desc (default: desc)

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Basic Leather Wallet",
      "description": "Simple bi-fold wallet project",
      "status": "published",
      "is_template": true,
      "created_by": 123,
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z",
      "estimated_duration": 240,
      "difficulty_level": "beginner",
      "has_multiple_outcomes": false
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### **2. Create Workflow**

```http
POST /api/v1/workflows/
```

**Request Body:**
```json
{
  "name": "My Custom Workflow",
  "description": "A workflow for custom projects",
  "is_template": false,
  "visibility": "private",
  "project_id": 456,
  "estimated_duration": 180,
  "difficulty_level": "intermediate",
  "has_multiple_outcomes": true
}
```

**Response:** `201 Created`
```json
{
  "id": 2,
  "name": "My Custom Workflow",
  "description": "A workflow for custom projects",
  "status": "draft",
  "is_template": false,
  "created_by": 123,
  "created_at": "2024-01-15T11:00:00Z",
  "updated_at": "2024-01-15T11:00:00Z",
  "project_id": 456,
  "visibility": "private",
  "estimated_duration": 180,
  "difficulty_level": "intermediate",
  "has_multiple_outcomes": true
}
```

#### **3. Get Workflow Details**

```http
GET /api/v1/workflows/{workflow_id}
```

**Response:**
```json
{
  "id": 1,
  "name": "Basic Leather Wallet",
  "description": "Simple bi-fold wallet project",
  "status": "published",
  "is_template": true,
  "created_by": 123,
  "steps": [
    {
      "id": 1,
      "name": "Prepare Workspace",
      "description": "Set up your work area",
      "step_type": "instruction",
      "display_order": 1,
      "estimated_duration": 10,
      "is_milestone": false,
      "resources": [
        {
          "id": 1,
          "resource_type": "tool",
          "quantity": 1,
          "unit": "piece",
          "notes": "Large cutting mat",
          "is_optional": false
        }
      ]
    }
  ],
  "outcomes": [
    {
      "id": 1,
      "name": "Completed Basic Wallet",
      "description": "Functional bi-fold leather wallet",
      "is_default": true
    }
  ]
}
```

#### **4. Update Workflow**

```http
PUT /api/v1/workflows/{workflow_id}
```

**Request Body:**
```json
{
  "name": "Updated Workflow Name",
  "description": "Updated description",
  "status": "active"
}
```

**Response:** `200 OK` (Updated workflow object)

#### **5. Delete Workflow**

```http
DELETE /api/v1/workflows/{workflow_id}
```

**Response:** `204 No Content`

### **Workflow Execution Endpoints**

#### **6. Start Workflow Execution**

```http
POST /api/v1/workflows/{workflow_id}/start
```

**Request Body:**
```json
{
  "selected_outcome_id": 1
}
```

**Response:** `201 Created`
```json
{
  "id": 100,
  "workflow_id": 1,
  "started_by": 123,
  "status": "active",
  "started_at": "2024-01-15T12:00:00Z",
  "current_step_id": 1,
  "selected_outcome_id": 1,
  "execution_data": {}
}
```

#### **7. Get Active Executions**

```http
GET /api/v1/workflows/executions/active
```

**Response:**
```json
[
  {
    "id": 100,
    "workflow_id": 1,
    "workflow_name": "Basic Leather Wallet",
    "status": "active",
    "started_at": "2024-01-15T12:00:00Z",
    "current_step_id": 3,
    "progress_percentage": 25.0
  }
]
```

### **Template Management Endpoints**

#### **8. Get Workflow Templates**

```http
GET /api/v1/workflows/templates/
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Basic Leather Wallet",
    "description": "Beginner-friendly wallet project",
    "difficulty_level": "beginner",
    "estimated_duration": 240,
    "visibility": "public",
    "created_by": 123
  }
]
```

#### **9. Publish as Template**

```http
POST /api/v1/workflows/{workflow_id}/publish
```

**Request Body:**
```json
{
  "visibility": "public"
}
```

**Response:** `200 OK` (Updated workflow object with `is_template: true`)

#### **10. Duplicate Workflow**

```http
POST /api/v1/workflows/{workflow_id}/duplicate
```

**Request Body:**
```json
{
  "new_name": "My Copy of Leather Wallet",
  "as_template": false
}
```

**Response:** `201 Created` (New workflow object)

### **Analytics Endpoints**

#### **11. Get Workflow Statistics**

```http
GET /api/v1/workflows/{workflow_id}/statistics
```

**Response:**
```json
{
  "workflow_id": 1,
  "total_executions": 25,
  "completed_executions": 20,
  "average_completion_time": 235.5,
  "success_rate": 80.0,
  "most_common_outcome": "Completed Basic Wallet"
}
```

### **Admin Endpoints (Superuser Required)**

#### **12. Import Workflow**

```http
POST /api/v1/workflows/import
```

**Request Body:**
```json
{
  "preset_info": {
    "name": "Imported Workflow",
    "description": "Workflow from JSON preset",
    "difficulty": "intermediate"
  },
  "workflow": {
    "name": "Imported Workflow",
    "steps": [...],
    "connections": [...],
    "outcomes": [...]
  },
  "required_resources": {...},
  "metadata": {...}
}
```

**Response:** `201 Created` (Created workflow object)

#### **13. Export Workflow**

```http
GET /api/v1/workflows/{workflow_id}/export
```

**Response:**
```json
{
  "preset_info": {
    "name": "Basic Leather Wallet",
    "description": "Simple bi-fold wallet project",
    "difficulty": "beginner",
    "estimated_time": 240
  },
  "workflow": {
    "name": "Basic Leather Wallet Workflow",
    "steps": [...],
    "connections": [...],
    "outcomes": [...]
  },
  "required_resources": {
    "materials": [...],
    "tools": [...],
    "documentation": []
  },
  "metadata": {
    "version": "1.0",
    "exported_at": "2024-01-15T13:00:00Z",
    "original_workflow_id": 1
  }
}
```

### **Utility Endpoints**

#### **14. Get Workflow Steps**

```http
GET /api/v1/workflows/{workflow_id}/steps
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Prepare Workspace",
    "step_type": "instruction",
    "display_order": 1,
    "resources": [...],
    "decision_options": []
  }
]
```

#### **15. Bulk Delete Workflows**

```http
DELETE /api/v1/workflows/bulk
```

**Request Body:**
```json
{
  "workflow_ids": [1, 2, 3]
}
```

**Response:** `204 No Content` or `207 Multi-Status` with error details

#### **16. Health Check**

```http
GET /api/v1/workflows/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "workflow_management",
  "timestamp": "2024-01-15T13:00:00Z"
}
```

### **Error Responses**

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

**Common HTTP Status Codes:**
- `400 Bad Request`: Invalid input data or business rule violation
- `401 Unauthorized`: Missing or invalid authentication
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Duplicate resource or constraint violation
- `422 Unprocessable Entity`: Validation errors
- `500 Internal Server Error`: Unexpected server error

---

## 🎛️ **Service Layer**

### **WorkflowService**

The core service for workflow management and business logic.

#### **Key Methods**

```python
class WorkflowService:
    def create_workflow(self, workflow_data: Dict[str, Any], user_id: int) -> Workflow
    def update_workflow(self, workflow_id: int, update_data: Dict[str, Any], user_id: int) -> Workflow
    def get_workflow(self, workflow_id: int, user_id: Optional[int] = None) -> Workflow
    def delete_workflow(self, workflow_id: int, user_id: int) -> bool
    def duplicate_workflow(self, workflow_id: int, new_name: str, user_id: int, as_template: bool = False) -> Workflow
    def get_workflow_templates(self, user_id: Optional[int] = None) -> List[Workflow]
    def publish_as_template(self, workflow_id: int, user_id: int, visibility: str = 'public') -> Workflow
    def search_workflows(self, search_params: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]
    def start_workflow_execution(self, workflow_id: int, user_id: int, selected_outcome_id: Optional[int] = None) -> WorkflowExecution
    def get_workflow_statistics(self, workflow_id: int, user_id: Optional[int] = None) -> Dict[str, Any]
```

#### **Usage Example**

```python
from app.services.workflow_service import WorkflowService

# Initialize service
workflow_service = WorkflowService(session)

# Create a new workflow
workflow_data = {
    "name": "My Leather Project",
    "description": "Custom leather working project",
    "difficulty_level": "intermediate",
    "estimated_duration": 300
}
workflow = workflow_service.create_workflow(workflow_data, user_id=123)

# Start execution
execution = workflow_service.start_workflow_execution(
    workflow.id, 
    user_id=123, 
    selected_outcome_id=None
)
```

#### **Business Rules Enforced**

- **Name Uniqueness**: Workflow names must be unique per user
- **Permission Checks**: Users can only modify their own workflows
- **Status Validation**: Workflows must be in appropriate status for operations
- **Template Publication**: Workflows must meet quality criteria before publication
- **Execution Prerequisites**: Resource availability checked before starting

### **WorkflowExecutionService**

Handles runtime workflow execution and flow control.

#### **Key Methods**

```python
class WorkflowExecutionService:
    def get_execution(self, execution_id: int, user_id: Optional[int] = None) -> WorkflowExecution
    def pause_execution(self, execution_id: int, user_id: int) -> WorkflowExecution
    def resume_execution(self, execution_id: int, user_id: int) -> WorkflowExecution
    def cancel_execution(self, execution_id: int, user_id: int, reason: Optional[str] = None) -> WorkflowExecution
    def navigate_to_step(self, execution_id: int, target_step_id: int, user_id: int) -> WorkflowExecution
    def complete_step(self, execution_id: int, step_id: int, user_id: int, completion_data: Optional[Dict[str, Any]] = None) -> WorkflowExecution
    def make_decision(self, execution_id: int, step_id: int, decision_option_id: int, user_id: int) -> WorkflowExecution
    def get_execution_progress(self, execution_id: int, user_id: Optional[int] = None) -> Dict[str, Any]
    def get_next_available_steps(self, execution_id: int, user_id: Optional[int] = None) -> List[WorkflowStep]
```

#### **Execution Flow**

```python
# Start execution
execution = workflow_service.start_workflow_execution(workflow_id, user_id)

# Navigate to specific step
execution_service.navigate_to_step(execution.id, step_id=5, user_id=user_id)

# Complete current step
completion_data = {
    "notes": "Completed successfully",
    "actual_duration": 15.5
}
execution_service.complete_step(execution.id, step_id=5, user_id=user_id, completion_data=completion_data)

# Make decision at decision point
execution_service.make_decision(execution.id, step_id=8, decision_option_id=2, user_id=user_id)

# Check progress
progress = execution_service.get_execution_progress(execution.id, user_id)
```

### **WorkflowNavigationService**

Provides interactive, text-adventure style workflow guidance.

#### **Key Methods**

```python
class WorkflowNavigationService:
    def get_navigation_context(self, execution_id: int, user_id: int) -> Dict[str, Any]
    def get_step_guidance(self, execution_id: int, step_id: int, user_id: int) -> Dict[str, Any]
    def suggest_next_action(self, execution_id: int, user_id: int) -> Dict[str, Any]
    def process_natural_language_command(self, execution_id: int, command: str, user_id: int) -> Dict[str, Any]
    def find_optimal_path(self, execution_id: int, target_outcome_id: Optional[int] = None, user_id: Optional[int] = None) -> Dict[str, Any]
```

#### **Interactive Features**

```python
# Get complete navigation context
context = navigation_service.get_navigation_context(execution_id, user_id)
# Returns: current step, available options, progress, guidance

# Get detailed step guidance
guidance = navigation_service.get_step_guidance(execution_id, step_id, user_id)
# Returns: instructions, resources needed, tips, warnings

# Get AI-powered suggestions
suggestion = navigation_service.suggest_next_action(execution_id, user_id)
# Returns: recommended action with reasoning

# Process natural language commands
result = navigation_service.process_natural_language_command(
    execution_id, "show me what materials I need", user_id
)
# Returns: parsed command result with helpful response
```

### **WorkflowImportExportService**

Manages JSON-based workflow sharing and preset system.

#### **Key Methods**

```python
class WorkflowImportExportService:
    def import_workflow(self, import_data: Dict[str, Any], user_id: int) -> Workflow
    def import_workflow_from_file(self, file_path: str, user_id: int) -> Workflow
    def export_workflow(self, workflow_id: int) -> Dict[str, Any]
    def export_workflow_to_file(self, workflow_id: int, file_path: str) -> bool
    def create_preset_from_workflow(self, workflow_id: int, preset_name: str, preset_description: str, difficulty: str = 'intermediate') -> Dict[str, Any]
    def validate_preset_data(self, preset_data: Dict[str, Any]) -> List[str]
```

#### **Import/Export Example**

```python
# Export workflow to JSON
export_data = import_export_service.export_workflow(workflow_id)

# Save to file
import_export_service.export_workflow_to_file(workflow_id, "my_workflow.json")

# Import from JSON
with open("preset.json") as f:
    preset_data = json.load(f)

workflow = import_export_service.import_workflow(preset_data, user_id)

# Validate preset before import
errors = import_export_service.validate_preset_data(preset_data)
if not errors:
    workflow = import_export_service.import_workflow(preset_data, user_id)
```

### **WorkflowResourceService**

Integrates workflow execution with material and tool management.

#### **Key Methods**

```python
class WorkflowResourceService:
    def analyze_workflow_resources(self, workflow_id: int) -> Dict[str, Any]
    def check_execution_readiness(self, workflow_id: int) -> Dict[str, Any]
    def reserve_execution_resources(self, execution_id: int) -> Dict[str, Any]
    def release_execution_resources(self, execution_id: int) -> bool
    def prepare_step_resources(self, execution_id: int, step_id: int) -> Dict[str, Any]
    def complete_step_resource_usage(self, execution_id: int, step_id: int, actual_usage: Optional[Dict[str, Any]] = None) -> bool
```

#### **Resource Management Example**

```python
# Analyze workflow resource requirements
analysis = resource_service.analyze_workflow_resources(workflow_id)
# Returns: material/tool requirements, availability, costs

# Check if workflow is ready for execution
readiness = resource_service.check_execution_readiness(workflow_id)
# Returns: ready status, blocking issues, recommendations

# Reserve resources for execution
reservation = resource_service.reserve_execution_resources(execution_id)
# Returns: reservation details and success status

# Prepare resources for specific step
preparation = resource_service.prepare_step_resources(execution_id, step_id)
# Returns: materials and tools needed for the step
```

---

## 🗂️ **Repository Layer**

### **WorkflowRepository**

Core data access for workflow operations.

#### **Key Methods**

```python
class WorkflowRepository(BaseRepository):
    def get_workflow_with_steps(self, workflow_id: int, include_resources: bool = True) -> Optional[Workflow]
    def get_workflow_templates(self, user_id: Optional[int] = None, include_system: bool = True) -> List[Workflow]
    def search_workflows(self, search_term: Optional[str] = None, status: Optional[str] = None, ...) -> Dict[str, Any]
    def get_user_workflows(self, user_id: int, include_templates: bool = False) -> List[Workflow]
    def duplicate_workflow(self, workflow_id: int, new_name: str, created_by: int, as_template: bool = False) -> Workflow
    def get_initial_steps(self, workflow_id: int) -> List[WorkflowStep]
    def get_next_steps(self, current_step_id: int, execution_data: Optional[Dict[str, Any]] = None) -> List[WorkflowStep]
    def get_workflow_statistics(self, workflow_id: int) -> Dict[str, Any]
    def update_workflow_status(self, workflow_id: int, new_status: str) -> bool
    def delete_workflow_cascade(self, workflow_id: int) -> bool
```

#### **Optimized Queries**

```python
# Efficient workflow loading with relationships
workflow = repository.get_workflow_with_steps(workflow_id, include_resources=True)
# Uses selectinload() and joinedload() for optimal performance

# Paginated search with filtering
results = repository.search_workflows(
    search_term="leather",
    status="published",
    is_template=True,
    limit=50,
    offset=0
)
# Returns paginated results with total count

# Optimized duplication with step mapping
duplicate = repository.duplicate_workflow(
    source_workflow_id, 
    "Copy of Original", 
    user_id, 
    as_template=False
)
# Preserves all relationships and creates ID mappings
```

### **WorkflowStepRepository**

Specialized repository for step management.

#### **Key Methods**

```python
class WorkflowStepRepository(BaseRepository):
    def get_step_with_details(self, step_id: int) -> Optional[WorkflowStep]
    def get_workflow_steps_ordered(self, workflow_id: int) -> List[WorkflowStep]
    def create_step_with_resources(self, step_data: Dict[str, Any], resources: Optional[List[Dict[str, Any]]] = None, decision_options: Optional[List[Dict[str, Any]]] = None) -> WorkflowStep
    def update_step_order(self, workflow_id: int, step_orders: List[Tuple[int, int]]) -> bool
    def get_steps_by_type(self, workflow_id: int, step_type: str) -> List[WorkflowStep]
    def create_step_connection(self, source_step_id: int, target_step_id: int, connection_type: str = 'sequential', ...) -> WorkflowStepConnection
    def get_step_connections(self, step_id: int, direction: str = 'outgoing') -> List[WorkflowStepConnection]
    def add_step_resource(self, step_id: int, resource_data: Dict[str, Any]) -> WorkflowStepResource
    def get_step_resources(self, step_id: int, resource_type: Optional[str] = None) -> List[WorkflowStepResource]
    def find_orphaned_steps(self, workflow_id: int) -> List[WorkflowStep]
    def validate_step_connections(self, workflow_id: int) -> List[Dict[str, Any]]
```

#### **Step Management Example**

```python
# Create step with resources and decisions
step_data = {
    "workflow_id": 1,
    "name": "Cut Leather Pieces",
    "step_type": "tool",
    "display_order": 3
}

resources = [
    {
        "resource_type": "material",
        "dynamic_material_id": 5,
        "quantity": 2.0,
        "unit": "pieces"
    },
    {
        "resource_type": "tool", 
        "tool_id": 10,
        "notes": "Sharp leather knife required"
    }
]

decision_options = [
    {
        "option_text": "Hand cut with knife",
        "is_default": True
    },
    {
        "option_text": "Use rotary cutter",
        "is_default": False
    }
]

step = step_repo.create_step_with_resources(step_data, resources, decision_options)

# Create connection between steps
connection = step_repo.create_step_connection(
    source_step_id=2,
    target_step_id=step.id,
    connection_type="sequential"
)

# Validate workflow integrity
issues = step_repo.validate_step_connections(workflow_id)
orphaned = step_repo.find_orphaned_steps(workflow_id)
```

### **WorkflowExecutionRepository**

Tracks runtime execution state and history.

#### **Key Methods**

```python
class WorkflowExecutionRepository(BaseRepository):
    def get_execution_with_details(self, execution_id: int) -> Optional[WorkflowExecution]
    def get_active_executions(self, user_id: Optional[int] = None, workflow_id: Optional[int] = None) -> List[WorkflowExecution]
    def update_execution_status(self, execution_id: int, new_status: str, completion_data: Optional[Dict[str, Any]] = None) -> bool
    def update_current_step(self, execution_id: int, step_id: int) -> bool
    def create_step_execution(self, execution_id: int, step_id: int, initial_status: str = 'ready') -> WorkflowStepExecution
    def get_step_execution(self, execution_id: int, step_id: int) -> Optional[WorkflowStepExecution]
    def update_step_execution(self, execution_id: int, step_id: int, update_data: Dict[str, Any]) -> bool
    def record_navigation(self, execution_id: int, step_id: int, action_type: str, action_data: Optional[Dict[str, Any]] = None) -> WorkflowNavigationHistory
    def get_navigation_history(self, execution_id: int, limit: int = 50) -> List[WorkflowNavigationHistory]
    def calculate_execution_progress(self, execution_id: int) -> Dict[str, Any]
    def search_executions(self, user_id: Optional[int] = None, workflow_id: Optional[int] = None, ...) -> Dict[str, Any]
```

#### **Execution Tracking Example**

```python
# Track step progression
step_execution = execution_repo.create_step_execution(execution_id, step_id, "active")

# Update step with completion data
update_data = {
    "status": "completed",
    "completed_at": datetime.utcnow(),
    "actual_duration": 12.5,
    "notes": "Completed without issues"
}
execution_repo.update_step_execution(execution_id, step_id, update_data)

# Record navigation action
navigation = execution_repo.record_navigation(
    execution_id, 
    step_id, 
    "completed",
    {"actual_duration": 12.5}
)

# Calculate progress
progress = execution_repo.calculate_execution_progress(execution_id)
# Returns: total steps, completed, percentage, time estimates
```

---

## 🔔 **Event Integration**

### **Workflow Events Overview**

The workflow system publishes comprehensive events for all significant actions:

| Event Category | Events | Purpose |
|----------------|--------|---------|
| **Workflow Management** | Created, Updated, Deleted, Published | Template lifecycle tracking |
| **Execution Lifecycle** | Started, Completed, Paused, Resumed, Cancelled | Execution state changes |
| **Step Progression** | Started, Completed, Decision Made, Navigation | Step-level tracking |
| **Resource Management** | Reserved, Released, Unavailable | Inventory integration |
| **Analytics** | Milestone Reached, Progress Updated | Performance tracking |

### **Event Publishing**

Events are automatically published by services:

```python
# Service automatically publishes events
workflow = workflow_service.create_workflow(workflow_data, user_id)
# Publishes: WorkflowCreatedEvent

execution = workflow_service.start_workflow_execution(workflow_id, user_id)
# Publishes: WorkflowStartedEvent

execution_service.complete_step(execution_id, step_id, user_id, completion_data)
# Publishes: WorkflowStepCompletedEvent
```

### **Event Handling Examples**

#### **Resource Management Handler**

```python
@global_event_bus.subscribe
def handle_workflow_started(event: WorkflowStartedEvent):
    """Reserve resources when workflow starts."""
    workflow = get_workflow(event.workflow_id)
    
    for step in workflow.steps:
        for resource in step.resources:
            if resource.resource_type == 'material':
                reserve_material(resource.dynamic_material_id, resource.quantity)
            elif resource.resource_type == 'tool':
                schedule_tool_usage(resource.tool_id, step.estimated_duration)

@global_event_bus.subscribe  
def handle_workflow_completed(event: WorkflowCompletedEvent):
    """Release resources when workflow completes."""
    release_all_execution_resources(event.execution_id)
```

#### **Analytics Handler**

```python
class WorkflowAnalytics:
    def __init__(self):
        global_event_bus.subscribe(WorkflowStartedEvent, self.track_start)
        global_event_bus.subscribe(WorkflowCompletedEvent, self.track_completion)
        global_event_bus.subscribe(WorkflowStepCompletedEvent, self.track_step_duration)
    
    def track_start(self, event: WorkflowStartedEvent):
        """Track workflow start metrics."""
        self.record_metric('workflow_started', {
            'workflow_id': event.workflow_id,
            'user_id': event.user_id,
            'timestamp': event.timestamp
        })
    
    def track_completion(self, event: WorkflowCompletedEvent):
        """Track completion and calculate success rate."""
        self.record_metric('workflow_completed', {
            'workflow_id': event.workflow_id,
            'duration': event.total_duration,
            'outcome_id': event.outcome_id
        })
        
        # Update success rate statistics
        self.update_workflow_success_rate(event.workflow_id)
```

#### **Notification Handler**

```python
async def setup_workflow_notifications():
    """Set up notification handlers for workflow events."""
    
    async def notify_milestone(event: WorkflowMilestoneReachedEvent):
        """Send notification when milestone reached."""
        message = f"🎉 Milestone reached: {event.milestone_name} ({event.progress_percentage}%)"
        await send_user_notification(event.user_id, message)
    
    async def notify_completion(event: WorkflowCompletedEvent):
        """Send notification when workflow completes."""
        message = f"✅ Workflow completed: {event.workflow_name}"
        await send_user_notification(event.user_id, message)
    
    await global_event_bus.subscribe_async(WorkflowMilestoneReachedEvent, notify_milestone)
    await global_event_bus.subscribe_async(WorkflowCompletedEvent, notify_completion)
```

### **Custom Event Handlers**

```python
# Set up custom event handlers during app startup
def setup_custom_workflow_handlers():
    """Set up application-specific workflow event handlers."""
    
    @global_event_bus.subscribe
    def log_workflow_activity(event: DomainEvent):
        """Log all workflow-related events for audit."""
        if event.__class__.__name__.startswith('Workflow'):
            logger.info(f"Workflow Event: {event.__class__.__name__} - {event.to_dict()}")
    
    @global_event_bus.subscribe
    def update_project_stats(event: WorkflowStartedEvent):
        """Update project statistics when workflows start."""
        if hasattr(event, 'project_id') and event.project_id:
            increment_project_activity(event.project_id)
    
    @global_event_bus.subscribe
    def backup_important_workflows(event: WorkflowPublishedEvent):
        """Backup workflows when they're published as templates."""
        if event.visibility == 'public':
            backup_workflow_to_storage(event.workflow_id)
```

---

## 📥📤 **Import/Export System**

### **JSON Preset Format**

The workflow system uses a standardized JSON format for sharing workflows:

```json
{
  "preset_info": {
    "name": "Workflow Name",
    "description": "Description of the workflow",
    "difficulty": "beginner|intermediate|advanced",
    "estimated_time": 240,
    "tags": ["tag1", "tag2"],
    "category": "category_name"
  },
  "workflow": {
    "name": "Internal workflow name",
    "description": "Detailed description",
    "has_multiple_outcomes": true,
    "steps": [...],
    "connections": [...],
    "outcomes": [...]
  },
  "required_resources": {
    "materials": [...],
    "tools": [...],
    "documentation": [...]
  },
  "metadata": {
    "version": "1.0",
    "created_by": "system",
    "export_format_version": "1.0",
    "exported_at": "2024-01-15T10:00:00Z"
  }
}
```

### **Step Definition Format**

```json
{
  "id": 1,
  "name": "Step Name",
  "description": "Step description",
  "instructions": "Detailed instructions for the step",
  "display_order": 1,
  "step_type": "instruction|material|tool|time|decision|milestone|outcome",
  "estimated_duration": 15,
  "is_milestone": false,
  "is_decision_point": false,
  "is_outcome": false,
  "resources": [
    {
      "resource_type": "material|tool|documentation",
      "name": "Resource name",
      "quantity": 2.5,
      "unit": "pieces",
      "is_optional": false,
      "notes": "Additional notes"
    }
  ],
  "decision_options": [
    {
      "option_text": "Choice description",
      "display_order": 1,
      "is_default": true,
      "result_action": "{\"goto_step\": 5}"
    }
  ]
}
```

### **Connection Format**

```json
{
  "source_step": 1,
  "target_step": 2,
  "connection_type": "sequential|conditional|parallel|choice|fallback|loop",
  "condition": "{\"variable\": \"value\"}",
  "is_default": true
}
```

### **Usage Examples**

#### **Importing a Preset**

```python
# Load preset from file
with open("basic_leather_project.json") as f:
    preset_data = json.load(f)

# Validate preset
errors = import_export_service.validate_preset_data(preset_data)
if errors:
    print(f"Validation errors: {errors}")
    return

# Import workflow
workflow = import_export_service.import_workflow(preset_data, user_id)
print(f"Imported workflow: {workflow.name} (ID: {workflow.id})")
```

#### **Exporting a Workflow**

```python
# Export workflow to JSON
export_data = import_export_service.export_workflow(workflow_id)

# Save to file
with open("my_custom_workflow.json", "w") as f:
    json.dump(export_data, f, indent=2, default=str)

# Or use convenience method
success = import_export_service.export_workflow_to_file(
    workflow_id, 
    "exports/my_workflow.json"
)
```

#### **Creating a Preset from Existing Workflow**

```python
# Create preset with custom metadata
preset_data = import_export_service.create_preset_from_workflow(
    workflow_id=5,
    preset_name="Advanced Leather Tooling",
    preset_description="Complex leather working techniques for experienced crafters",
    difficulty="advanced"
)

# Add custom metadata
preset_data['metadata']['tags'] = ['leather', 'advanced', 'tooling']
preset_data['metadata']['safety_notes'] = [
    "Always wear safety glasses when using power tools",
    "Ensure proper ventilation when using dyes"
]

# Save as community preset
with open("community_presets/advanced_tooling.json", "w") as f:
    json.dump(preset_data, f, indent=2, default=str)
```

### **Preset Validation**

The system validates presets before import:

```python
def validate_preset_structure(preset_data):
    """Comprehensive preset validation."""
    errors = []
    
    # Required sections
    required_sections = ['preset_info', 'workflow']
    for section in required_sections:
        if section not in preset_data:
            errors.append(f"Missing required section: {section}")
    
    # Preset info validation
    preset_info = preset_data.get('preset_info', {})
    if not preset_info.get('name'):
        errors.append("Preset info must include a name")
    
    # Workflow validation
    workflow = preset_data.get('workflow', {})
    if not workflow.get('steps'):
        errors.append("Workflow must include steps")
    
    # Step validation
    for i, step in enumerate(workflow.get('steps', [])):
        if not step.get('name'):
            errors.append(f"Step {i+1} must have a name")
        if not step.get('step_type'):
            errors.append(f"Step {i+1} must have a step_type")
    
    # Connection validation
    step_ids = {step.get('id') for step in workflow.get('steps', [])}
    for conn in workflow.get('connections', []):
        if conn.get('source_step') not in step_ids:
            errors.append(f"Invalid source step in connection: {conn.get('source_step')}")
        if conn.get('target_step') not in step_ids:
            errors.append(f"Invalid target step in connection: {conn.get('target_step')}")
    
    return errors
```

### **Community Preset Library**

#### **Sample Presets Included**

1. **Basic Leather Wallet** (`basic_leather_project.json`)
   - **Difficulty**: Beginner
   - **Duration**: 240 minutes
   - **Steps**: 12 steps from workspace setup to final conditioning
   - **Resources**: 4 materials, 6 tools

2. **Simple Wooden Box** (`simple_woodworking.json`)
   - **Difficulty**: Intermediate  
   - **Duration**: 360 minutes
   - **Steps**: 18 steps with decision points for joinery methods
   - **Resources**: 5 materials, 6 tools

#### **Preset Categories**

- **Leatherworking**: Wallets, belts, bags, sheaths
- **Woodworking**: Boxes, cutting boards, furniture, tools
- **Metalworking**: Knives, hardware, decorative items
- **Fiber Arts**: Weaving, spinning, dyeing
- **General Crafting**: Multi-material projects

---

## 🧰 **Resource Management**

### **Integration with HideSync Systems**

The workflow system seamlessly integrates with existing HideSync resource management:

#### **DynamicMaterial Integration**

```python
# Workflow steps reference dynamic materials
step_resource = {
    "resource_type": "material",
    "dynamic_material_id": 42,  # References existing material
    "quantity": 2.5,
    "unit": "sq_ft",
    "notes": "Vegetable tanned leather, 4-5oz thickness"
}

# Service integration
class WorkflowResourceService:
    def __init__(self, session: Session):
        self.dynamic_material_service = DynamicMaterialService(session)
    
    def check_material_availability(self, material_id: int, required_quantity: float):
        """Check if sufficient material is available."""
        material = self.dynamic_material_service.get_material(material_id)
        if material:
            return material.quantity >= required_quantity
        return False
```

#### **Tool System Integration**

```python
# Workflow steps reference tools from tool management
step_resource = {
    "resource_type": "tool",
    "tool_id": 15,  # References existing tool
    "notes": "Leather knife - ensure sharp blade"
}

# Tool availability checking
def check_tool_availability(self, tool_id: int, estimated_duration: float):
    """Check if tool is available for estimated duration."""
    # Integration with tool checkout/scheduling system
    tool = self.tool_service.get_tool(tool_id)
    if tool and tool.status == 'available':
        return True
    
    # Check if tool will be available in timeframe
    return self.tool_service.check_availability_window(
        tool_id, 
        start_time=datetime.utcnow(),
        duration=estimated_duration
    )
```

### **Resource Planning**

#### **Workflow Resource Analysis**

```python
# Analyze all resources needed for a workflow
analysis = resource_service.analyze_workflow_resources(workflow_id)

# Returns comprehensive analysis:
{
  "workflow_id": 1,
  "material_requirements": [
    {
      "material_id": 42,
      "name": "Vegetable Tanned Leather",
      "total_quantity": 3.0,
      "unit": "sq_ft",
      "steps": [
        {"step_id": 2, "step_name": "Cut Main Pieces", "quantity": 2.0},
        {"step_id": 5, "step_name": "Cut Card Slots", "quantity": 1.0}
      ]
    }
  ],
  "tool_requirements": [
    {
      "tool_id": 15,
      "name": "Leather Knife",
      "total_usage_time": 45,
      "steps": [
        {"step_id": 2, "estimated_duration": 30},
        {"step_id": 5, "estimated_duration": 15}
      ]
    }
  ],
  "material_availability": [
    {
      "material_id": 42,
      "available": true,
      "required_quantity": 3.0,
      "available_quantity": 5.5
    }
  ],
  "tool_availability": [
    {
      "tool_id": 15,
      "available": true,
      "scheduled_until": null
    }
  ],
  "readiness_score": 100.0
}
```

#### **Execution Readiness Check**

```python
# Check if workflow is ready for execution
readiness = resource_service.check_execution_readiness(workflow_id)

# Returns readiness assessment:
{
  "workflow_id": 1,
  "ready_for_execution": true,
  "readiness_score": 95.0,
  "blocking_issues": [],
  "warnings": [
    "Optional material unavailable: Edge Paint"
  ],
  "estimated_setup_time": 15,
  "recommendations": [
    "Gather all materials and tools before starting",
    "Review step instructions for any special requirements"
  ]
}
```

### **Resource Reservations**

#### **Automatic Resource Reservation**

```python
# Reserve resources when execution starts
@global_event_bus.subscribe
def handle_workflow_started(event: WorkflowStartedEvent):
    """Automatically reserve resources when workflow starts."""
    try:
        reservation = resource_service.reserve_execution_resources(event.execution_id)
        
        if reservation['reservation_successful']:
            logger.info(
                f"Reserved {reservation['materials_reserved']} materials and "
                f"{reservation['tools_reserved']} tools for execution {event.execution_id}"
            )
        else:
            logger.warning(f"Resource reservation failed for execution {event.execution_id}")
            
    except Exception as e:
        logger.error(f"Error reserving resources: {e}")
```

#### **Resource Release on Completion**

```python
@global_event_bus.subscribe
def handle_workflow_completed(event: WorkflowCompletedEvent):
    """Release resources when workflow completes."""
    try:
        success = resource_service.release_execution_resources(event.execution_id)
        
        if success:
            logger.info(f"Released resources for completed execution {event.execution_id}")
        else:
            logger.warning(f"Failed to release resources for execution {event.execution_id}")
            
    except Exception as e:
        logger.error(f"Error releasing resources: {e}")
```

### **Step-Level Resource Management**

#### **Preparing Resources for Steps**

```python
# Get resources needed for specific step
preparation = resource_service.prepare_step_resources(execution_id, step_id)

# Returns step-specific resource info:
{
  "execution_id": 100,
  "step_id": 5,
  "step_name": "Cut Leather Pieces",
  "materials_needed": [
    {
      "material_id": 42,
      "name": "Vegetable Tanned Leather",
      "quantity_needed": 2.0,
      "unit": "sq_ft",
      "notes": "4-5oz thickness recommended",
      "is_optional": false
    }
  ],
  "tools_needed": [
    {
      "tool_id": 15,
      "name": "Leather Knife",
      "notes": "Ensure blade is sharp",
      "is_optional": false
    }
  ],
  "preparation_notes": [
    "Gather 1 material(s) for this step",
    "Prepare 1 tool(s) for this step",
    "Estimated duration: 30 minutes"
  ],
  "estimated_setup_time": 2
}
```

#### **Recording Actual Usage**

```python
# Record actual resource usage when step completes
actual_usage = {
    "materials": {
        42: {"actual_quantity": 1.8, "notes": "Used slightly less than estimated"}
    },
    "tools": {
        15: {"actual_duration": 25, "condition": "good"}
    }
}

success = resource_service.complete_step_resource_usage(
    execution_id, 
    step_id, 
    actual_usage
)
```

### **Resource Optimization**

#### **Usage Analytics**

```python
# Track resource usage patterns for optimization
class ResourceAnalytics:
    def analyze_material_efficiency(self, workflow_id: int):
        """Analyze material usage efficiency across executions."""
        executions = self.get_completed_executions(workflow_id)
        
        efficiency_data = {}
        for execution in executions:
            for step_execution in execution.step_executions:
                if step_execution.step_data and 'resource_usage' in step_execution.step_data:
                    usage = step_execution.step_data['resource_usage']
                    
                    for material_id, usage_data in usage.get('materials', {}).items():
                        planned = usage_data.get('planned_quantity', 0)
                        actual = usage_data.get('actual_quantity', 0)
                        
                        if material_id not in efficiency_data:
                            efficiency_data[material_id] = []
                        
                        if planned > 0:
                            efficiency = actual / planned
                            efficiency_data[material_id].append(efficiency)
        
        # Calculate average efficiency per material
        return {
            material_id: sum(efficiencies) / len(efficiencies)
            for material_id, efficiencies in efficiency_data.items()
        }
```

#### **Resource Recommendations**

```python
def generate_resource_recommendations(self, workflow_id: int):
    """Generate recommendations for resource optimization."""
    analysis = self.analyze_workflow_resources(workflow_id)
    recommendations = []
    
    # Check for over-allocation
    for material in analysis['material_requirements']:
        efficiency = self.get_material_efficiency(material['material_id'])
        if efficiency and efficiency < 0.8:  # Using less than 80% of allocated
            recommendations.append({
                'type': 'optimization',
                'message': f"Consider reducing {material['name']} allocation by {(1-efficiency)*100:.1f}%",
                'material_id': material['material_id'],
                'current_allocation': material['total_quantity'],
                'suggested_allocation': material['total_quantity'] * efficiency
            })
    
    # Check for tool alternatives
    for tool in analysis['tool_requirements']:
        if not tool['available']:
            alternatives = self.find_tool_alternatives(tool['tool_id'])
            if alternatives:
                recommendations.append({
                    'type': 'substitution',
                    'message': f"Tool {tool['name']} unavailable, consider alternatives",
                    'tool_id': tool['tool_id'],
                    'alternatives': alternatives
                })
    
    return recommendations
```

---

## 🧭 **Interactive Navigation**

### **Text-Adventure Style Interface**

The navigation service provides an interactive, conversational interface for workflow execution:

#### **Navigation Context**

```python
# Get complete navigation context
context = navigation_service.get_navigation_context(execution_id, user_id)

# Returns comprehensive context:
{
  "execution_id": 100,
  "workflow_name": "Basic Leather Wallet",
  "status": "active",
  "current_step": {
    "id": 5,
    "name": "Cut Leather Pieces",
    "type": "tool",
    "description": "Cut leather pieces according to pattern",
    "status": "active",
    "is_milestone": true,
    "is_decision_point": false
  },
  "navigation_options": [
    {
      "action": "complete_step",
      "step_id": 5,
      "label": "Complete: Cut Leather Pieces",
      "description": "Mark this step as completed"
    },
    {
      "action": "navigate_to_step",
      "step_id": 6,
      "label": "Go to: Mark Stitch Lines",
      "description": "Navigate to tool step"
    },
    {
      "action": "pause",
      "label": "Pause Workflow",
      "description": "Pause execution to continue later"
    }
  ],
  "progress": {
    "total_steps": 12,
    "completed_steps": 4,
    "progress_percentage": 33.3,
    "estimated_remaining_time": 180.0
  },
  "guidance": {
    "primary": "Working on \"Cut Leather Pieces\"...",
    "secondary": "Take your time and mark complete when finished.",
    "tone": "supportive"
  },
  "recent_history": [
    {
      "timestamp": "2024-01-15T12:45:00Z",
      "action_type": "completed",
      "step_name": "Select Leather"
    }
  ]
}
```

#### **Step-Specific Guidance**

```python
# Get detailed guidance for a specific step
guidance = navigation_service.get_step_guidance(execution_id, step_id, user_id)

# Returns detailed step information:
{
  "step_id": 5,
  "step_name": "Cut Leather Pieces",
  "step_type": "tool",
  "description": "Cut leather pieces according to wallet pattern",
  "instructions": "Using a sharp knife and metal ruler, cut: 2 main body pieces (4\"x3.5\"), 2 card slot pieces (3.5\"x2.5\"). Cut slowly and steadily for clean edges.",
  "detailed_instructions": "Position the leather on your cutting mat. Use the metal ruler as a guide and apply steady, consistent pressure. Make multiple passes rather than trying to cut through in one stroke.",
  "estimated_duration": 30,
  "is_milestone": true,
  "is_decision_point": false,
  "status": "active",
  "resources": [
    {
      "type": "material",
      "quantity": 1.0,
      "unit": "sq_ft",
      "notes": "Vegetable tanned leather, 4-5oz thickness",
      "is_optional": false
    },
    {
      "type": "tool",
      "quantity": 1,
      "unit": "piece",
      "notes": "Sharp craft knife or rotary cutter",
      "is_optional": false
    }
  ],
  "decision_options": [],
  "tips": [
    "Keep knives sharp for safer cutting",
    "Cut on a self-healing cutting mat to protect your work surface",
    "Mark your pieces with chalk before cutting for accuracy"
  ],
  "warnings": [
    "Always cut away from your body",
    "Take breaks if your hand gets tired to maintain accuracy"
  ]
}
```

### **AI-Powered Suggestions**

```python
# Get smart suggestions for next actions
suggestion = navigation_service.suggest_next_action(execution_id, user_id)

# Returns contextual suggestions:
{
  "action": "complete_step",
  "step_id": 5,
  "step_name": "Cut Leather Pieces",
  "reason": "Step in progress",
  "message": "Continue working on \"Cut Leather Pieces\" and mark complete when finished.",
  "estimated_time_remaining": 15,
  "confidence": 0.95
}

# Different suggestion types based on context:
{
  "action": "navigate_to_step",
  "step_id": 1,
  "step_name": "Prepare Workspace", 
  "reason": "Start workflow execution",
  "message": "Ready to begin! Start with \"Prepare Workspace\"."
}

{
  "action": "make_decision",
  "step_id": 8,
  "step_name": "Choose Stitching Method",
  "reason": "Decision required",
  "message": "A decision is needed for \"Choose Stitching Method\".",
  "decision_options": [
    {"id": 1, "text": "Hand stitching (traditional)", "is_default": true},
    {"id": 2, "text": "Machine stitching (faster)"}
  ]
}
```

### **Natural Language Commands**

The system supports conversational interaction:

```python
# Process natural language commands
commands = [
    "help",
    "what materials do I need?",
    "show me the next step",
    "complete this step",
    "how much progress have I made?",
    "skip to step 8",
    "what tools do I need for this step?"
]

for command in commands:
    result = navigation_service.process_natural_language_command(
        execution_id, command, user_id
    )
    print(f"Command: {command}")
    print(f"Response: {result['message']}")
```

**Example Interactions:**

```python
# "help" command
{
  "success": true,
  "message": "Available commands:",
  "commands": [
    "help - Show this help",
    "status - Show current progress", 
    "next - Move to next step",
    "complete - Mark current step as complete",
    "show steps - List all steps",
    "show resources - Show required resources"
  ]
}

# "what materials do I need?" command
{
  "success": true,
  "message": "Materials for Cut Leather Pieces:",
  "resources": [
    {
      "type": "material",
      "name": "Vegetable Tanned Leather",
      "quantity": 1.0,
      "unit": "sq_ft",
      "notes": "4-5oz thickness"
    }
  ]
}

# "how much progress have I made?" command
{
  "success": true,
  "message": "Workflow: Basic Leather Wallet",
  "progress": {
    "total_steps": 12,
    "completed_steps": 4,
    "progress_percentage": 33.3,
    "current_step": "Cut Leather Pieces"
  }
}
```

### **Path Finding and Optimization**

```python
# Find optimal path through workflow
path_analysis = navigation_service.find_optimal_path(
    execution_id, 
    target_outcome_id=1,  # Specific outcome
    user_id=user_id
)

# Returns path optimization:
{
  "current_step_id": 5,
  "target_outcome_id": 1,
  "optimal_path": [
    {
      "step_id": 5,
      "step_name": "Cut Leather Pieces",
      "step_type": "tool",
      "estimated_duration": 30
    },
    {
      "step_id": 6,
      "step_name": "Mark Stitch Lines", 
      "step_type": "tool",
      "estimated_duration": 20
    },
    {
      "step_id": 7,
      "step_name": "Punch Holes",
      "step_type": "tool", 
      "estimated_duration": 25
    }
  ],
  "alternative_paths": [
    // Other possible paths
  ],
  "estimated_time": 75,
  "difficulty_score": 4
}
```

### **Interactive Features**

#### **Progress Visualization**

```python
def generate_progress_display(execution_id: int):
    """Generate ASCII art progress display."""
    progress = navigation_service.get_execution_progress(execution_id)
    
    total_steps = progress['total_steps']
    completed_steps = progress['completed_steps']
    current_step = progress['current_step_name']
    
    # ASCII progress bar
    bar_length = 20
    filled_length = int(bar_length * completed_steps / total_steps)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    return f"""
Progress: {completed_steps}/{total_steps} ({progress['progress_percentage']:.1f}%)
[{bar}]

Current Step: {current_step}
Estimated Remaining: {progress.get('estimated_remaining_time', 'Unknown')} minutes
    """.strip()
```

#### **Step-by-Step Guidance**

```python
def provide_step_guidance(execution_id: int, step_id: int):
    """Provide comprehensive step guidance."""
    guidance = navigation_service.get_step_guidance(execution_id, step_id, user_id)
    
    # Format guidance for display
    output = [
        f"=== {guidance['step_name']} ===",
        f"Type: {guidance['step_type'].title()}",
        f"Duration: ~{guidance['estimated_duration']} minutes",
        "",
        "Instructions:",
        guidance['instructions'],
        ""
    ]
    
    if guidance['resources']:
        output.append("Resources Needed:")
        for resource in guidance['resources']:
            optional = " (optional)" if resource['is_optional'] else ""
            output.append(f"  • {resource['quantity']} {resource['unit']} {resource['type']}{optional}")
            if resource['notes']:
                output.append(f"    Note: {resource['notes']}")
        output.append("")
    
    if guidance['tips']:
        output.append("💡 Tips:")
        for tip in guidance['tips']:
            output.append(f"  • {tip}")
        output.append("")
    
    if guidance['warnings']:
        output.append("⚠️  Important:")
        for warning in guidance['warnings']:
            output.append(f"  • {warning}")
    
    return "\n".join(output)
```

---

## ⚙️ **Setup & Configuration**

### **Installation Steps**

#### **1. Database Setup**

```bash
# Run the main database setup (includes workflow tables)
python scripts/setup_database.py

# Verify workflow tables were created
python -c "
from app.db.session import SessionLocal
from sqlalchemy import inspect
db = SessionLocal()
inspector = inspect(db.bind)
tables = inspector.get_table_names()
workflow_tables = [t for t in tables if 'workflow' in t]
print(f'Workflow tables created: {len(workflow_tables)}')
print(workflow_tables)
"
```

#### **2. Enum Configuration**

```bash
# Set up workflow enum types (run FIRST)
python scripts/setup_workflow_enum_types.py

# Set up workflow enum values (run SECOND)
python scripts/setup_workflow_enums.py

# Verify enums were created
python -c "
from app.services.enum_service import EnumService
from app.db.session import SessionLocal
db = SessionLocal()
enum_service = EnumService(db)
step_types = enum_service.get_enum_values('workflow_step_type', 'en')
print(f'Step types configured: {len(step_types)}')
for st in step_types:
    print(f'  - {st[\"code\"]}: {st[\"display_text\"]}')
"
```

#### **3. API Integration**

Update your main API router:

```python
# app/api/api.py
from app.api.endpoints import workflows

api_router.include_router(
    workflows.router,
    prefix="/workflows", 
    tags=["workflows"]
)
```

#### **4. Event Handler Setup**

```python
# app/main.py or startup code
from app.services.workflow_event_handlers import setup_workflow_event_handlers
from app.db.session import SessionLocal

@app.on_event("startup")
async def configure_workflow_events():
    """Set up workflow event handlers."""
    session = SessionLocal()
    try:
        setup_workflow_event_handlers(session)
    finally:
        session.close()
```

### **Environment Configuration**

#### **Required Environment Variables**

```bash
# Database configuration (should already be set)
DATABASE_URL=postgresql://user:password@localhost/hidesync

# Optional workflow-specific settings
WORKFLOW_MAX_EXECUTION_TIME=86400  # 24 hours in seconds
WORKFLOW_AUTO_CLEANUP_DAYS=30      # Clean up old executions
WORKFLOW_ENABLE_ANALYTICS=true     # Enable analytics tracking
WORKFLOW_PRESET_DIRECTORY=./scripts/workflow_presets/
```

#### **Application Configuration**

```python
# app/core/config.py additions
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Workflow system settings
    workflow_max_execution_time: int = 86400
    workflow_auto_cleanup_days: int = 30
    workflow_enable_analytics: bool = True
    workflow_preset_directory: str = "./scripts/workflow_presets/"
    workflow_enable_events: bool = True
    workflow_enable_resource_tracking: bool = True
```

### **Initial Data Setup**

#### **Load Sample Presets**

```python
# scripts/load_sample_presets.py
import json
import os
from app.db.session import SessionLocal
from app.services.workflow_import_export_service import WorkflowImportExportService

def load_sample_presets():
    """Load sample workflow presets."""
    session = SessionLocal()
    import_export_service = WorkflowImportExportService(session)
    
    preset_dir = "scripts/workflow_presets/"
    preset_files = [
        "basic_leather_project.json",
        "simple_woodworking.json"
    ]
    
    admin_user_id = 1  # Replace with actual admin user ID
    
    for preset_file in preset_files:
        file_path = os.path.join(preset_dir, preset_file)
        if os.path.exists(file_path):
            try:
                workflow = import_export_service.import_workflow_from_file(
                    file_path, admin_user_id
                )
                print(f"✅ Loaded preset: {workflow.name} (ID: {workflow.id})")
            except Exception as e:
                print(f"❌ Error loading {preset_file}: {e}")
        else:
            print(f"⚠️  Preset file not found: {file_path}")
    
    session.close()

if __name__ == "__main__":
    load_sample_presets()
```

```bash
# Run the preset loader
python scripts/load_sample_presets.py
```

### **Dependency Injection Setup**

Update your dependency injection:

```python
# app/api/deps.py additions (if not already added)
def get_workflow_service(
    db: Session = Depends(get_db),
    security_context=Depends(get_security_context)
) -> WorkflowService:
    """Provides an instance of WorkflowService."""
    return WorkflowService(session=db, security_context=security_context)

def get_workflow_execution_service(
    db: Session = Depends(get_db),
    workflow_service: WorkflowService = Depends(get_workflow_service)
) -> WorkflowExecutionService:
    """Provides an instance of WorkflowExecutionService."""
    return WorkflowExecutionService(session=db, workflow_service=workflow_service)

# Add other workflow service dependencies...
```

### **Repository Factory Updates**

```python
# app/repositories/repository_factory.py additions
class RepositoryFactory:
    def create_workflow_repository(self) -> WorkflowRepository:
        """Create a WorkflowRepository instance."""
        return WorkflowRepository(self.session, self.encryption_service)
    
    def create_workflow_step_repository(self) -> WorkflowStepRepository:
        """Create a WorkflowStepRepository instance."""
        return WorkflowStepRepository(self.session, self.encryption_service)
    
    def create_workflow_execution_repository(self) -> WorkflowExecutionRepository:
        """Create a WorkflowExecutionRepository instance."""
        return WorkflowExecutionRepository(self.session, self.encryption_service)
```

### **Validation and Testing**

#### **System Health Check**

```python
# scripts/validate_workflow_setup.py
from app.db.session import SessionLocal
from app.services.workflow_service import WorkflowService
from app.services.enum_service import EnumService

def validate_workflow_setup():
    """Validate that workflow system is properly configured."""
    session = SessionLocal()
    errors = []
    
    try:
        # Check enum setup
        enum_service = EnumService(session)
        step_types = enum_service.get_enum_values('workflow_step_type', 'en')
        if len(step_types) < 7:
            errors.append(f"Insufficient step types: {len(step_types)} (expected at least 7)")
        
        # Check workflow service
        workflow_service = WorkflowService(session)
        templates = workflow_service.get_workflow_templates()
        print(f"✅ Found {len(templates)} workflow templates")
        
        # Check repository factory
        from app.repositories.repository_factory import RepositoryFactory
        factory = RepositoryFactory(session)
        workflow_repo = factory.create_workflow_repository()
        print("✅ Repository factory working")
        
        if errors:
            for error in errors:
                print(f"❌ {error}")
            return False
        else:
            print("✅ Workflow system validation passed!")
            return True
            
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False
    finally:
        session.close()

if __name__ == "__main__":
    validate_workflow_setup()
```

```bash
# Run validation
python scripts/validate_workflow_setup.py
```

### **Monitoring and Logging**

#### **Logging Configuration**

```python
# app/core/logging.py additions
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        # ... existing loggers ...
        "hidesync.workflows": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False
        },
        "hidesync.workflow.execution": {
            "level": "DEBUG", 
            "handlers": ["default"],
            "propagate": False
        },
        "hidesync.workflow.events": {
            "level": "INFO",
            "handlers": ["default"],
            "propagate": False
        }
    }
}
```

#### **Performance Monitoring**

```python
# scripts/monitor_workflow_performance.py
import time
from collections import defaultdict
from app.core.events import global_event_bus

class WorkflowPerformanceMonitor:
    def __init__(self):
        self.metrics = defaultdict(list)
        self.setup_monitoring()
    
    def setup_monitoring(self):
        """Set up performance monitoring."""
        @global_event_bus.subscribe
        def track_execution_time(event):
            if hasattr(event, 'execution_id') and hasattr(event, 'total_duration'):
                self.metrics['execution_duration'].append(event.total_duration)
        
        @global_event_bus.subscribe
        def track_step_time(event):
            if hasattr(event, 'actual_duration') and event.actual_duration:
                self.metrics['step_duration'].append(event.actual_duration)
    
    def get_performance_summary(self):
        """Get performance metrics summary."""
        summary = {}
        
        for metric_name, values in self.metrics.items():
            if values:
                summary[metric_name] = {
                    'count': len(values),
                    'average': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values)
                }
        
        return summary

# Enable monitoring
monitor = WorkflowPerformanceMonitor()
```

---

## 📚 **Usage Examples**

### **Basic Workflow Creation**

```python
from app.services.workflow_service import WorkflowService
from app.db.session import SessionLocal

# Initialize service
session = SessionLocal()
workflow_service = WorkflowService(session)

# Create a simple workflow
workflow_data = {
    "name": "Basic Project Workflow",
    "description": "A simple workflow for beginners",
    "difficulty_level": "beginner",
    "estimated_duration": 120,
    "has_multiple_outcomes": False
}

workflow = workflow_service.create_workflow(workflow_data, user_id=1)
print(f"Created workflow: {workflow.name} (ID: {workflow.id})")
```

### **Adding Steps to Workflow**

```python
from app.repositories.workflow_step_repository import WorkflowStepRepository
from app.repositories.repository_factory import RepositoryFactory

# Initialize repository
factory = RepositoryFactory(session)
step_repo = factory.create_workflow_step_repository()

# Define steps
steps = [
    {
        "workflow_id": workflow.id,
        "name": "Gather Materials",
        "description": "Collect all required materials",
        "step_type": "material",
        "display_order": 1,
        "estimated_duration": 15,
        "instructions": "Review the materials list and gather everything you need."
    },
    {
        "workflow_id": workflow.id,
        "name": "Prepare Workspace",
        "description": "Set up your work area",
        "step_type": "instruction",
        "display_order": 2,
        "estimated_duration": 10,
        "instructions": "Clear your workspace and organize tools."
    },
    {
        "workflow_id": workflow.id,
        "name": "Begin Crafting",
        "description": "Start the main crafting work",
        "step_type": "tool",
        "display_order": 3,
        "estimated_duration": 90,
        "is_milestone": True,
        "instructions": "Follow the detailed crafting instructions."
    }
]

# Create steps with resources
for step_data in steps:
    resources = []
    
    if step_data["step_type"] == "material":
        resources = [
            {
                "resource_type": "material",
                "dynamic_material_id": 1,  # Replace with actual material ID
                "quantity": 1.0,
                "unit": "piece",
                "notes": "Primary material for project"
            }
        ]
    elif step_data["step_type"] == "tool":
        resources = [
            {
                "resource_type": "tool",
                "tool_id": 1,  # Replace with actual tool ID
                "notes": "Primary crafting tool"
            }
        ]
    
    step = step_repo.create_step_with_resources(step_data, resources)
    print(f"Created step: {step.name}")
```

### **Creating Step Connections**

```python
# Get the created steps
steps = step_repo.get_workflow_steps_ordered(workflow.id)

# Create sequential connections
for i in range(len(steps) - 1):
    connection = step_repo.create_step_connection(
        source_step_id=steps[i].id,
        target_step_id=steps[i + 1].id,
        connection_type="sequential"
    )
    print(f"Connected step {steps[i].name} → {steps[i + 1].name}")
```

### **Starting and Managing Execution**

```python
from app.services.workflow_execution_service import WorkflowExecutionService

# Initialize execution service
execution_service = WorkflowExecutionService(session, workflow_service)

# Start workflow execution
execution = workflow_service.start_workflow_execution(workflow.id, user_id=1)
print(f"Started execution: {execution.id}")

# Get execution progress
progress = execution_service.get_execution_progress(execution.id, user_id=1)
print(f"Progress: {progress['completed_steps']}/{progress['total_steps']} steps")

# Navigate to first step
first_step = steps[0]
execution = execution_service.navigate_to_step(execution.id, first_step.id, user_id=1)
print(f"Navigated to: {first_step.name}")

# Complete the step
completion_data = {
    "notes": "Successfully gathered all materials",
    "actual_duration": 12.0
}
execution = execution_service.complete_step(
    execution.id, 
    first_step.id, 
    user_id=1, 
    completion_data=completion_data
)
print(f"Completed step: {first_step.name}")
```

### **Interactive Navigation Example**

```python
from app.services.workflow_navigation_service import WorkflowNavigationService

# Initialize navigation service
navigation_service = WorkflowNavigationService(session, execution_service)

# Get navigation context
context = navigation_service.get_navigation_context(execution.id, user_id=1)
print(f"Current step: {context['current_step']['name']}")
print(f"Progress: {context['progress']['progress_percentage']:.1f}%")

# Get step guidance
current_step_id = context['current_step']['id']
guidance = navigation_service.get_step_guidance(execution.id, current_step_id, user_id=1)
print(f"Instructions: {guidance['instructions']}")

# Get AI suggestions
suggestion = navigation_service.suggest_next_action(execution.id, user_id=1)
print(f"Suggestion: {suggestion['message']}")

# Process natural language commands
commands = ["help", "what do I need?", "complete this step"]
for command in commands:
    result = navigation_service.process_natural_language_command(
        execution.id, command, user_id=1
    )
    print(f"'{command}' → {result['message']}")
```

### **Resource Management Example**

```python
from app.services.workflow_resource_service import WorkflowResourceService

# Initialize resource service
resource_service = WorkflowResourceService(session)

# Analyze workflow resources
analysis = resource_service.analyze_workflow_resources(workflow.id)
print(f"Materials needed: {len(analysis['material_requirements'])}")
print(f"Tools needed: {len(analysis['tool_requirements'])}")
print(f"Readiness score: {analysis['readiness_score']}/100")

# Check execution readiness
readiness = resource_service.check_execution_readiness(workflow.id)
if readiness['ready_for_execution']:
    print("✅ Workflow is ready for execution")
else:
    print("❌ Workflow has blocking issues:")
    for issue in readiness['blocking_issues']:
        print(f"  - {issue}")

# Reserve resources for execution
if readiness['ready_for_execution']:
    reservation = resource_service.reserve_execution_resources(execution.id)
    if reservation['reservation_successful']:
        print(f"✅ Reserved {reservation['materials_reserved']} materials")
```

### **Import/Export Example**

```python
from app.services.workflow_import_export_service import WorkflowImportExportService
import json

# Initialize import/export service
import_export_service = WorkflowImportExportService(session, workflow_service)

# Export workflow to JSON
export_data = import_export_service.export_workflow(workflow.id)
print(f"Exported workflow: {export_data['preset_info']['name']}")

# Save to file
with open("my_workflow_export.json", "w") as f:
    json.dump(export_data, f, indent=2, default=str)
print("Saved to my_workflow_export.json")

# Import a preset
preset_file = "scripts/workflow_presets/basic_leather_project.json"
try:
    imported_workflow = import_export_service.import_workflow_from_file(
        preset_file, user_id=1
    )
    print(f"Imported workflow: {imported_workflow.name}")
except Exception as e:
    print(f"Import failed: {e}")
```

### **Advanced Workflow with Decision Points**

```python
# Create workflow with decision points
advanced_workflow_data = {
    "name": "Advanced Crafting Workflow",
    "description": "Workflow with multiple paths and decision points",
    "difficulty_level": "intermediate",
    "estimated_duration": 240,
    "has_multiple_outcomes": True
}

advanced_workflow = workflow_service.create_workflow(advanced_workflow_data, user_id=1)

# Create decision step
decision_step_data = {
    "workflow_id": advanced_workflow.id,
    "name": "Choose Construction Method",
    "description": "Select your preferred construction approach",
    "step_type": "decision",
    "display_order": 3,
    "is_decision_point": True,
    "instructions": "Consider your skill level and available time."
}

decision_options = [
    {
        "option_text": "Traditional hand method (slower, more authentic)",
        "display_order": 1,
        "is_default": True,
        "result_action": json.dumps({"set_variable": {"method": "hand"}})
    },
    {
        "option_text": "Modern power tool method (faster, requires tools)",
        "display_order": 2,
        "is_default": False,
        "result_action": json.dumps({"set_variable": {"method": "power"}})
    }
]

decision_step = step_repo.create_step_with_resources(
    decision_step_data, 
    resources=[], 
    decision_options=decision_options
)

print(f"Created decision step with {len(decision_options)} options")

# Create outcome-specific steps
hand_method_step = {
    "workflow_id": advanced_workflow.id,
    "name": "Hand Construction Process",
    "description": "Traditional hand crafting approach",
    "step_type": "tool",
    "display_order": 4,
    "estimated_duration": 120,
    "instructions": "Use traditional hand tools and techniques.",
    "condition_logic": json.dumps({"if": {"method": "hand"}})
}

power_method_step = {
    "workflow_id": advanced_workflow.id,
    "name": "Power Tool Construction",
    "description": "Modern power tool approach",
    "step_type": "tool", 
    "display_order": 5,
    "estimated_duration": 60,
    "instructions": "Use power tools for faster construction.",
    "condition_logic": json.dumps({"if": {"method": "power"}})
}

# Create both method steps
hand_step = step_repo.create_step_with_resources(hand_method_step)
power_step = step_repo.create_step_with_resources(power_method_step)

# Create conditional connections
step_repo.create_step_connection(
    source_step_id=decision_step.id,
    target_step_id=hand_step.id,
    connection_type="conditional",
    condition=json.dumps({"method": "hand"})
)

step_repo.create_step_connection(
    source_step_id=decision_step.id,
    target_step_id=power_step.id,
    connection_type="conditional", 
    condition=json.dumps({"method": "power"})
)

print("Created conditional workflow paths")

# Create multiple outcomes
outcomes = [
    {
        "workflow_id": advanced_workflow.id,
        "name": "Handcrafted Premium Item",
        "description": "High-quality item made with traditional methods",
        "is_default": False,
        "display_order": 1
    },
    {
        "workflow_id": advanced_workflow.id,
        "name": "Efficient Modern Item", 
        "description": "Well-made item using modern techniques",
        "is_default": True,
        "display_order": 2
    }
]

for outcome_data in outcomes:
    outcome = WorkflowOutcome(**outcome_data)
    session.add(outcome)

session.commit()
print(f"Created {len(outcomes)} outcome options")
```

### **Event-Driven Workflow Management**

```python
from app.core.events import global_event_bus
from app.services.workflow_event_handlers import WorkflowEventHandlers

# Set up custom event handlers
def setup_custom_handlers():
    """Set up custom workflow event handlers."""
    
    @global_event_bus.subscribe
    def track_user_progress(event):
        """Track user progress across all workflows."""
        if hasattr(event, 'user_id') and hasattr(event, 'workflow_id'):
            # Update user statistics
            update_user_workflow_stats(event.user_id, event.workflow_id)
    
    @global_event_bus.subscribe
    def auto_backup_completed_workflows(event):
        """Backup completed workflow executions."""
        if event.__class__.__name__ == 'WorkflowCompletedEvent':
            backup_execution_data(event.execution_id)
    
    @global_event_bus.subscribe
    def suggest_next_workflows(event):
        """Suggest related workflows when one completes."""
        if event.__class__.__name__ == 'WorkflowCompletedEvent':
            suggestions = find_related_workflows(event.workflow_id)
            send_workflow_suggestions(event.user_id, suggestions)

# Initialize custom handlers
setup_custom_handlers()

# Start workflow and observe events
execution = workflow_service.start_workflow_execution(workflow.id, user_id=1)
# This triggers WorkflowStartedEvent

# Complete steps to see events in action
for step in steps:
    execution_service.navigate_to_step(execution.id, step.id, user_id=1)
    # Triggers StepNavigationEvent
    
    execution_service.complete_step(execution.id, step.id, user_id=1)
    # Triggers StepCompletedEvent

# Workflow completion triggers WorkflowCompletedEvent
```

---

## 🎯 **Best Practices**

### **Workflow Design Principles**

#### **1. Clear Step Definitions**

```python
# ✅ Good: Clear, actionable step
{
    "name": "Cut Leather to Pattern",
    "description": "Cut main body pieces according to template",
    "instructions": "Place pattern on leather, trace with awl, cut with sharp knife using metal ruler guide. Cut 2 pieces.",
    "step_type": "tool",
    "estimated_duration": 30
}

# ❌ Poor: Vague, confusing step  
{
    "name": "Do leather stuff",
    "description": "Cut things",
    "instructions": "Cut the leather somehow",
    "step_type": "instruction"
}
```

#### **2. Logical Step Sequencing**

```python
# ✅ Good: Logical flow with dependencies
workflow_steps = [
    {"name": "Prepare Workspace", "display_order": 1},
    {"name": "Select Materials", "display_order": 2}, 
    {"name": "Cut Pieces", "display_order": 3},       # Depends on materials
    {"name": "Mark Guidelines", "display_order": 4},   # Depends on cut pieces
    {"name": "Punch Holes", "display_order": 5},      # Depends on guidelines
    {"name": "Stitch Together", "display_order": 6}    # Depends on holes
]

# ❌ Poor: Random order without logic
workflow_steps = [
    {"name": "Stitch Together", "display_order": 1},   # Can't stitch without pieces!
    {"name": "Select Materials", "display_order": 2},
    {"name": "Punch Holes", "display_order": 3},       # No pieces to punch!
    {"name": "Cut Pieces", "display_order": 4}
]
```

#### **3. Appropriate Resource Planning**

```python
# ✅ Good: Specific, measurable resources
step_resources = [
    {
        "resource_type": "material",
        "dynamic_material_id": 42,
        "quantity": 0.25,
        "unit": "sq_ft",
        "notes": "Vegetable tanned leather, 4-5oz thickness"
    },
    {
        "resource_type": "tool",
        "tool_id": 15,
        "notes": "Sharp craft knife with new blade"
    }
]

# ❌ Poor: Vague, unmeasurable resources
step_resources = [
    {
        "resource_type": "material", 
        "notes": "Some leather"  # How much? What type?
    },
    {
        "resource_type": "tool",
        "notes": "A knife"       # What kind? Sharp?
    }
]
```

### **Performance Optimization**

#### **1. Efficient Database Queries**

```python
# ✅ Good: Use eager loading for related data
def get_workflow_for_execution(workflow_id: int):
    """Efficiently load workflow with all needed relationships."""
    return session.query(Workflow).options(
        selectinload(Workflow.steps).options(
            selectinload(WorkflowStep.resources),
            selectinload(WorkflowStep.decision_options),
            selectinload(WorkflowStep.outgoing_connections)
        ),
        selectinload(Workflow.outcomes)
    ).filter(Workflow.id == workflow_id).first()

# ❌ Poor: N+1 query problem
def get_workflow_inefficient(workflow_id: int):
    """This will cause many separate queries."""
    workflow = session.query(Workflow).filter(Workflow.id == workflow_id).first()
    # Each step access triggers a new query
    for step in workflow.steps:
        print(step.resources)  # New query for each step
        print(step.decision_options)  # Another query for each step
```

#### **2. Smart Caching Strategies**

```python
from functools import lru_cache
from typing import Dict, Any

class WorkflowCache:
    """Cache frequently accessed workflow data."""
    
    @lru_cache(maxsize=100)
    def get_workflow_templates(self, user_id: Optional[int] = None) -> Tuple[WorkflowTemplate, ...]:
        """Cache workflow templates (they change infrequently)."""
        templates = self.workflow_repo.get_workflow_templates(user_id)
        return tuple(templates)  # Immutable for caching
    
    @lru_cache(maxsize=50)
    def get_step_types(self, locale: str = 'en') -> Tuple[Dict[str, Any], ...]:
        """Cache step type enums."""
        step_types = self.enum_service.get_enum_values('workflow_step_type', locale)
        return tuple(step_types)
    
    def invalidate_workflow_cache(self, workflow_id: int):
        """Invalidate cache when workflow changes."""
        # Clear relevant cache entries
        self.get_workflow_templates.cache_clear()
```

#### **3. Pagination and Limits**

```python
# ✅ Good: Always use pagination for lists
def search_workflows_efficiently(search_params: Dict[str, Any]):
    """Implement proper pagination."""
    # Enforce reasonable limits
    limit = min(search_params.get('limit', 50), 100)  # Max 100 items
    offset = search_params.get('offset', 0)
    
    # Use database-level pagination
    query = session.query(Workflow)
    # ... apply filters ...
    
    total = query.count()  # Get total before limiting
    items = query.offset(offset).limit(limit).all()
    
    return {
        'items': items,
        'total': total,
        'limit': limit,
        'offset': offset,
        'has_more': offset + limit < total
    }
```

### **Error Handling and Validation**

#### **1. Comprehensive Input Validation**

```python
def validate_workflow_data(workflow_data: Dict[str, Any]) -> List[str]:
    """Comprehensive workflow validation."""
    errors = []
    
    # Required fields
    if not workflow_data.get('name'):
        errors.append("Workflow name is required")
    elif len(workflow_data['name']) > 200:
        errors.append("Workflow name must be 200 characters or less")
    
    # Duration validation
    if 'estimated_duration' in workflow_data:
        duration = workflow_data['estimated_duration']
        if duration is not None:
            if not isinstance(duration, (int, float)):
                errors.append("Estimated duration must be a number")
            elif duration < 0:
                errors.append("Estimated duration cannot be negative")
            elif duration > 86400:  # 24 hours
                errors.append("Estimated duration cannot exceed 24 hours")
    
    # Enum validation
    if 'difficulty_level' in workflow_data:
        valid_levels = ['beginner', 'intermediate', 'advanced', 'expert']
        if workflow_data['difficulty_level'] not in valid_levels:
            errors.append(f"Difficulty level must be one of: {valid_levels}")
    
    return errors
```

#### **2. Graceful Error Recovery**

```python
class WorkflowExecutionService:
    def complete_step_with_recovery(self, execution_id: int, step_id: int, 
                                    user_id: int, completion_data: Optional[Dict] = None):
        """Complete step with error recovery."""
        try:
            return self.complete_step(execution_id, step_id, user_id, completion_data)
            
        except ValidationException as e:
            # Log validation error and provide helpful message
            logger.warning(f"Step completion validation failed: {e}")
            raise BusinessRuleException(
                f"Cannot complete step: {e}. Please check the step requirements."
            )
            
        except DatabaseException as e:
            # Handle database errors gracefully
            logger.error(f"Database error completing step: {e}")
            # Try to recover by refreshing the execution state
            try:
                execution = self.get_execution(execution_id, user_id)
                if execution.status == 'active':
                    # Retry once
                    return self.complete_step(execution_id, step_id, user_id, completion_data)
            except:
                pass
            
            raise BusinessRuleException(
                "A system error occurred. Please try again or contact support."
            )
            
        except Exception as e:
            # Log unexpected errors
            logger.error(f"Unexpected error completing step: {e}", exc_info=True)
            raise BusinessRuleException(
                "An unexpected error occurred. Please try again later."
            )
```

### **Security Considerations**

#### **1. Access Control**

```python
def check_workflow_access(workflow: Workflow, user_id: int, action: str) -> bool:
    """Comprehensive access control checking."""
    
    # Owner always has full access
    if workflow.created_by == user_id:
        return True
    
    # Public workflows - read-only access
    if workflow.visibility == 'public':
        return action in ['read', 'execute', 'duplicate']
    
    # Shared workflows - check sharing permissions
    if workflow.visibility == 'shared':
        return check_sharing_permissions(workflow.id, user_id, action)
    
    # Private workflows - owner only
    return False

def secure_workflow_operation(func):
    """Decorator for securing workflow operations."""
    def wrapper(self, workflow_id: int, user_id: int, *args, **kwargs):
        workflow = self.workflow_repo.get_by_id(workflow_id)
        if not workflow:
            raise EntityNotFoundException("Workflow", workflow_id)
        
        # Determine required action based on function name
        action_map = {
            'get_workflow': 'read',
            'update_workflow': 'write', 
            'delete_workflow': 'delete',
            'start_workflow_execution': 'execute'
        }
        required_action = action_map.get(func.__name__, 'read')
        
        if not check_workflow_access(workflow, user_id, required_action):
            raise BusinessRuleException("Insufficient permissions for this operation")
        
        return func(self, workflow_id, user_id, *args, **kwargs)
    return wrapper
```

#### **2. Input Sanitization**

```python
import html
import re
from typing import Any, Dict

def sanitize_workflow_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize workflow input data."""
    sanitized = {}
    
    # Text fields - escape HTML and limit length
    text_fields = ['name', 'description', 'instructions']
    for field in text_fields:
        if field in data and data[field]:
            # Remove potentially dangerous characters
            value = str(data[field])
            value = html.escape(value)  # Escape HTML
            value = re.sub(r'[<>]', '', value)  # Remove angle brackets
            value = value.strip()[:1000]  # Limit length
            sanitized[field] = value
    
    # Numeric fields - validate ranges
    numeric_fields = ['estimated_duration', 'display_order']
    for field in numeric_fields:
        if field in data and data[field] is not None:
            try:
                value = float(data[field])
                if field == 'estimated_duration' and (value < 0 or value > 86400):
                    raise ValueError("Duration out of range")
                if field == 'display_order' and (value < 1 or value > 1000):
                    raise ValueError("Display order out of range")
                sanitized[field] = value
            except (ValueError, TypeError):
                raise ValidationException(f"Invalid {field} value")
    
    return sanitized
```

### **Testing Strategies**

#### **1. Unit Test Examples**

```python
import pytest
from unittest.mock import Mock, patch
from app.services.workflow_service import WorkflowService
from app.core.exceptions import ValidationException, BusinessRuleException

class TestWorkflowService:
    
    def test_create_workflow_success(self):
        """Test successful workflow creation."""
        mock_repo = Mock()
        mock_repo.create.return_value = Mock(id=1, name="Test Workflow")
        
        service = WorkflowService(Mock(), repository=mock_repo)
        
        workflow_data = {
            "name": "Test Workflow",
            "description": "Test description",
            "difficulty_level": "beginner"
        }
        
        result = service.create_workflow(workflow_data, user_id=1)
        
        assert result.id == 1
        assert result.name == "Test Workflow"
        mock_repo.create.assert_called_once()
    
    def test_create_workflow_duplicate_name(self):
        """Test workflow creation with duplicate name."""
        mock_repo = Mock()
        mock_repo.get_workflow_by_name.return_value = Mock(id=1)  # Existing workflow
        
        service = WorkflowService(Mock(), repository=mock_repo)
        
        workflow_data = {"name": "Duplicate Name"}
        
        with pytest.raises(BusinessRuleException, match="already exists"):
            service.create_workflow(workflow_data, user_id=1)
    
    def test_create_workflow_validation_error(self):
        """Test workflow creation with invalid data."""
        service = WorkflowService(Mock())
        
        workflow_data = {"name": ""}  # Empty name
        
        with pytest.raises(ValidationException, match="name is required"):
            service.create_workflow(workflow_data, user_id=1)
```

#### **2. Integration Test Examples**

```python
import pytest
from app.db.session import SessionLocal
from app.services.workflow_service import WorkflowService

@pytest.fixture
def db_session():
    """Create a test database session."""
    session = SessionLocal()
    yield session
    session.rollback()  # Rollback any changes
    session.close()

@pytest.fixture 
def test_user(db_session):
    """Create a test user."""
    from app.db.models.user import User
    user = User(email="test@example.com", username="testuser")
    db_session.add(user)
    db_session.commit()
    return user

class TestWorkflowIntegration:
    
    def test_complete_workflow_lifecycle(self, db_session, test_user):
        """Test complete workflow creation and execution lifecycle."""
        workflow_service = WorkflowService(db_session)
        
        # Create workflow
        workflow_data = {
            "name": "Integration Test Workflow",
            "description": "Test workflow for integration testing",
            "difficulty_level": "beginner",
            "estimated_duration": 60
        }
        
        workflow = workflow_service.create_workflow(workflow_data, test_user.id)
        assert workflow.id is not None
        assert workflow.name == "Integration Test Workflow"
        
        # Add steps
        from app.repositories.repository_factory import RepositoryFactory
        factory = RepositoryFactory(db_session)
        step_repo = factory.create_workflow_step_repository()
        
        step_data = {
            "workflow_id": workflow.id,
            "name": "Test Step",
            "step_type": "instruction",
            "display_order": 1
        }
        
        step = step_repo.create_step_with_resources(step_data)
        assert step.id is not None
        
        # Start execution
        execution = workflow_service.start_workflow_execution(workflow.id, test_user.id)
        assert execution.status == "active"
        
        # Complete workflow
        from app.services.workflow_execution_service import WorkflowExecutionService
        execution_service = WorkflowExecutionService(db_session, workflow_service)
        
        execution_service.navigate_to_step(execution.id, step.id, test_user.id)
        updated_execution = execution_service.complete_step(execution.id, step.id, test_user.id)
        
        # Verify completion
        progress = execution_service.get_execution_progress(execution.id, test_user.id)
        assert progress['completed_steps'] == 1
```

---

## 🔧 **Troubleshooting**

### **Common Issues and Solutions**

#### **1. Database Connection Issues**

**Problem**: `sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server`

**Solutions**:
```python
# Check database connection
def test_database_connection():
    """Test database connectivity."""
    try:
        from app.db.session import SessionLocal
        session = SessionLocal()
        result = session.execute("SELECT 1").scalar()
        print(f"✅ Database connection successful: {result}")
        session.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

# Verify environment variables
import os
print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set')}")

# Check if workflow tables exist
def check_workflow_tables():
    """Verify workflow tables exist."""
    from sqlalchemy import inspect
    from app.db.session import engine
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    workflow_tables = [t for t in tables if 'workflow' in t]
    
    print(f"Found {len(workflow_tables)} workflow tables:")
    for table in workflow_tables:
        print(f"  - {table}")
    
    return len(workflow_tables) >= 10  # Should have at least 10 workflow tables
```

#### **2. Enum Configuration Problems**

**Problem**: `ValidationException: Invalid status: draft. Valid options: []`

**Solutions**:
```bash
# Re-run enum setup scripts
python scripts/setup_workflow_enum_types.py
python scripts/setup_workflow_enums.py

# Verify enum data
python -c "
from app.services.enum_service import EnumService
from app.db.session import SessionLocal
session = SessionLocal()
enum_service = EnumService(session)

try:
    statuses = enum_service.get_enum_values('workflow_status', 'en')
    print(f'✅ Found {len(statuses)} workflow statuses')
    for status in statuses:
        print(f'  - {status[\"code\"]}')
except Exception as e:
    print(f'❌ Error loading statuses: {e}')
"
```

**Manual enum repair**:
```python
def repair_workflow_enums():
    """Manually repair workflow enum data."""
    from app.db.session import SessionLocal
    from sqlalchemy import text
    
    session = SessionLocal()
    
    # Check if enum tables exist
    result = session.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name LIKE 'enum_value_workflow_%'
    """)).fetchall()
    
    print(f"Found {len(result)} enum tables")
    
    # Check enum data
    for table_name, in result:
        count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        print(f"{table_name}: {count} values")
        
        if count == 0:
            print(f"⚠️  {table_name} is empty - re-run setup scripts")
```

#### **3. Import/Export Failures**

**Problem**: `ValidationException: Import validation failed: Missing required field: workflow`

**Solutions**:
```python
def debug_import_failure(preset_file: str):
    """Debug workflow import issues."""
    import json
    
    try:
        with open(preset_file) as f:
            data = json.load(f)
        
        print("✅ JSON file loaded successfully")
        
        # Check required sections
        required = ['preset_info', 'workflow']
        for section in required:
            if section in data:
                print(f"✅ Section '{section}' found")
            else:
                print(f"❌ Missing section '{section}'")
        
        # Check workflow structure
        if 'workflow' in data:
            workflow = data['workflow']
            if 'steps' in workflow:
                print(f"✅ Found {len(workflow['steps'])} steps")
            else:
                print("❌ No steps in workflow")
        
        # Validate with service
        from app.services.workflow_import_export_service import WorkflowImportExportService
        from app.db.session import SessionLocal
        
        session = SessionLocal()
        service = WorkflowImportExportService(session)
        
        errors = service.validate_preset_data(data)
        if errors:
            print("❌ Validation errors:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("✅ Preset validation passed")
            
    except FileNotFoundError:
        print(f"❌ File not found: {preset_file}")
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
```

#### **4. Performance Issues**

**Problem**: Slow workflow queries or timeouts

**Solutions**:
```python
# Enable SQL query logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Identify slow queries
def profile_workflow_queries():
    """Profile workflow query performance."""
    import time
    from app.services.workflow_service import WorkflowService
    from app.db.session import SessionLocal
    
    session = SessionLocal()
    service = WorkflowService(session)
    
    # Time workflow loading
    start = time.time()
    workflows = service.search_workflows({'limit': 10}, user_id=1)
    duration = time.time() - start
    print(f"Search workflows: {duration:.2f}s")
    
    if workflows['items']:
        workflow_id = workflows['items'][0].id
        
        # Time detailed loading
        start = time.time()
        workflow = service.get_workflow(workflow_id, user_id=1)
        duration = time.time() - start
        print(f"Get workflow details: {duration:.2f}s")

# Check database indexes
def check_workflow_indexes():
    """Verify database indexes are present."""
    from sqlalchemy import text
    from app.db.session import SessionLocal
    
    session = SessionLocal()
    
    expected_indexes = [
        'idx_workflow_status_template',
        'idx_workflow_created_by',
        'idx_workflow_step_workflow_order',
        'idx_workflow_execution_workflow'
    ]
    
    for index_name in expected_indexes:
        result = session.execute(text(f"""
            SELECT 1 FROM pg_indexes 
            WHERE indexname = '{index_name}'
        """)).scalar()
        
        if result:
            print(f"✅ Index {index_name} exists")
        else:
            print(f"❌ Missing index {index_name}")
```

#### **5. Event System Issues**

**Problem**: Events not firing or handlers not working

**Solutions**:
```python
def debug_event_system():
    """Debug workflow event system."""
    from app.core.events import global_event_bus
    
    # Test event publishing
    test_fired = False
    
    @global_event_bus.subscribe
    def test_handler(event):
        nonlocal test_fired
        test_fired = True
        print(f"✅ Test event received: {event}")
    
    # Publish test event
    from app.core.events import EntityCreatedEvent
    test_event = EntityCreatedEvent(
        entity_id=999,
        entity_type="Test",
        user_id=1
    )
    
    global_event_bus.publish(test_event)
    
    if test_fired:
        print("✅ Event system working")
    else:
        print("❌ Event system not working")
    
    # Check workflow event handlers
    from app.services.workflow_event_handlers import setup_workflow_event_handlers
    from app.db.session import SessionLocal
    
    try:
        session = SessionLocal()
        setup_workflow_event_handlers(session)
        print("✅ Workflow event handlers setup successful")
    except Exception as e:
        print(f"❌ Event handlers setup failed: {e}")
```

### **Diagnostic Tools**

#### **System Health Check**

```python
def comprehensive_health_check():
    """Comprehensive workflow system health check."""
    results = {}
    
    # Database connectivity
    try:
        from app.db.session import SessionLocal
        session = SessionLocal()
        session.execute("SELECT 1").scalar()
        session.close()
        results['database'] = {'status': 'healthy', 'message': 'Connected successfully'}
    except Exception as e:
        results['database'] = {'status': 'error', 'message': str(e)}
    
    # Workflow tables
    try:
        from sqlalchemy import inspect
        from app.db.session import engine
        inspector = inspect(engine)
        workflow_tables = [t for t in inspector.get_table_names() if 'workflow' in t]
        results['tables'] = {
            'status': 'healthy' if len(workflow_tables) >= 10 else 'warning',
            'message': f'Found {len(workflow_tables)} workflow tables'
        }
    except Exception as e:
        results['tables'] = {'status': 'error', 'message': str(e)}
    
    # Enum data
    try:
        from app.services.enum_service import EnumService
        session = SessionLocal()
        enum_service = EnumService(session)
        step_types = enum_service.get_enum_values('workflow_step_type', 'en')
        results['enums'] = {
            'status': 'healthy' if len(step_types) >= 7 else 'warning',
            'message': f'Found {len(step_types)} step types'
        }
        session.close()
    except Exception as e:
        results['enums'] = {'status': 'error', 'message': str(e)}
    
    # Services
    try:
        from app.services.workflow_service import WorkflowService
        session = SessionLocal()
        service = WorkflowService(session)
        templates = service.get_workflow_templates()
        results['services'] = {
            'status': 'healthy',
            'message': f'Service working, {len(templates)} templates available'
        }
        session.close()
    except Exception as e:
        results['services'] = {'status': 'error', 'message': str(e)}
    
    # Print results
    print("🏥 Workflow System Health Check")
    print("=" * 40)
    
    for component, result in results.items():
        status_icon = {
            'healthy': '✅',
            'warning': '⚠️',
            'error': '❌'
        }.get(result['status'], '❓')
        
        print(f"{status_icon} {component.title()}: {result['message']}")
    
    overall_status = 'healthy'
    if any(r['status'] == 'error' for r in results.values()):
        overall_status = 'error'
    elif any(r['status'] == 'warning' for r in results.values()):
        overall_status = 'warning'
    
    print(f"\n🎯 Overall Status: {overall_status.upper()}")
    return results
```

#### **Data Consistency Checks**

```python
def check_data_consistency():
    """Check workflow data consistency."""
    from app.db.session import SessionLocal
    from sqlalchemy import text
    
    session = SessionLocal()
    issues = []
    
    # Check orphaned steps
    orphaned_steps = session.execute(text("""
        SELECT s.id, s.name, s.workflow_id 
        FROM workflow_steps s
        LEFT JOIN workflows w ON s.workflow_id = w.id
        WHERE w.id IS NULL
    """)).fetchall()
    
    if orphaned_steps:
        issues.append(f"Found {len(orphaned_steps)} orphaned steps")
    
    # Check broken connections
    broken_connections = session.execute(text("""
        SELECT c.id, c.source_step_id, c.target_step_id
        FROM workflow_step_connections c
        LEFT JOIN workflow_steps s1 ON c.source_step_id = s1.id
        LEFT JOIN workflow_steps s2 ON c.target_step_id = s2.id
        WHERE s1.id IS NULL OR s2.id IS NULL
    """)).fetchall()
    
    if broken_connections:
        issues.append(f"Found {len(broken_connections)} broken connections")
    
    # Check executions without workflows
    orphaned_executions = session.execute(text("""
        SELECT e.id, e.workflow_id
        FROM workflow_executions e
        LEFT JOIN workflows w ON e.workflow_id = w.id
        WHERE w.id IS NULL
    """)).fetchall()
    
    if orphaned_executions:
        issues.append(f"Found {len(orphaned_executions)} orphaned executions")
    
    if issues:
        print("❌ Data consistency issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ No data consistency issues found")
    
    session.close()
    return len(issues) == 0
```

---

## 🔧 **Extension Guide**

### **Adding Custom Step Types**

#### **1. Define New Step Type**

```python
# First, add to enum system
def add_custom_step_type():
    """Add a custom step type to the system."""
    from app.services.enum_service import EnumService
    from app.db.session import SessionLocal
    
    session = SessionLocal()
    enum_service = EnumService(session)
    
    custom_step_type = {
        'code': 'inspection',
        'display_text': 'Quality Inspection',
        'description': 'Step for quality control and inspection',
        'display_order': 10,
        'is_system': False  # Custom step type
    }
    
    try:
        enum_service.create_enum_value('workflow_step_type', custom_step_type)
        print("✅ Added custom step type: inspection")
    except Exception as e:
        print(f"❌ Error adding step type: {e}")
    
    session.close()
```

#### **2. Create Step Type Handler**

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class StepTypeHandler(ABC):
    """Base class for step type handlers."""
    
    @abstractmethod
    def validate_step_data(self, step_data: Dict[str, Any]) -> List[str]:
        """Validate step-specific data."""
        pass
    
    @abstractmethod
    def get_step_guidance(self, step: WorkflowStep, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate step-specific guidance."""
        pass
    
    @abstractmethod
    def can_complete_step(self, step: WorkflowStep, execution_context: Dict[str, Any]) -> bool:
        """Check if step can be completed."""
        pass

class InspectionStepHandler(StepTypeHandler):
    """Handler for quality inspection steps."""
    
    def validate_step_data(self, step_data: Dict[str, Any]) -> List[str]:
        """Validate inspection step data."""
        errors = []
        
        # Inspection steps should have quality criteria
        if not step_data.get('instructions'):
            errors.append("Inspection steps must have detailed instructions")
        
        # Should have decision options for pass/fail
        if not step_data.get('is_decision_point'):
            errors.append("Inspection steps should be decision points")
        
        return errors
    
    def get_step_guidance(self, step: WorkflowStep, execution_context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate inspection-specific guidance."""
        return {
            'primary_guidance': f'Carefully inspect the work according to: {step.instructions}',
            'inspection_checklist': self._generate_checklist(step),
            'quality_standards': self._get_quality_standards(step),
            'tips': [
                'Take your time with quality inspection',
                'Document any issues found',
                'Compare against quality standards'
            ]
        }
    
    def can_complete_step(self, step: WorkflowStep, execution_context: Dict[str, Any]) -> bool:
        """Inspection steps require decision to be made."""
        return execution_context.get('decision_made', False)
    
    def _generate_checklist(self, step: WorkflowStep) -> List[str]:
        """Generate inspection checklist from step instructions."""
        # Parse instructions to create checklist
        instructions = step.instructions or ""
        # Simple implementation - split by sentences
        return [item.strip() for item in instructions.split('.') if item.strip()]
    
    def _get_quality_standards(self, step: WorkflowStep) -> Dict[str, Any]:
        """Extract quality standards from step data."""
        # Look for quality criteria in step data
        if hasattr(step, 'condition_logic') and step.condition_logic:
            import json
            try:
                logic = json.loads(step.condition_logic)
                return logic.get('quality_standards', {})
            except:
                pass
        return {}

# Register the handler
class StepTypeRegistry:
    """Registry for step type handlers."""
    
    _handlers = {
        'instruction': DefaultStepHandler(),
        'material': MaterialStepHandler(),
        'tool': ToolStepHandler(),
        'inspection': InspectionStepHandler(),  # Register custom handler
    }
    
    @classmethod
    def get_handler(cls, step_type: str) -> StepTypeHandler:
        """Get handler for step type."""
        return cls._handlers.get(step_type, cls._handlers['instruction'])
    
    @classmethod
    def register_handler(cls, step_type: str, handler: StepTypeHandler):
        """Register a custom step type handler."""
        cls._handlers[step_type] = handler
```

#### **3. Integrate with Navigation Service**

```python
class EnhancedWorkflowNavigationService(WorkflowNavigationService):
    """Enhanced navigation service with custom step type support."""
    
    def get_step_guidance(self, execution_id: int, step_id: int, user_id: int) -> Dict[str, Any]:
        """Get step guidance with custom step type support."""
        # Get base guidance
        guidance = super().get_step_guidance(execution_id, step_id, user_id)
        
        # Get step and execution context
        step = self.step_repo.get_step_with_details(step_id)
        execution = self.execution_service.get_execution(execution_id, user_id)
        
        # Get custom handler guidance
        handler = StepTypeRegistry.get_handler(step.step_type)
        execution_context = self._build_execution_context(execution, step)
        
        custom_guidance = handler.get_step_guidance(step, execution_context)
        
        # Merge custom guidance with base guidance
        guidance.update(custom_guidance)
        
        return guidance
    
    def _build_execution_context(self, execution: WorkflowExecution, step: WorkflowStep) -> Dict[str, Any]:
        """Build execution context for step handlers."""
        return {
            'execution_id': execution.id,
            'workflow_id': execution.workflow_id,
            'execution_data': execution.execution_data or {},
            'step_executions': {se.step_id: se for se in execution.step_executions},
            'navigation_history': execution.navigation_history
        }
```

### **Custom Resource Types**

#### **1. Add Documentation Resource Type**

```python
# Update the resource model to support documentation
class WorkflowStepResource(Base):
    # ... existing fields ...
    
    # Add documentation support
    documentation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("documentation.id"), nullable=True
    )
    
    # Add relationship
    documentation: Mapped[Optional["Documentation"]] = relationship("Documentation")

# Create documentation model if it doesn't exist
class Documentation(Base):
    """Documentation resource model."""
    __tablename__ = "documentation"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, video, image, text
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

#### **2. Extend Resource Service**

```python
class EnhancedWorkflowResourceService(WorkflowResourceService):
    """Enhanced resource service with documentation support."""
    
    def _prepare_documentation_resource(self, resource: WorkflowStepResource, 
                                        execution_id: int) -> Optional[Dict[str, Any]]:
        """Prepare documentation resource information."""
        if not resource.documentation_id:
            return None
        
        # Get documentation details
        doc = self.get_documentation(resource.documentation_id)
        if not doc:
            return None
        
        return {
            'documentation_id': resource.documentation_id,
            'title': doc.title,
            'doc_type': doc.doc_type,
            'file_path': doc.file_path,
            'notes': resource.notes,
            'is_optional': resource.is_optional,
            'access_url': self._generate_doc_access_url(doc)
        }
    
    def _generate_doc_access_url(self, doc: Documentation) -> str:
        """Generate secure access URL for documentation."""
        if doc.file_path:
            # Generate signed URL for file access
            return f"/api/v1/documentation/{doc.id}/view"
        elif doc.content:
            # Direct content access
            return f"/api/v1/documentation/{doc.id}/content"
        return ""
    
    def get_documentation(self, doc_id: int) -> Optional[Documentation]:
        """Get documentation by ID."""
        return self.db_session.query(Documentation).filter(
            Documentation.id == doc_id
        ).first()
```

### **Custom Navigation Commands**

#### **1. Add Voice Commands**

```python
class VoiceCommandProcessor:
    """Processor for voice navigation commands."""
    
    def __init__(self, navigation_service: WorkflowNavigationService):
        self.navigation_service = navigation_service
        self.command_patterns = {
            r"start\s+(.+)": self._handle_start_command,
            r"complete\s+(.+)": self._handle_complete_command,
            r"show\s+(.+)": self._handle_show_command,
            r"go\s+to\s+(.+)": self._handle_goto_command,
            r"what\s+do\s+i\s+need": self._handle_needs_command,
            r"help": self._handle_help_command
        }
    
    def process_voice_command(self, command: str, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Process voice command and return response."""
        command = command.lower().strip()
        
        for pattern, handler in self.command_patterns.items():
            import re
            match = re.match(pattern, command)
            if match:
                return handler(match, execution_id, user_id)
        
        return {
            'success': False,
            'message': f"I didn't understand '{command}'. Try saying 'help' for available commands.",
            'speech_response': "I didn't understand that command. Try saying help for available commands."
        }
    
    def _handle_start_command(self, match, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Handle 'start <step>' commands."""
        step_name = match.group(1)
        
        # Find step by name
        context = self.navigation_service.get_navigation_context(execution_id, user_id)
        
        # Simple fuzzy matching
        for option in context['navigation_options']:
            if step_name in option['label'].lower():
                if option['action'] == 'navigate_to_step':
                    # Navigate to the step
                    execution_service = self.navigation_service.execution_service
                    execution_service.navigate_to_step(execution_id, option['step_id'], user_id)
                    
                    return {
                        'success': True,
                        'message': f"Started {option['label']}",
                        'speech_response': f"Starting {option['label']}. Let me know when you're ready to continue."
                    }
        
        return {
            'success': False,
            'message': f"Couldn't find step '{step_name}'",
            'speech_response': f"I couldn't find a step called {step_name}. What would you like to do?"
        }
    
    def _handle_needs_command(self, match, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Handle 'what do I need' commands."""
        context = self.navigation_service.get_navigation_context(execution_id, user_id)
        
        if context['current_step']:
            step_id = context['current_step']['id']
            guidance = self.navigation_service.get_step_guidance(execution_id, step_id, user_id)
            
            resources = guidance.get('resources', [])
            if resources:
                materials = [r for r in resources if r['type'] == 'material']
                tools = [r for r in resources if r['type'] == 'tool']
                
                response_parts = []
                if materials:
                    response_parts.append(f"Materials: {', '.join(f'{m['quantity']} {m['unit']} {m['type']}' for m in materials)}")
                if tools:
                    response_parts.append(f"Tools: {', '.join(t['type'] for t in tools)}")
                
                response = "For this step you need: " + ". ".join(response_parts)
                
                return {
                    'success': True,
                    'message': response,
                    'speech_response': response,
                    'resources': resources
                }
        
        return {
            'success': True,
            'message': "No specific resources needed for the current step",
            'speech_response': "You don't need any specific resources for the current step"
        }
```

#### **2. Add Gesture Recognition**

```python
class GestureCommandProcessor:
    """Processor for gesture-based navigation."""
    
    GESTURE_COMMANDS = {
        'swipe_right': 'next_step',
        'swipe_left': 'previous_step', 
        'tap_hold': 'complete_step',
        'double_tap': 'show_guidance',
        'pinch_in': 'show_overview',
        'pinch_out': 'show_details'
    }
    
    def __init__(self, navigation_service: WorkflowNavigationService):
        self.navigation_service = navigation_service
    
    def process_gesture(self, gesture: str, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Process gesture command."""
        command = self.GESTURE_COMMANDS.get(gesture)
        
        if not command:
            return {'success': False, 'message': f'Unknown gesture: {gesture}'}
        
        return self._execute_gesture_command(command, execution_id, user_id)
    
    def _execute_gesture_command(self, command: str, execution_id: int, user_id: int) -> Dict[str, Any]:
        """Execute gesture command."""
        context = self.navigation_service.get_navigation_context(execution_id, user_id)
        
        if command == 'next_step':
            # Find next available step
            for option in context['navigation_options']:
                if option['action'] == 'navigate_to_step':
                    execution_service = self.navigation_service.execution_service
                    execution_service.navigate_to_step(execution_id, option['step_id'], user_id)
                    return {'success': True, 'message': f'Moved to {option["label"]}'}
        
        elif command == 'complete_step':
            # Complete current step
            if context['current_step']:
                execution_service = self.navigation_service.execution_service
                execution_service.complete_step(execution_id, context['current_step']['id'], user_id)
                return {'success': True, 'message': f'Completed {context["current_step"]["name"]}'}
        
        elif command == 'show_guidance':
            # Return current step guidance
            if context['current_step']:
                guidance = self.navigation_service.get_step_guidance(
                    execution_id, context['current_step']['id'], user_id
                )
                return {'success': True, 'guidance': guidance}
        
        return {'success': False, 'message': f'Could not execute command: {command}'}
```

### **Workflow Analytics Extensions**

#### **1. Advanced Metrics Collection**

```python
class AdvancedWorkflowAnalytics:
    """Advanced analytics for workflow system."""
    
    def __init__(self, session: Session):
        self.db_session = session
        self.setup_event_handlers()
    
    def setup_event_handlers(self):
        """Set up analytics event handlers."""
        from app.core.events import global_event_bus
        
        @global_event_bus.subscribe
        def track_step_difficulty(event):
            """Track which steps users find difficult."""
            if hasattr(event, 'step_id') and hasattr(event, 'actual_duration'):
                self._record_step_performance(event)
        
        @global_event_bus.subscribe  
        def track_decision_patterns(event):
            """Track decision patterns in workflows."""
            if hasattr(event, 'decision_option_id'):
                self._record_decision_choice(event)
    
    def _record_step_performance(self, event):
        """Record step performance metrics."""
        # Get step details
        step = self.db_session.query(WorkflowStep).filter(
            WorkflowStep.id == event.step_id
        ).first()
        
        if step:
            # Calculate difficulty score based on time variance
            estimated = step.estimated_duration or 0
            actual = event.actual_duration
            
            if estimated > 0:
                variance = abs(actual - estimated) / estimated
                difficulty_score = min(variance * 100, 100)  # Cap at 100
                
                # Store in analytics table
                self._store_metric('step_difficulty', {
                    'step_id': event.step_id,
                    'workflow_id': step.workflow_id,
                    'difficulty_score': difficulty_score,
                    'estimated_duration': estimated,
                    'actual_duration': actual,
                    'user_id': getattr(event, 'user_id', None)
                })
    
    def _record_decision_choice(self, event):
        """Record decision choice patterns."""
        decision_option = self.db_session.query(WorkflowDecisionOption).filter(
            WorkflowDecisionOption.id == event.decision_option_id
        ).first()
        
        if decision_option:
            self._store_metric('decision_choice', {
                'step_id': decision_option.step_id,
                'option_id': event.decision_option_id,
                'option_text': decision_option.option_text,
                'user_id': getattr(event, 'user_id', None),
                'execution_id': getattr(event, 'execution_id', None)
            })
    
    def _store_metric(self, metric_type: str, data: Dict[str, Any]):
        """Store analytics metric."""
        # Implementation would store in analytics table
        # For now, just log
        logger.info(f"Analytics - {metric_type}: {data}")
    
    def generate_workflow_insights(self, workflow_id: int) -> Dict[str, Any]:
        """Generate insights for a workflow."""
        insights = {}
        
        # Find bottleneck steps
        bottlenecks = self._identify_bottleneck_steps(workflow_id)
        insights['bottlenecks'] = bottlenecks
        
        # Decision patterns
        decision_patterns = self._analyze_decision_patterns(workflow_id)
        insights['decision_patterns'] = decision_patterns
        
        # User success patterns
        success_patterns = self._analyze_success_patterns(workflow_id)
        insights['success_patterns'] = success_patterns
        
        return insights
    
    def _identify_bottleneck_steps(self, workflow_id: int) -> List[Dict[str, Any]]:
        """Identify steps that consistently take longer than expected."""
        # Query step performance data
        from sqlalchemy import text
        
        result = self.db_session.execute(text("""
            SELECT s.id, s.name, 
                   AVG(se.actual_duration) as avg_actual,
                   s.estimated_duration,
                   COUNT(*) as execution_count
            FROM workflow_steps s
            JOIN workflow_step_executions se ON s.id = se.step_id
            WHERE s.workflow_id = :workflow_id 
              AND se.actual_duration IS NOT NULL
              AND s.estimated_duration IS NOT NULL
            GROUP BY s.id, s.name, s.estimated_duration
            HAVING AVG(se.actual_duration) > s.estimated_duration * 1.5
            ORDER BY (AVG(se.actual_duration) / s.estimated_duration) DESC
        """), {'workflow_id': workflow_id}).fetchall()
        
        return [
            {
                'step_id': row.id,
                'step_name': row.name,
                'avg_actual_duration': float(row.avg_actual),
                'estimated_duration': float(row.estimated_duration),
                'overrun_ratio': float(row.avg_actual) / float(row.estimated_duration),
                'execution_count': row.execution_count
            }
            for row in result
        ]
```

### **Integration with External Systems**

#### **1. ERP System Integration**

```python
class ERPIntegration:
    """Integration with external ERP systems."""
    
    def __init__(self, erp_config: Dict[str, Any]):
        self.config = erp_config
        self.api_base = erp_config['api_base']
        self.api_key = erp_config['api_key']
    
    def sync_materials_with_erp(self, workflow_id: int):
        """Sync workflow material requirements with ERP."""
        from app.services.workflow_resource_service import WorkflowResourceService
        
        resource_service = WorkflowResourceService(self.session)
        analysis = resource_service.analyze_workflow_resources(workflow_id)
        
        # Convert to ERP format
        erp_materials = []
        for material in analysis['material_requirements']:
            erp_material = {
                'item_code': self._get_erp_item_code(material['material_id']),
                'quantity_required': material['total_quantity'],
                'unit': material['unit'],
                'workflow_reference': f"WF-{workflow_id}"
            }
            erp_materials.append(erp_material)
        
        # Send to ERP
        self._send_to_erp('/materials/reserve', {
            'materials': erp_materials,
            'workflow_id': workflow_id
        })
    
    def _get_erp_item_code(self, material_id: int) -> str:
        """Map internal material ID to ERP item code."""
        # Implementation would maintain mapping table
        return f"MAT-{material_id:06d}"
    
    def _send_to_erp(self, endpoint: str, data: Dict[str, Any]):
        """Send data to ERP system."""
        import requests
        
        url = f"{self.api_base}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        return response.json()
```

#### **2. IoT Device Integration**

```python
class IoTWorkflowIntegration:
    """Integration with IoT devices for automated workflow tracking."""
    
    def __init__(self, mqtt_config: Dict[str, Any]):
        self.mqtt_config = mqtt_config
        self.setup_mqtt_client()
    
    def setup_mqtt_client(self):
        """Set up MQTT client for IoT communication."""
        import paho.mqtt.client as mqtt
        
        self.client = mqtt.Client()
        self.client.on_connect = self._on_mqtt_connect
        self.client.on_message = self._on_mqtt_message
        
        self.client.connect(
            self.mqtt_config['broker'],
            self.mqtt_config['port'],
            60
        )
        self.client.loop_start()
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        print(f"Connected to MQTT broker with result code {rc}")
        
        # Subscribe to workflow-related topics
        client.subscribe("workflow/+/step/+/sensor")
        client.subscribe("workflow/+/tool/usage")
        client.subscribe("workflow/+/environmental")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        import json
        
        try:
            topic_parts = msg.topic.split('/')
            data = json.loads(msg.payload.decode())
            
            if 'sensor' in topic_parts:
                self._handle_sensor_data(topic_parts, data)
            elif 'tool' in topic_parts:
                self._handle_tool_usage(topic_parts, data)
            elif 'environmental' in topic_parts:
                self._handle_environmental_data(topic_parts, data)
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _handle_sensor_data(self, topic_parts: List[str], data: Dict[str, Any]):
        """Handle sensor data from workflow steps."""
        workflow_id = int(topic_parts[1])
        step_id = int(topic_parts[3])
        
        # Auto-complete steps based on sensor input
        if data.get('action') == 'step_completed':
            from app.services.workflow_execution_service import WorkflowExecutionService
            
            # Find active execution for this workflow
            execution = self._find_active_execution(workflow_id)
            if execution and execution.current_step_id == step_id:
                execution_service = WorkflowExecutionService(self.session)
                execution_service.complete_step(
                    execution.id,
                    step_id,
                    user_id=execution.started_by,
                    completion_data={
                        'notes': 'Auto-completed by IoT sensor',
                        'sensor_data': data
                    }
                )
    
    def _find_active_execution(self, workflow_id: int) -> Optional[WorkflowExecution]:
        """Find active execution for workflow."""
        return self.session.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.status == 'active'
        ).first()
```

---

## 🎉 **Conclusion**

The HideSync Workflow Management System provides a comprehensive, extensible platform for managing complex workflows within the HideSync ecosystem. This documentation has covered:

### **Key Achievements**

- ✅ **Complete System Architecture**: 12 database tables, 5 service layers, 15+ API endpoints
- ✅ **Interactive Navigation**: Text-adventure style guidance with AI-powered suggestions  
- ✅ **Resource Integration**: Seamless connection with materials and tools inventory
- ✅ **Import/Export System**: JSON-based preset sharing for community collaboration
- ✅ **Event-Driven Design**: Real-time notifications and analytics integration
- ✅ **Extensible Framework**: Support for custom step types and integrations

### **System Capabilities**

The workflow system enables users to:

1. **Create and Share Templates**: Build reusable workflows for common projects
2. **Execute with Guidance**: Step-by-step navigation with contextual help
3. **Track Progress**: Real-time monitoring with detailed analytics
4. **Manage Resources**: Automated planning and reservation integration
5. **Collaborate**: Import/export workflows as JSON presets
6. **Extend Functionality**: Add custom step types and integrations

### **Next Steps**

To further enhance the workflow system, consider:

1. **Machine Learning Integration**: AI-powered workflow optimization and recommendations
2. **Mobile App Support**: Native mobile apps with offline execution capabilities
3. **Advanced Analytics**: Predictive modeling for workflow success and resource needs
4. **Community Platform**: Central repository for sharing and rating workflow templates
5. **Voice Control**: Enhanced voice navigation with natural language processing

### **Support and Resources**

- **Documentation**: This comprehensive guide covers all aspects of the system
- **Code Examples**: Practical examples for common use cases and extensions
- **Best Practices**: Proven patterns for optimal performance and maintainability
- **Troubleshooting**: Common issues and diagnostic tools
- **Extension Guide**: Framework for adding custom functionality

The HideSync Workflow Management System is designed to grow with your needs, providing a solid foundation for process automation and knowledge sharing in maker communities. Whether you're a beginner following your first leather working project or an expert creating complex multi-step processes, the system provides the tools and flexibility needed for success.

---

*Happy making! 🛠️*