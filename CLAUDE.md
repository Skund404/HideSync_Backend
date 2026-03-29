# CLAUDE.md — HideSync → Makestack Migration

Single source of truth for every Claude Code session in this repository.
Read it in full before touching any file.

---

## What This Codebase Is Becoming

```
makestack-core  (Go, runs at localhost:8420)
  └─ Physical domain data: tools, materials, techniques, workflows, projects, events
  └─ Stored as JSON manifests in Git repositories
  └─ REST API with FTS, versioning, federation

HideSync Backend  (Python / FastAPI — this repo)
  └─ User identity, auth, roles
  └─ Personal state: inventory (user_id + core_path + quantity)
  └─ Commerce: sales, purchases, suppliers, customers, shipments
  └─ Proxies physical domain queries to makestack-core
```

The Python backend never owns or stores physical domain data.
It holds references to makestack-core manifests via `core_path` strings.

---

## The Six Primitives

| Primitive  | Replaces in HideSync                              |
|------------|---------------------------------------------------|
| tool       | Tool, ToolMaintenance, ToolCheckout               |
| material   | Material (leather, hardware, supplies, wood)      |
| technique  | Pattern                                           |
| workflow   | Workflow, WorkflowStep, ProjectTemplate           |
| project    | Project, RecurringProject                         |
| event      | TimelineTask                                      |

Manifest shape:
```json
{
  "id": "uuid",
  "type": "tool",
  "name": "Swivel Knife",
  "slug": "swivel-knife",
  "description": "...",
  "tags": ["leather", "carving"],
  "created": "2026-01-01T00:00:00Z",
  "modified": "2026-01-01T00:00:00Z",
  "relationships": [{ "type": "used_by", "target": "techniques/carving/manifest.json" }]
}
```

---

## Hard Constraints

### 1. SQLAlchemy never holds physical domain data
Python DB holds: users, roles, auth tokens, inventory mappings, commerce records.
If a SQLAlchemy model describes a tool, material, technique, workflow, project,
or event — it must be deleted, not migrated.

### 2. httpx calls belong exclusively in the repository layer
`MakestackClient` (httpx) → `app/core/makestack_client.py`
`PrimitiveRepository` → `app/repositories/primitive_repository.py`
Routers and services never import httpx or call makestack-core directly.

### 3. SQLCipher is gone entirely
No `pragma key`, no `pysqlcipher3`, no encrypted DB fixtures.
Standard `sqlite:///` only (dev). Files that exist solely for encryption: deleted.

### 4. Exactly six Pydantic schemas for the physical domain
`app/schemas/primitives.py` — `BasePrimitive` + six subclasses.
Legacy domain schemas (material.py, tool.py, pattern.py, workflow.py, etc.) deleted.

### 5. No shim layers
No `*Adapter`, `*Compat`, `*Bridge`, `*Wrapper` classes.
The manifest shape IS the data shape.

### 6. No partial deletes
Delete files completely. Git history is the backup.

### 7. One domain per session
Do not touch files outside the declared scope even if they appear broken.

### 8. Inventory holds references, not data
```python
class Inventory(Base):
    id: int
    user_id: int          # FK → User
    core_path: str        # e.g. "tools/swivel-knife/manifest.json"
    commit_hash: str      # pinned version at time of entry
    primitive_type: str   # denormalized: "tool" | "material"
    quantity: float
    unit: str
```
No name, description, or supplier fields — those come from makestack-core.

---

## Architecture

### Request Flow (Physical Domain)
```
Router → Service → PrimitiveRepository → MakestackClient → makestack-core
```

### Request Flow (User State)
```
Router → Service → StateRepository (SQLAlchemy) → SQLite
```

### Inventory Merge Flow
```python
InventoryService.get_user_inventory(user_id):
    1. state_repo.get_inventory_for_user(user_id)   # List[Inventory]
    2. primitive_repo.get_many(paths)                # List[manifest dict]
    3. merge: zip quantities onto manifests
    4. return to router
```

