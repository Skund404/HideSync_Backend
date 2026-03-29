# Session 13 — Infrastructure

**Goal:** Update shared infrastructure — search, service/repository factories,
analytics, dashboard, tags, media assets, import/export, notifications.

**Prerequisites:** Sessions 0–12 complete. Full test suite passing.

**Scope:**
```
app/services/  search_service.py, service_factory.py,
               dashboard_service.py, report_service.py,
               tag_service.py, media_asset_service.py,
               entity_media_service.py, import_export_service.py,
               notification_service.py, audit_service.py,
               cache_service.py, platform_integration_service.py
app/repositories/ repository_factory.py
app/dependencies/ repositories.py (if exists)
app/api/endpoints/ analytics.py, reports.py, tags.py,
                   media_assets.py, entity_media.py,
                   platform_integrations.py
```

---

## Step A — Search service (`app/services/search_service.py`)

The old search service queried SQLAlchemy models for materials, tools, etc.
Rewrite to fan out to both makestack-core and the Python DB:

```python
"""
Search service — fans out to makestack-core FTS and app DB.

Results from Core: primitives (tools, materials, techniques, workflows,
projects, events) — rich FTS5 search.

Results from app DB: customers (by name/email), suppliers (by name),
sales (by reference number), purchases (by order number).
"""

import asyncio
from typing import Any
from sqlalchemy.orm import Session
from app.repositories.primitive_repository import PrimitiveRepository


class SearchService:
    def __init__(self, db: Session, primitive_repo: PrimitiveRepository) -> None:
        self._db = db
        self._primitives = primitive_repo

    async def search(self, q: str) -> dict[str, list[Any]]:
        # Run Core FTS and DB search concurrently
        core_results, db_results = await asyncio.gather(
            self._search_core(q),
            asyncio.to_thread(self._search_db, q),
        )
        return {
            "primitives": core_results,
            "customers": db_results.get("customers", []),
            "suppliers": db_results.get("suppliers", []),
            "sales": db_results.get("sales", []),
        }

    async def _search_core(self, q: str) -> list:
        try:
            return await self._primitives.search(q)
        except Exception:
            return []

    def _search_db(self, q: str) -> dict:
        from app.db.models.customer import Customer
        from app.db.models.supplier import Supplier
        from app.db.models.sales import Sale

        like = f"%{q}%"
        customers = self._db.query(Customer).filter(
            Customer.name.ilike(like)
        ).limit(10).all()
        suppliers = self._db.query(Supplier).filter(
            Supplier.name.ilike(like)
        ).limit(10).all()
        sales = self._db.query(Sale).filter(
            Sale.reference_number.ilike(like)
        ).limit(10).all() if hasattr(Sale, "reference_number") else []

        return {
            "customers": customers,
            "suppliers": suppliers,
            "sales": sales,
        }
```

---

## Step B — Tags (`app/services/tag_service.py`, `app/db/models/tag.py`)

Audit `tag.py` model:
- If tags were applied only to domain primitives (Material, Tool, etc.) via
  association tables that were deleted — the tag model may now have no
  remaining associations. Evaluate whether to keep or delete.
- If tags are applied to app-owned entities (customers, products, sales) via
  a surviving junction table — keep the model and service, remove dead associations.
- Primitive tags are manifest fields managed directly in makestack-core.
  Do NOT replicate them in the Python DB tag table.

---

## Step C — Service factory (`app/services/service_factory.py`)

Remove all registrations for deleted services. The file should only register
services for surviving domains: user, role, inventory, customer, supplier,
sale, purchase, shipment, refund, product, picking_list, storage, tag,
media_asset, documentation, annotation, platform_integration.

If `service_factory.py` has become trivially small after gutting, consider
whether it's still needed or whether direct instantiation in `deps.py` is cleaner.

---

## Step D — Repository factory (`app/repositories/repository_factory.py`)

Same as service factory: remove all methods for deleted repositories.

---

## Step E — Dashboard / Analytics / Reports

`dashboard_service.py` likely counted materials, tools, projects by querying
SQLAlchemy. Update counts to call makestack-core:

```python
async def get_counts(self) -> dict:
    tools = await self._primitives.list(type="tool")
    materials = await self._primitives.list(type="material")
    # Local counts from DB
    from sqlalchemy import func
    customer_count = self._db.query(func.count(Customer.id)).scalar()
    sale_count = self._db.query(func.count(Sale.id)).scalar()
    return {
        "tools": len(tools),
        "materials": len(materials),
        "customers": customer_count,
        "sales": sale_count,
    }
```

---

## Step F — Import/Export (`app/services/import_export_service.py`)

The old import/export format was likely a DMMS-specific format.
Evaluate what this service does now:
- Exporting Core primitives: Core has its own JSON manifest format — use that.
  The Python backend can proxy an export by calling `primitive_repo.list()` and
  returning the JSON directly.
- Importing: POST to Core via `primitive_repo.create()`.
- Exporting user state (inventory, sales): still meaningful — keep this path.

Rewrite or simplify based on what is actually used.

---

## Step G — `app/main.py` cleanup

Audit `app/main.py` for:
- `setup_event_handlers()` — check `events.py` for deleted service references.
- `register_material_settings_on_startup()` — this likely called `app/settings/`
  which was deleted. Remove or replace with a no-op.
- Any startup code importing deleted modules.

---

## Test Gate

```bash
python -m pytest -m "not integration" -q   # zero failures

# App starts cleanly
uvicorn app.main:app --reload
curl http://localhost:8000/health
# → 200 OK
```
