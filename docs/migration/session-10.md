# Session 10 — Suppliers

**Goal:** Clean supplier domain of any references to deleted domain models.
Suppliers are entirely user-owned; no interaction with makestack-core.

**Prerequisites:** Session 9 complete.

**Scope:**
```
app/db/models/    supplier.py, supplier_history.py, supplier_rating.py
app/repositories/ supplier_repository.py, supplier_history_repository.py,
                  supplier_rating_repository.py
app/services/     supplier_service.py, supplier_history_service.py,
                  supplier_rating_service.py
app/schemas/      supplier.py, supplier_history.py, supplier_rating.py
app/api/endpoints/ suppliers.py
```

**Strategy:** Cleanup only. No new functionality.

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_suppliers.py -v
python -m pytest -m "not integration" -q
```

---

## Step A — Models

### `supplier.py`

Audit for:
- Any relationship to `Material` (supplier supplied materials).
  Material is now a Core primitive. Remove the relationship.
  If the supplier's materials need to be tracked, a supplier can be referenced
  in a manifest's `relationships` array in Core:
  ```json
  { "type": "supplied_by", "target": "suppliers/abc/manifest.json" }
  ```
  Or store it as a tag: `["supplier:wickett-craig"]`.
  The Python DB supplier row is the authoritative supplier record.
  Core manifests can reference it by a slug or ID string.

- Remove any `SupplierMaterial` junction table references if that model
  was in `material.py` (which was deleted).

### `supplier_history.py`, `supplier_rating.py`

These are likely clean already. Audit for any deleted model imports.

---

## Step B — Repositories, Services, Schemas, Endpoints

For each file in scope:
1. Remove imports from deleted modules.
2. Remove methods that queried deleted tables.
3. Update schemas to remove fields that referenced deleted types.

Common patterns to fix:
```python
# Remove
from app.db.models.material import Material
from app.schemas.material import MaterialRead

# Remove method like:
def get_materials_for_supplier(self, supplier_id: int) -> List[Material]: ...
```

If a method like `get_materials_for_supplier` is needed for business logic,
note that it must now call makestack-core search:
```python
# New pattern (in service, not repository):
async def get_materials_for_supplier(self, supplier_slug: str) -> list:
    return await primitive_repo.search(q=f"supplier:{supplier_slug}")
```
But only implement this if it was an active endpoint — don't add features.

---

## Test Gate

```bash
python -m pytest -m "not integration" -q
```
