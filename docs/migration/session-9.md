# Session 9 — Commerce

**Goal:** Clean commerce models (sales, purchases, products, picking lists,
shipments, refunds) of integer FKs pointing to deleted domain tables.
Replace material/tool FKs with `core_path` strings.

**Prerequisites:** Session 8 complete.

**Scope:**
```
app/db/models/    sales.py, purchase.py, product.py, picking_list.py,
                  shipment.py, refund.py
app/repositories/ sale_repository.py, purchase_repository.py,
                  product_repository.py, picking_list_repository.py,
                  shipment_repository.py, refund_repository.py
app/services/     sale_service.py, purchase_service.py,
                  purchase_timeline_service.py, product_service.py,
                  picking_list_service.py, shipment_service.py,
                  refund_service.py
app/schemas/      sale.py, purchase.py, purchase_timeline.py,
                  product.py, picking_list.py, shipment.py, refund.py
app/api/endpoints/ sales.py, purchases.py, products.py,
                   picking_list.py, shipments.py, refunds.py
```

**Strategy:** Cleanup only. No new functionality. Work layer by layer:
models → repositories → services → schemas → endpoints.
Run pytest after each layer.

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_sales.py -v
python -m pytest tests/api/endpoints/test_purchases.py -v
python -m pytest -m "not integration" -q
```

---

## Step A — Models

### `sales.py` — `SaleItem`

`SaleItem` likely has a `material_id` or `product_id` integer FK.
Materials no longer have integer IDs in the Python DB.

Change:
```python
# Before
material_id = Column(Integer, ForeignKey("materials.id"), nullable=True)

# After — for primitives from Core
core_path = Column(String, nullable=True)
# For user-owned products that still have a local DB row:
product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
```

Remove the relationship() to Material/Tool. Keep the one to Product.

### `purchase.py` — `PurchaseItem`

Same pattern: replace `material_id` FK with `core_path: String`.
Keep `supplier_id` FK — suppliers remain in the Python DB.

### `product.py`

Product is a user-owned finished-good template. It may reference materials
used in its construction (via a `ComponentMaterial`-style table, or directly).
`Component` and `ComponentMaterial` models were deleted in session 0.

Audit `product.py`:
- Remove any relationship to Component or ComponentMaterial.
- If a `bill_of_materials` relationship existed, replace with a simple
  `materials: list[str]` JSON column storing core_paths:
  ```python
  bill_of_materials = Column(JSON, nullable=True)
  # Stores: [{"core_path": "materials/veg-tan/manifest.json", "quantity": 0.5, "unit": "m²"}]
  ```

### `picking_list.py` — `PickingListItem`

`PickingListItem` references items to pick. Replace integer `material_id`/
`tool_id` FKs with `core_path: String`.

---

## Step B — Repositories

For each repository listed in scope:
1. Remove any query joining against deleted tables.
2. Replace `filter_by(material_id=...)` with `filter_by(core_path=...)`.
3. Remove eager-load options for deleted relationships.

---

## Step C — Services

For each service listed in scope:
1. Remove calls to deleted services (tool_service, material_service, etc.).
2. If a service method fetched material details for display, it now needs
   to accept `core_path` and call `PrimitiveRepository.get(core_path)`.
   Add `PrimitiveRepository` as an injected dependency where needed.
3. Remove any import of deleted schemas or models.

### `sale_service.py` — inventory deduction on sale

When a sale is confirmed, inventory should be deducted.
Old pattern: `inventory_repo.adjust(material_id, -qty)`.
New pattern: `inventory_service.adjust_quantity(user_id, inventory_id, adj)`.

The `inventory_id` can be looked up via `state_repo.get_inventory_item(user_id, core_path)`.

---

## Step D — Schemas

For each schema listed in scope:
1. Replace `material_id: int` fields with `core_path: Optional[str]`.
2. Remove any `MaterialRead` / `ToolRead` embedded response schemas
   (those schemas were deleted in session 0).
3. If a response schema included nested material data for display, replace
   with an optional `manifest: Optional[dict]` field that the service
   populates by calling Core.

---

## Step E — Endpoints

For each endpoint listed in scope:
1. Remove any `Depends()` that injected a deleted service.
2. Where services now need `PrimitiveRepository`, inject it from `deps.py`.
3. Verify response shapes match the updated schemas.

---

## Test Gate

```bash
python -m pytest -m "not integration" -q
```

Zero failures required before moving to session 10.
