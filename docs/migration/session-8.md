# Session 8 — Storage

**Goal:** Clean storage models, repositories, services, and schemas of all
references to deleted domain models. Storage is entirely user-owned — no
interaction with makestack-core.

**Prerequisites:** Session 7 complete.

**Scope:**
- `app/db/models/storage.py`
- `app/repositories/storage_repository.py`
- `app/services/storage_service.py`
- `app/services/storage_location_service.py`
- `app/services/storage_location_type_service.py`
- `app/schemas/storage.py`
- `app/api/endpoints/storage.py`

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_storage.py -v
python -m pytest -m "not integration" -q
```

---

## Step A — Audit `app/db/models/storage.py`

Read the file and identify:
1. Any ForeignKey to deleted tables (`materials`, `tools`, `products` via old polymorphic IDs).
2. Any relationship() pointing to deleted models.
3. Any import from deleted modules.

**Expected changes:**
- `StorageAssignment` likely has a polymorphic `item_type`/`item_id` pattern
  pointing to Material or Tool rows. Replace with `core_path: String` for
  primitives and a nullable `product_id: Integer` FK for user-owned products.
- Remove any dynamic property definition columns or DMMS references.

New `StorageAssignment` shape:
```python
class StorageAssignment(AbstractBase):
    __tablename__ = "storage_assignments"

    storage_cell_id = Column(Integer, ForeignKey("storage_cells.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # For primitives (tools, materials) — reference to Core
    core_path = Column(String, nullable=True)

    # For user-owned items (products) — local FK
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)

    quantity = Column(Float, default=0.0)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(String, nullable=True)
```

---

## Step B — Audit `app/repositories/storage_repository.py`

Remove any query that joins against deleted tables.
Remove any method that accepted `item_type`/`item_id` and replace
parameters with `core_path: Optional[str]` and `product_id: Optional[int]`.

---

## Step C — Remove `storage_property_definition_service.py` references

This service was already deleted in session 0. Check that no surviving storage
service imports it. Remove any property-definition-related code in:
- `app/services/storage_service.py`
- `app/services/storage_location_service.py`

---

## Step D — Update `app/schemas/storage.py`

Remove any schema field that referenced deleted enum values:
- `item_type` enum discriminator → replace with `core_path: Optional[str]`
  and `product_id: Optional[int]`
- Remove: `StorageLocationType` values that reference deleted domain
  (likely fine as StorageLocationType stays in enums.py)

---

## Step E — Update `app/api/endpoints/storage.py`

Remove any endpoint that called a deleted service.
Ensure all remaining endpoints work with the updated storage service.

---

## Test Gate

```bash
python -m pytest -m "not integration" -q
```
