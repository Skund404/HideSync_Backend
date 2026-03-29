# Session 0 — SQLCipher + Physical Domain Removal

**Goal:** Eliminate all encryption infrastructure and every physical domain
model, repository, service, schema, and endpoint. Leave only userDB and
commerce code intact. The app will not start cleanly after this session —
that is expected. Session 1 wires in the replacement.

**Prerequisites:** None. This is the first session.

**Test gate:** `python -c "from app.core.config import settings; print('OK')"` passes.
`python -m pytest --collect-only -q` collects without import errors on
surviving test files.

---

## Step A — Delete SQLCipher infrastructure

### Files to delete entirely
```
app/sqlcipher_dialect.py
app/core/key_manager.py
app/db/session.py.bak
SQLCipher_connection_test.py
sqlcipher_diagnostic.py
dev_db.key
scripts/generate_key.py
```

### Remove from `requirements.txt`
Delete the line: `pysqlcipher3`

### Rewrite `app/core/config.py`

Replace the entire file. Keep: API settings, security/JWT, CORS, email,
superuser, metrics. Add makestack settings. Remove everything SQLCipher/key-management.

```python
"""Application configuration for HideSync."""

import secrets
from typing import List, Optional, Union

from pydantic import AnyHttpUrl, EmailStr, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "HideSync"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    FRONTEND_URL: str = "http://localhost:3000"
    JWT_ALGORITHM: str = "HS256"
    TOKEN_URL: str = "/api/v1/auth/login"
    MIN_PASSWORD_LENGTH: int = 4

    # CORS
    BACKEND_CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                return [i.strip() for i in v.split(",")]
        return v or []

    # Database — plain SQLite for dev
    DATABASE_URL: str = "sqlite:///./hidesync.db"

    # makestack-core
    MAKESTACK_CORE_URL: str = "http://localhost:8420"
    MAKESTACK_API_KEY: str = ""

    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None

    # Superuser
    FIRST_SUPERUSER: EmailStr = "admin@hidesync.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin"
    FIRST_SUPERUSER_USERNAME: str = "admin"
    FIRST_SUPERUSER_FULLNAME: str = "HideSync Administrator"

    # Metrics
    ENABLE_METRICS: bool = True

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
```

### Rewrite `app/db/session.py`

Replace the entire file with a minimal standard SQLAlchemy session:

