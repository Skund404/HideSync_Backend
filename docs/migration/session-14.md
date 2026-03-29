# Session 14 — Final Audit

**Goal:** Confirm the migration is complete. Every grep check returns zero.
App starts. Health check returns 200. Full test suite passes.

**Prerequisites:** Sessions 0–13 complete.

---

## Step A — Grep checks (all must return zero results)

Run each command. Fix any non-zero result before proceeding to the next check.

```bash
# No SQLCipher remnants
grep -r "sqlcipher\|pragma key\|pysqlcipher" app/

# No deleted dynamic systems
grep -r "dynamic_material\|property_definition\|enum_service\|preset_service" app/
grep -r "material_type_service\|localization_service" app/
grep -r "DynamicMaterial\|EnumType\|EnumTranslation\|EntityTranslation" app/

# No deleted domain model imports
grep -r "from app\.db\.models\.material" app/
grep -r "from app\.db\.models\.tool" app/
grep -r "from app\.db\.models\.pattern" app/
grep -r "from app\.db\.models\.workflow import" app/
grep -r "from app\.db\.models\.project import" app/
grep -r "from app\.db\.models\.component" app/
grep -r "from app\.db\.models\.timeline" app/
grep -r "from app\.db\.models\.recurring" app/
grep -r "from app\.db\.models\.dynamic" app/
grep -r "from app\.db\.models\.entity_trans" app/
grep -r "from app\.db\.models\.preset" app/
grep -r "from app\.db\.models\.associations" app/

# No deleted service imports
grep -r "from app\.services\.tool_service" app/
grep -r "from app\.services\.material" app/
grep -r "from app\.services\.pattern" app/
grep -r "from app\.services\.workflow_service" app/
grep -r "from app\.services\.project_service" app/
grep -r "from app\.services\.component" app/
grep -r "from app\.services\.dynamic" app/
grep -r "from app\.services\.enum_service" app/

# No deleted repository imports
grep -r "from app\.repositories\.material" app/
grep -r "from app\.repositories\.tool" app/
grep -r "from app\.repositories\.pattern" app/
grep -r "from app\.repositories\.workflow_repo" app/
grep -r "from app\.repositories\.project_repo" app/
grep -r "from app\.repositories\.dynamic" app/
grep -r "from app\.repositories\.entity_trans" app/
grep -r "from app\.repositories\.preset" app/

# No key manager
grep -r "from app\.core\.key_manager" app/

# No shim layers
grep -r "class.*Adapter\|class.*Compat\|class.*Bridge\|class.*Wrapper" app/
```

---

## Step B — Module imports verify

```bash
python -c "from app.core.config import settings; print('config OK')"
python -c "from app.db.session import get_db; print('session OK')"
python -c "from app.api.api import api_router; print('api_router OK')"
python -c "from app.core.makestack_client import MakestackClient; print('client OK')"
python -c "from app.repositories.primitive_repository import PrimitiveRepository; print('prim_repo OK')"
python -c "from app.schemas.primitives import PrimitiveUnion; print('schemas OK')"
```

---

## Step C — Rebuild `__init__.py` files

### `app/db/models/__init__.py`

Should only import surviving models:
```python
from app.db.models.base import Base, AbstractBase
from app.db.models.user import User
from app.db.models.role import Role
from app.db.models.password_reset import PasswordResetToken
from app.db.models.settings import Settings
from app.db.models.enums import *  # operational enums only
from app.db.models.inventory import Inventory, InventoryTransaction
from app.db.models.customer import Customer
from app.db.models.supplier import Supplier
from app.db.models.supplier_history import SupplierHistory
from app.db.models.supplier_rating import SupplierRating
from app.db.models.sales import Sale, SaleItem
from app.db.models.purchase import Purchase, PurchaseItem
from app.db.models.shipment import Shipment
from app.db.models.refund import Refund
from app.db.models.product import Product
from app.db.models.picking_list import PickingList, PickingListItem
from app.db.models.storage import StorageLocation, StorageCell, StorageAssignment, StorageMove
from app.db.models.tag import Tag
from app.db.models.media_asset import MediaAsset
from app.db.models.entity_media import EntityMedia
from app.db.models.documentation import DocumentationCategory, DocumentationResource
from app.db.models.annotation import Annotation
from app.db.models.platform_integration import PlatformIntegration
from app.db.models.file_metadata import FileMetadata
from app.db.models.communication import Communication
from app.db.models.customer_communication import CustomerCommunication
from app.db.models.workflow_execution import WorkflowExecution
```

### `app/schemas/__init__.py`

Should export surviving schemas + new primitives schema.

---

## Step D — Full test suite

```bash
python -m pytest -m "not integration" -v
```

Target: zero failures, zero errors.

If any test failures remain, fix them before marking session 14 complete.
Do not suppress or skip tests — fix the underlying issue.

---

## Step E — App smoke test

```bash
uvicorn app.main:app --reload &
sleep 3

# Health
curl -s http://localhost:8000/health
# Expected: 200 OK

# Auth
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin@hidesync.com&password=admin" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# List tools (requires running makestack-core)
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/tools/

# User inventory
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/inventory/

kill %1
```

---

## Step F — Documentation cleanup

Delete legacy documentation files:
```
app/docs/Domain/dynamic_enum_system_domain_documentation.md
app/docs/Dynamic_Material_Management_System.md
app/docs/SQLAlchemy Case-Insensitive Enum Patch.md
```
(adjust filenames to match actual files in `app/docs/`)

---

## Step G — Final report

Record:
- File count before migration (from git log of first commit on this branch)
- File count after migration
- Line count reduction in `app/`
- Number of deleted SQLAlchemy models
- Number of surviving SQLAlchemy models
- Test count before / after