### File Layout After Migration
```
app/
├── api/endpoints/
├── core/
│   ├── config.py           # + MAKESTACK_CORE_URL, MAKESTACK_API_KEY
│   ├── makestack_client.py # NEW — async httpx
│   ├── exceptions.py       # + MakestackUnavailableException
│   └── security.py
├── db/
│   └── models/
│       ├── base.py, user.py, role.py, password_reset.py, settings.py  # unchanged
│       ├── inventory.py        # REWRITTEN — core_path based
│       ├── customer.py         # kept, cleaned
│       ├── supplier.py         # kept, cleaned
│       ├── sales.py            # kept, cleaned
│       ├── purchase.py         # kept, cleaned
│       ├── storage.py          # kept, cleaned
│       └── [other commerce]    # kept, cleaned
├── repositories/
│   ├── primitive_repository.py # NEW
│   ├── state_repository.py     # NEW
│   └── [user/commerce repos]   # kept
├── schemas/
│   ├── primitives.py           # NEW
│   └── [user/commerce schemas] # kept
└── services/
    ├── makestack_service.py    # NEW
    ├── inventory_service.py    # REWRITTEN
    └── [user/commerce services]# kept
```

---

## makestack-core API Quick Reference

Full contract: `MAKESTACK_CORE_API.md`

```
Base URL: http://localhost:8420   (env: MAKESTACK_CORE_URL)
Auth:     Authorization: Bearer   (env: MAKESTACK_API_KEY)
```

| Method | Endpoint | Notes |
|--------|----------|-------|
| GET | `/api/primitives` | `?type=tool&root=primary` |
| GET | `/api/primitives/{path}/manifest.json` | `?at={hash}` pins version |
| GET | `/api/primitives/{path}/manifest.json/hash` | last-modified hash |
| POST | `/api/primitives` | returns 201 |
| PUT | `/api/primitives/{path}/manifest.json` | |
| DELETE | `/api/primitives/{path}/manifest.json` | returns 204 |
| GET | `/api/search?q=` | FTS5 |

Error mapping: `404`→EntityNotFoundException · `400`→ValidationException ·
`409`→BusinessRuleException · `503`→MakestackUnavailableException

---

## Session Index

| Session | Domain | Strategy |
|---------|--------|----------|
| 0 | SQLCipher + physical domain removal | Delete |
| 1 | Foundation | MakestackClient + PrimitiveRepository + schemas |
| 2 | Tools | First primitive vertical slice |
| 3 | Materials | Second atom |
| 4 | Techniques | Patterns → technique |
| 5 | Workflows | First molecule |
| 6 | Projects | Second molecule |
| 7 | Inventory | Schema rewrite + merge flow |
| 8 | Storage | Remove DMMS property refs |
| 9 | Commerce | Sales, purchases, products — replace material FKs with core_path |
| 10 | Suppliers | Cleanup |
| 11 | Customers | Cleanup |
| 12 | Auth / Users | Verify only |
| 13 | Infrastructure | Search fanout, factories, tags, analytics |
| 14 | Final audit | Dead code removal, import verification |

---

## Session 0 — SQLCipher + Physical Domain Removal

### Step A — Delete SQLCipher

Files to delete:
```
app/sqlcipher_dialect.py
app/core/key_manager.py
app/db/session.py.bak
SQLCipher_connection_test.py
sqlcipher_diagnostic.py
dev_db.key
scripts/generate_key.py
```

Remove from `requirements.txt`: `pysqlcipher3`

Edit `app/core/config.py`:
- Remove: `USE_SQLCIPHER`, `DATABASE_ENCRYPTION_KEY`, `KEY_MANAGEMENT_METHOD`,
  `KEY_FILE_PATH`, `KEY_ENVIRONMENT_VARIABLE`, `ENFORCE_KEY_FILE_PERMISSIONS`,
  `AWS_SECRET_*`, `AZURE_*`, `GCP_*` settings and their validators.
- Simplify `DATABASE_URL` to always return `sqlite:///./hidesync.db` in dev.

Rewrite `app/db/session.py`:
- Standard `create_engine("sqlite:///./hidesync.db")`
- Remove all encryption, pragma key, KeyManager, and SQLCipherDialect imports.
- Keep: `SessionLocal`, `get_db()`, `init_db()` that calls `Base.metadata.create_all`.

### Step B — Delete physical domain MODELS

Delete from `app/db/models/`:
```
material.py          tool.py              pattern.py
workflow.py          project.py           component.py
timeline_task.py     recurring_project.py
dynamic_enum.py      dynamic_material.py  entity_translation.py
preset.py            associations.py      association_media.py
```