```python
"""Database session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings
from app.db.models.base import Base

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## Step B — Delete physical domain MODELS

Delete these files from `app/db/models/`:
```
material.py
tool.py
pattern.py
workflow.py
project.py
component.py
timeline_task.py
recurring_project.py
dynamic_enum.py
dynamic_material.py
entity_translation.py
preset.py
associations.py
association_media.py
```

**Do not delete:**
```
base.py               user.py              role.py
password_reset.py     settings.py          enums.py
customer.py           supplier.py          supplier_history.py
supplier_rating.py    sales.py             purchase.py
shipment.py           refund.py            product.py
picking_list.py       storage.py           inventory.py
tag.py                media_asset.py       entity_media.py
documentation.py      annotation.py        platform_integration.py
file_metadata.py      communication.py
customer_communication_service.py   (misnamed model — fix name in session 11)
```

### Update `app/db/models/__init__.py`

Remove imports for every deleted model. Only import surviving models.

---

## Step C — Prune `app/db/models/enums.py`

Delete these enum classes (catalogue-only — replaced by core manifest tags):
```
AnimalSource
ComponentType
EdgeFinishType
HardwareFinish
HardwareMaterialEnum
HardwareType
LeatherFinish
LeatherType
MaterialQualityGrade
MaterialStatus
MaterialType
PatternFileType
ProjectType
SuppliesMaterialType
TannageType
TimelineTaskStatus
ToolCategory
ToolCondition
ToolStatus
ToolType
MaintenanceType
WoodFinish
WoodGrain
WoodType
WorkflowConnectionType
WorkflowStatus
WorkflowStepType
WorkflowThemeStyle
```

**Keep** these enum classes (userDB operational enums — used in surviving models):
```
CommunicationChannel    CommunicationType       CustomerSource
CustomerStatus          CustomerTier            DocumentationCategory
FulfillmentStatus       FileType                InventoryAdjustmentType
InventoryStatus         InventoryTransactionType MeasurementUnit
PaymentStatus           PickingListItemStatus   PickingListStatus
ProjectStatus           PurchaseOrderStatus     PurchaseStatus
QualityGrade            SaleStatus              SkillLevel
StorageLocationStatus   StorageLocationType     StorageSection
SupplierStatus          ToolListStatus          TransactionType
UserRole
```

After pruning, scan surviving model files for any import of a deleted enum
and remove that import (or the column using it).

---

## Step D — Delete physical domain REPOSITORIES

Delete from `app/repositories/`:
```
material_repository.py
tool_repository.py
pattern_repository.py
workflow_repository.py
workflow_step_repository.py
project_repository.py
project_template_repository.py
recurring_project_repository.py
component_repository.py
timeline_task_repository.py
workflow_execution_repository.py
dynamic_material_repository.py
material_type_repository.py
property_definition_repository.py
entity_translation_repository.py
preset_repository.py
media_asset_tag_repository.py
```

**Keep:**
```
__init__.py                         base_repository.py
user_repository.py                  role_repository.py
password_reset_repository.py        settings_repository.py
inventory_repository.py             inventory_transaction_repository.py
customer_repository.py              supplier_repository.py
supplier_history_repository.py      supplier_rating_repository.py
sale_repository.py                  purchase_repository.py
shipment_repository.py              refund_repository.py
product_repository.py               picking_list_repository.py
storage_repository.py               tag_repository.py
annotation_repository.py            documentation_repository.py
media_asset_repository.py           entity_media_repository.py
file_metadata_repository.py         platform_integration_repository.py
communication_repository.py         customer_communication_repository.py
```

### Gut `app/repositories/repository_factory.py`

Remove factory methods for every deleted repository. Keep only methods for
surviving repositories. The file itself stays.

---

## Step E — Delete physical domain SERVICES

Delete from `app/services/`:
```
dynamic_material_service.py
enum_service.py
material_type_service.py
property_definition_service.py
preset_service.py
localization_service.py
tool_service.py
pattern_service.py
workflow_service.py
workflow_event_handlers.py
workflow_execution_service.py
workflow_import_export_service.py
workflow_navigation_service.py
workflow_resource_service.py
project_service.py
project_template_service.py
recurring_project_service.py
timeline_task_service.py
component_service.py
storage_property_definition_service.py
```

**Keep:**
```
__init__.py                     base_service.py
service_factory.py              (gut contents — remove deleted services)
user_service.py                 role_service.py
settings_service.py             audit_service.py
cache_service.py                notification_service.py
search_service.py               (will be rewritten in session 13)
dashboard_service.py            report_service.py
analytics (if any)              import_export_service.py
inventory_service.py            customer_service.py
supplier_service.py             supplier_history_service.py
supplier_rating_service.py      sale_service.py
purchase_service.py             purchase_timeline_service.py
refund_service.py               shipment_service.py
product_service.py              picking_list_service.py
storage_service.py              storage_location_service.py
storage_location_type_service.py
tag_service.py                  media_asset_service.py
entity_media_service.py         documentation_service.py
annotation_service.py           file_storage_service.py
platform_integration_service.py customer_communication_service.py
```

### Gut `app/services/service_factory.py`

Remove registrations for every deleted service. Keep the file.

---

## Step F — Delete physical domain SCHEMAS

Delete from `app/schemas/`:
```
material.py
hardware_material.py
leather_material.py
supplies_material.py
tool.py
pattern.py
workflow.py
project.py
recurring_project.py
dynamic_material.py
entity_translation.py
translation_api.py
enum.py
preset.py
compatibility.py
solution.md
```

**Keep:**
```
__init__.py             user.py             token.py
role.py                 settings.py         analytics.py
customer.py             sale.py             purchase.py
purchase_timeline.py    refund.py           shipment.py
product.py              picking_list.py     supplier.py
supplier_history.py     supplier_rating.py  storage.py
inventory.py            annotation.py       webhook.py
report.py               search_params.py    detail_responses.py
media_asset.py          tag.py
```

Note: `inventory.py` schema is kept but marked for full rewrite in session 7.
`product.py` schema is kept but will need cleanup in session 9.

---

## Step G — Delete physical domain ENDPOINTS and update `api.py`

Delete from `app/api/endpoints/`:
```
enums.py
material_types.py
property_definitions.py
dynamic_materials.py
presets.py
translations.py
materials.py
tools.py
patterns.py
workflows.py
projects.py
project_templates.py
recurring_projects.py
components.py
```

### Rewrite `app/api/api.py`

Remove every import and `include_router` call for deleted endpoints.
Surviving registrations after this session:

```python
from fastapi import APIRouter
from app.api.endpoints import (
    analytics, annotations, auth, customers, documentation,
    entity_media, inventory, media_assets, picking_list,
    platform_integrations, products, purchases, qrcode,
    refunds, reports, roles, sales, settings, shipments,
    storage, suppliers, tags, users, webhooks,
)

api_router = APIRouter()

api_router.include_router(analytics.router,              prefix="/analytics",             tags=["Analytics"])
api_router.include_router(annotations.router,            prefix="/annotations",           tags=["Annotations"])
api_router.include_router(auth.router,                   prefix="/auth",                  tags=["Authentication"])
api_router.include_router(customers.router,              prefix="/customers",             tags=["Customers"])
api_router.include_router(documentation.router,          prefix="/documentation",         tags=["Documentation"])
api_router.include_router(entity_media.router,           prefix="/entity-media",          tags=["Entity Media"])
api_router.include_router(inventory.router,              prefix="/inventory",             tags=["Inventory"])
api_router.include_router(media_assets.router,           prefix="/media-assets",          tags=["Media Assets"])
api_router.include_router(picking_list.router,           prefix="/picking-lists",         tags=["Picking Lists"])
api_router.include_router(platform_integrations.router,  prefix="/integrations",          tags=["Integrations"])
api_router.include_router(products.router,               prefix="/products",              tags=["Products"])
api_router.include_router(purchases.router,              prefix="/purchases",             tags=["Purchases"])
api_router.include_router(qrcode.router,                 prefix="/qrcode",               tags=["QR Code"])
api_router.include_router(refunds.router,                prefix="/refunds",               tags=["Refunds"])
api_router.include_router(reports.router,                prefix="/reports",               tags=["Reports"])
api_router.include_router(roles.router,                  prefix="/roles",                 tags=["Roles"])
api_router.include_router(sales.router,                  prefix="/sales",                 tags=["Sales"])
api_router.include_router(settings.router,               prefix="/settings",              tags=["Settings"])
api_router.include_router(shipments.router,              prefix="/shipments",             tags=["Shipments"])
api_router.include_router(storage.router,                prefix="/storage",               tags=["Storage"])
api_router.include_router(suppliers.router,              prefix="/suppliers",             tags=["Suppliers"])
api_router.include_router(tags.router,                   prefix="/tags",                  tags=["Tags"])
api_router.include_router(users.router,                  prefix="/users",                 tags=["Users"])
api_router.include_router(webhooks.router,               prefix="/webhooks",              tags=["Webhooks"])
```

---

## Step H — Delete root-level debris

```
api_database_diagnostic.py
database_diagnostics.py
database_write_read_diagnostic.py
db_diagnostics.py
db_fix_script.py
db_repair.py
debug_endpoint.py
debug_fix.py
extract_seed_data_hex.py
check_live_data.py
check_path.py
```

Also delete:
```
scripts/migrations/          (entire directory)
db_tools/populate_enums.py
app/db/enum_patch.py
app/settings/                (entire directory)
```

---

## Step I — Fix surviving files

### `app/db/init_db.py`

Rewrite to only import and create tables for surviving models:

```python
"""Database initialisation."""

import logging
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, init_db
from app.services.user_service import UserService
from app.schemas.user import UserCreate
from app.core.config import settings

logger = logging.getLogger(__name__)


def init(db: Session) -> None:
    init_db()

    user_service = UserService(db)
    admin = user_service.get_by_email(email=settings.FIRST_SUPERUSER)
    if not admin:
        user_service.create_user(UserCreate(
            email=settings.FIRST_SUPERUSER,
            username=settings.FIRST_SUPERUSER_USERNAME,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            full_name=settings.FIRST_SUPERUSER_FULLNAME,
            is_superuser=True,
        ))


def main() -> None:
    db = SessionLocal()
    try:
        init(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

### Scan surviving files for broken imports

For each surviving file in `app/`, run:
```bash
python -c "import app.path.to.module"
```

For every `ImportError`:
- If it imports from a **deleted module** → remove the import line.
- Do NOT recreate the deleted module to fix the error.
- If a model field uses a deleted enum → remove the field or change to `String`.
- If a service method calls a deleted service → remove the method.

Common patterns to grep for and fix:
```bash
grep -r "from app.db.models.material"     app/
grep -r "from app.db.models.tool"         app/
grep -r "from app.db.models.pattern"      app/
grep -r "from app.db.models.workflow"     app/
grep -r "from app.db.models.project"      app/
grep -r "from app.db.models.component"    app/
grep -r "from app.db.models.timeline"     app/
grep -r "from app.db.models.dynamic"      app/
grep -r "from app.db.models.entity_trans" app/
grep -r "from app.db.models.preset"       app/
grep -r "from app.db.models.associations" app/
grep -r "from app.core.key_manager"       app/
grep -r "sqlcipher\|pragma key"           app/
```

### `app/main.py`

Remove imports of deleted modules (events.py may reference deleted services,
db_metrics.py may reference SQLCipher). Fix or stub as needed.

---

## Test Gate

```bash
# Config loads
python -c "from app.core.config import settings; print(settings.DATABASE_URL)"

# DB session loads
python -c "from app.db.session import SessionLocal; print('OK')"

# API router loads
python -c "from app.api.api import api_router; print('OK')"

# Pytest collects without errors
python -m pytest --collect-only -q 2>&1 | grep -E "error|Error" | head -20
```

All four must pass before starting session 1.