Keep in `app/db/models/`:
```
base.py  user.py  role.py  password_reset.py  settings.py
customer.py  supplier.py  supplier_history.py  supplier_rating.py
sales.py  purchase.py  shipment.py  refund.py  product.py
picking_list.py  storage.py  inventory.py  tag.py
media_asset.py  entity_media.py  documentation.py
annotation.py  platform_integration.py  file_metadata.py
communication.py  customer_communication_service.py  enums.py
```

Note: `customer_communication_service.py` is a model file with a wrong name —
rename it to `customer_communication.py` in Session 11.

### Step C — Prune enums.py

**Delete** these enum classes from `enums.py` (catalogue-only, move to core manifests):
```
AnimalSource         ComponentType        EdgeFinishType
HardwareFinish       HardwareMaterialEnum HardwareType
LeatherFinish        LeatherType          MaterialQualityGrade
MaterialStatus       MaterialType         PatternFileType
SuppliesMaterialType TannageType          TimelineTaskStatus
ToolCategory         ToolCondition        ToolStatus
ToolType             MaintenanceType      WoodFinish
WoodGrain            WoodType             WorkflowConnectionType
WorkflowStatus       WorkflowStepType     WorkflowThemeStyle
ProjectType
```

**Keep** these enum classes in `enums.py` (userDB operational enums):
```
CommunicationChannel  CommunicationType    CustomerSource
CustomerStatus        CustomerTier         DocumentationCategory
FulfillmentStatus     FileType             InventoryAdjustmentType
InventoryStatus       InventoryTransactionType  MeasurementUnit
PaymentStatus         PickingListItemStatus PickingListStatus
ProjectStatus         PurchaseOrderStatus  PurchaseStatus
QualityGrade          SaleStatus           SkillLevel
StorageLocationStatus StorageLocationType  StorageSection
SupplierStatus        TransactionType      UserRole
ToolListStatus
```

### Step D — Delete physical domain REPOSITORIES

Delete from `app/repositories/`:
```
material_repository.py           tool_repository.py
pattern_repository.py            workflow_repository.py
workflow_step_repository.py      project_repository.py
project_template_repository.py   recurring_project_repository.py
component_repository.py          timeline_task_repository.py
workflow_execution_repository.py dynamic_material_repository.py
material_type_repository.py      property_definition_repository.py
entity_translation_repository.py preset_repository.py
media_asset_tag_repository.py
```

Keep: `base_repository.py`, `user_repository.py`, `role_repository.py`,
`settings_repository.py`, `repository_factory.py` (gut contents),
`inventory_repository.py`, `inventory_transaction_repository.py`,
`customer_repository.py`, `supplier_repository.py`, `supplier_history_repository.py`,
`supplier_rating_repository.py`, `sale_repository.py`, `purchase_repository.py`,
`shipment_repository.py`, `refund_repository.py`, `product_repository.py`,
`picking_list_repository.py`, `storage_repository.py`, `tag_repository.py`,
`annotation_repository.py`, `documentation_repository.py`,
`media_asset_repository.py`, `entity_media_repository.py`,
`file_metadata_repository.py`, `platform_integration_repository.py`,
`password_reset_repository.py`, `communication_repository.py`,
`customer_communication_repository.py`, `__init__.py`

### Step E — Delete physical domain SERVICES

Delete from `app/services/`:
```
dynamic_material_service.py      enum_service.py
material_type_service.py         property_definition_service.py
preset_service.py                localization_service.py
tool_service.py                  pattern_service.py
workflow_service.py              workflow_event_handlers.py
workflow_execution_service.py    workflow_import_export_service.py
workflow_navigation_service.py   workflow_resource_service.py
project_service.py               project_template_service.py
recurring_project_service.py     timeline_task_service.py
component_service.py             storage_property_definition_service.py
```

Keep all commerce, user, storage, supplier, customer, and infrastructure services.

### Step F — Delete physical domain SCHEMAS

Delete from `app/schemas/`:
```
material.py          hardware_material.py  leather_material.py
supplies_material.py tool.py               pattern.py
workflow.py          project.py            recurring_project.py
component (if exists) dynamic_material.py  entity_translation.py
translation_api.py   enum.py               preset.py
compatibility.py     solution.md
```

Keep: `user.py`, `token.py`, `role.py`, `settings.py`, `analytics.py`,
`customer.py`, `sale.py`, `purchase.py`, `purchase_timeline.py`,
`refund.py`, `shipment.py`, `product.py`, `picking_list.py`,
`supplier.py`, `supplier_history.py`, `supplier_rating.py`,
`storage.py`, `inventory.py`, `annotation.py`, `webhook.py`,
`report.py`, `search_params.py`, `detail_responses.py`,
`media_asset.py`, `tag.py`, `__init__.py`

### Step G — Delete physical domain ENDPOINTS and deregister

Delete from `app/api/endpoints/`:
```
enums.py             material_types.py    property_definitions.py
dynamic_materials.py presets.py           translations.py
materials.py         tools.py             patterns.py
workflows.py         projects.py          project_templates.py
recurring_projects.py components.py
```

Remove their `include_router` calls from `app/api/api.py`.

### Step H — Delete root-level debris

```
api_database_diagnostic.py    database_diagnostics.py
database_write_read_diagnostic.py  db_diagnostics.py
db_fix_script.py              db_repair.py
debug_endpoint.py             debug_fix.py
extract_seed_data_hex.py      check_live_data.py
check_path.py
```

Also delete:
```
scripts/migrations/           (directory)
db_tools/populate_enums.py
app/db/enum_patch.py
app/settings/                 (directory)
```

### Step I — Update init_db.py and fix imports

Rewrite `app/db/init_db.py` to only import and create tables for surviving models.
Remove all imports from deleted modules throughout surviving files.
Do not recreate deleted files — remove the import instead.

Run: `python -m pytest --tb=short -q`
Fix import errors in surviving files only.

---

## Session 1 — Foundation

### Step A — Config additions
Add to `app/core/config.py`:
```python
MAKESTACK_CORE_URL: str = "http://localhost:8420"
MAKESTACK_API_KEY: str = ""
```

### Step B — MakestackClient
Create `app/core/makestack_client.py`:
```python
class MakestackClient:
    async def get_primitives(self, type=None, root=None) -> list[dict]
    async def get_primitive(self, path: str, at: str = None) -> dict
    async def get_primitive_hash(self, path: str) -> str
    async def create_primitive(self, data: dict) -> dict
    async def update_primitive(self, path: str, data: dict) -> dict
    async def delete_primitive(self, path: str) -> None
    async def search_primitives(self, q: str) -> list[dict]
    async def get_many(self, paths: list[str]) -> list[dict]  # concurrent
```

Error mapping: 404→EntityNotFoundException, 400→ValidationException,
409→BusinessRuleException, 503→MakestackUnavailableException, network→MakestackUnavailableException

Add `MakestackUnavailableException` to `app/core/exceptions.py`.

### Step C — Primitive schemas
Create `app/schemas/primitives.py` with `BasePrimitive` + Tool, Material,
Technique, Workflow, Project, Event subclasses + `PrimitiveUnion` discriminated union.

### Step D — PrimitiveRepository
Create `app/repositories/primitive_repository.py` wrapping MakestackClient.

### Step E — Dependency injection
Add `get_makestack_client()` and `get_primitive_repository()` to `app/api/deps.py`.

---

## Sessions 2–6 — Primitive Verticals (Tools → Materials → Techniques → Workflows → Projects)

Each session: create thin router in `app/api/endpoints/`, register in `api.py`,
write mocked unit tests. Follow Tools session as template.

WorkflowExecution (session 5) and ProjectSchedule (session 6) are user-state
models that stay in SQLAlchemy — create minimal models for them.

---

## Session 7 — Inventory Rewrite

Rewrite `app/db/models/inventory.py` with `core_path`/`commit_hash` fields.
Rewrite `app/services/inventory_service.py` with the merge flow.
Create `app/repositories/state_repository.py`.
Update `app/api/endpoints/inventory.py`.

---

## Sessions 8–13 — Commerce Cleanup & Infrastructure

Update commerce models to replace integer material/tool FKs with `core_path` strings.
Clean service_factory, repository_factory, search_service, dashboard_service.

---

## Session 14 — Final Audit

All grep checks must return zero:
```bash
grep -r "sqlcipher\|pragma key\|pysqlcipher" app/
grep -r "dynamic_material\|property_definition\|enum_service" app/
grep -r "from app.db.models.material\|from app.db.models.tool" app/
grep -r "from app.db.models.pattern\|from app.db.models.workflow" app/
grep -r "from app.db.models.project import\|from app.db.models.component" app/
grep -r "Adapter\|Compat\|Bridge\|Wrapper" app/
```

App must start: `uvicorn app.main:app --reload`
GET /health → 200, GET /api/tools → list from makestack-core
