# Session 7 — Inventory

**Goal:** Rewrite the `Inventory` model, service, and endpoint to use
`core_path` references instead of polymorphic integer FKs to deleted models.
Implement the merge flow that zips user quantities with live manifests from Core.

**Prerequisites:** Sessions 2–6 complete (all six primitive endpoints stable).

**Scope:**
- `app/db/models/inventory.py` (rewrite)
- `app/schemas/inventory.py` (rewrite)
- `app/repositories/state_repository.py` (new)
- `app/repositories/inventory_repository.py` (update or replace)
- `app/services/inventory_service.py` (rewrite)
- `app/api/endpoints/inventory.py` (update)

**Test gate:**
```bash
python -m pytest tests/services/test_inventory_service.py -v
python -m pytest tests/api/endpoints/test_inventory.py -v
```

---

## Step A — Rewrite `app/db/models/inventory.py`

Replace the current polymorphic model entirely:

```python
"""
Inventory model — tracks user stock levels for makestack-core primitives.

Stores a reference (core_path) to the primitive definition in makestack-core,
plus the user's quantity for that item. All descriptive data (name, description,
tags) is fetched live from makestack-core when needed.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.db.models.base import AbstractBase


class Inventory(AbstractBase):
    __tablename__ = "inventory"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Reference to makestack-core
    core_path = Column(String, nullable=False, index=True)
    # e.g. "tools/swivel-knife/manifest.json"
    # or   "materials/veg-tan-leather/manifest.json"

    commit_hash = Column(String, nullable=True)
    # Hash pinned at time of entry — use for "as purchased" version.
    # Null = always fetch latest.

    primitive_type = Column(String, nullable=False)
    # Denormalized from the manifest: "tool" | "material"
    # Avoids a round-trip to Core just to know what type this is.

    quantity = Column(Float, nullable=False, default=0.0)
    unit = Column(String, nullable=True)          # e.g. "m²", "kg", "pieces"
    reorder_point = Column(Float, nullable=True)  # trigger for low-stock alerts
    storage_location = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Inventory(user={self.user_id}, path={self.core_path}, qty={self.quantity})>"
```

Also rewrite `InventoryTransaction` in the same file to use `core_path` instead
of `item_type`/`item_id`:

```python
from app.db.models.enums import InventoryAdjustmentType, TransactionType

class InventoryTransaction(AbstractBase):
    __tablename__ = "inventory_transactions"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    core_path = Column(String, nullable=False, index=True)
    quantity = Column(Float, nullable=False)          # positive = in, negative = out
    transaction_type = Column(String, nullable=False) # from TransactionType enum
    adjustment_type = Column(String, nullable=True)   # from InventoryAdjustmentType enum

    # Context FKs (still valid — sales/purchases still exist in Python DB)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)

    from_location = Column(String, nullable=True)
    to_location = Column(String, nullable=True)
    performed_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    transaction_date = Column(DateTime, default=datetime.utcnow)
```

Remove the `project_id` FK — project is now a core primitive, not a Python DB row.

---

## Step B — Rewrite `app/schemas/inventory.py`

```python
"""Inventory schemas — user stock + merged manifest data."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class InventoryBase(BaseModel):
    core_path: str
    primitive_type: str
    quantity: float
    unit: Optional[str] = None
    reorder_point: Optional[float] = None
    storage_location: Optional[str] = None
    notes: Optional[str] = None


class InventoryCreate(InventoryBase):
    user_id: int
    commit_hash: Optional[str] = None


class InventoryUpdate(BaseModel):
    quantity: Optional[float] = None
    unit: Optional[str] = None
    reorder_point: Optional[float] = None
    storage_location: Optional[str] = None
    notes: Optional[str] = None


class InventoryRead(InventoryBase):
    """Raw inventory row — no manifest data."""
    id: int
    user_id: int
    commit_hash: Optional[str]
    last_updated: datetime

    class Config:
        from_attributes = True


class InventoryMerged(BaseModel):
    """
    Merged view: user inventory row + live manifest data from Core.
    Returned by GET /inventory endpoints for display purposes.
    """
    # From user DB
    id: int
    user_id: int
    core_path: str
    commit_hash: Optional[str]
    primitive_type: str
    quantity: float
    unit: Optional[str]
    reorder_point: Optional[float]
    storage_location: Optional[str]
    notes: Optional[str]
    last_updated: datetime

    # From makestack-core manifest (may be None if Core is unavailable)
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    manifest: Optional[Dict[str, Any]] = None   # full manifest for rich display


class InventoryAdjustment(BaseModel):
    quantity_delta: float       # positive = add stock, negative = consume
    transaction_type: str       # from TransactionType enum value
    adjustment_type: Optional[str] = None
    notes: Optional[str] = None
    performed_by: Optional[str] = None
```

---

## Step C — Create `app/repositories/state_repository.py`

```python
"""
StateRepository — SQLAlchemy CRUD for user-owned inventory state.

Deliberately simple. No business logic here — that lives in InventoryService.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from app.db.models.inventory import Inventory, InventoryTransaction
from app.schemas.inventory import InventoryCreate, InventoryUpdate


class StateRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Inventory ──────────────────────────────────────────────────────────

    def get_inventory_for_user(self, user_id: int) -> List[Inventory]:
        return self._db.query(Inventory).filter_by(user_id=user_id).all()

    def get_inventory_item(self, user_id: int, core_path: str) -> Optional[Inventory]:
        return (
            self._db.query(Inventory)
            .filter_by(user_id=user_id, core_path=core_path)
            .first()
        )

    def get_by_id(self, inventory_id: int) -> Optional[Inventory]:
        return self._db.get(Inventory, inventory_id)

    def create(self, data: InventoryCreate) -> Inventory:
        obj = Inventory(**data.model_dump())
        self._db.add(obj)
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def update(self, inventory_id: int, data: InventoryUpdate) -> Inventory:
        obj = self.get_by_id(inventory_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(obj, field, value)
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def update_quantity(self, inventory_id: int, delta: float) -> Inventory:
        obj = self.get_by_id(inventory_id)
        obj.quantity = max(0.0, obj.quantity + delta)
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def delete(self, inventory_id: int) -> None:
        obj = self.get_by_id(inventory_id)
        if obj:
            self._db.delete(obj)
            self._db.commit()

    def list_low_stock(self, user_id: int) -> List[Inventory]:
        """Return items where quantity <= reorder_point."""
        return (
            self._db.query(Inventory)
            .filter(
                Inventory.user_id == user_id,
                Inventory.reorder_point.isnot(None),
                Inventory.quantity <= Inventory.reorder_point,
            )
            .all()
        )

    # ── Transactions ───────────────────────────────────────────────────────

    def record_transaction(self, **kwargs) -> InventoryTransaction:
        txn = InventoryTransaction(**kwargs)
        self._db.add(txn)
        self._db.commit()
        self._db.refresh(txn)
        return txn

    def get_transactions_for_item(
        self, user_id: int, core_path: str, limit: int = 50
    ) -> List[InventoryTransaction]:
        return (
            self._db.query(InventoryTransaction)
            .filter_by(user_id=user_id, core_path=core_path)
            .order_by(InventoryTransaction.transaction_date.desc())
            .limit(limit)
            .all()
        )
```

---

## Step D — Rewrite `app/services/inventory_service.py`

```python
"""
Inventory service — owns the merge flow between user DB and makestack-core.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundException
from app.repositories.state_repository import StateRepository
from app.repositories.primitive_repository import PrimitiveRepository
from app.schemas.inventory import (
    InventoryCreate,
    InventoryMerged,
    InventoryRead,
    InventoryAdjustment,
)

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(
        self,
        db: Session,
        primitive_repo: PrimitiveRepository,
    ) -> None:
        self._state = StateRepository(db)
        self._primitives = primitive_repo

    # ── Read ───────────────────────────────────────────────────────────────

    async def get_user_inventory(self, user_id: int) -> List[InventoryMerged]:
        """
        Merge flow: fetch all inventory rows for user, then enrich with
        live manifest data from makestack-core in a single concurrent batch.
        """
        rows = self._state.get_inventory_for_user(user_id)
        if not rows:
            return []

        paths = [row.core_path for row in rows]
        manifests = await self._primitives.get_many(paths)
        manifest_map = {m.slug: m for m in manifests}
        # Also index by full path for direct lookup
        manifest_by_path: dict = {}
        for m in manifests:
            # core_path format: "tools/swivel-knife/manifest.json"
            # slug from manifest: "swivel-knife"
            manifest_by_path[m.slug] = m

        result = []
        for row in rows:
            # Extract slug from path: "tools/swivel-knife/manifest.json" → "swivel-knife"
            parts = row.core_path.rstrip("/manifest.json").split("/")
            slug = parts[-1] if parts else ""
            manifest = manifest_by_path.get(slug)

            merged = InventoryMerged(
                id=row.id,
                user_id=row.user_id,
                core_path=row.core_path,
                commit_hash=row.commit_hash,
                primitive_type=row.primitive_type,
                quantity=row.quantity,
                unit=row.unit,
                reorder_point=row.reorder_point,
                storage_location=row.storage_location,
                notes=row.notes,
                last_updated=row.last_updated,
                name=manifest.name if manifest else None,
                slug=manifest.slug if manifest else None,
                description=manifest.description if manifest else None,
                tags=manifest.tags if manifest else [],
                manifest=manifest.model_dump() if manifest else None,
            )
            result.append(merged)
        return result

    async def get_item(self, user_id: int, inventory_id: int) -> InventoryMerged:
        row = self._state.get_by_id(inventory_id)
        if not row or row.user_id != user_id:
            raise EntityNotFoundException(entity_type="Inventory", entity_id=str(inventory_id))
        manifest = await self._primitives.get(row.core_path)
        return InventoryMerged(
            **InventoryRead.model_validate(row).model_dump(),
            name=manifest.name,
            slug=manifest.slug,
            description=manifest.description,
            tags=manifest.tags,
            manifest=manifest.model_dump(),
        )

    async def get_low_stock(self, user_id: int) -> List[InventoryMerged]:
        rows = self._state.list_low_stock(user_id)
        if not rows:
            return []
        paths = [r.core_path for r in rows]
        manifests = await self._primitives.get_many(paths)
        # Same merge logic as get_user_inventory
        # (extract to _merge helper if this grows)
        return []  # TODO: implement merge for low stock

    # ── Write ──────────────────────────────────────────────────────────────

    async def add_to_inventory(self, data: InventoryCreate) -> InventoryRead:
        """
        Add a primitive to user inventory.
        Pins the commit hash from Core at time of entry.
        """
        if not data.commit_hash:
            data.commit_hash = await self._primitives.get_hash(data.core_path)
        row = self._state.create(data)
        return InventoryRead.model_validate(row)

    async def adjust_quantity(
        self,
        user_id: int,
        inventory_id: int,
        adjustment: InventoryAdjustment,
    ) -> InventoryRead:
        row = self._state.get_by_id(inventory_id)
        if not row or row.user_id != user_id:
            raise EntityNotFoundException(entity_type="Inventory", entity_id=str(inventory_id))

        updated = self._state.update_quantity(inventory_id, adjustment.quantity_delta)

        self._state.record_transaction(
            user_id=user_id,
            core_path=row.core_path,
            quantity=adjustment.quantity_delta,
            transaction_type=adjustment.transaction_type,
            adjustment_type=adjustment.adjustment_type,
            notes=adjustment.notes,
            performed_by=adjustment.performed_by,
        )
        return InventoryRead.model_validate(updated)

    def remove_from_inventory(self, user_id: int, inventory_id: int) -> None:
        row = self._state.get_by_id(inventory_id)
        if not row or row.user_id != user_id:
            raise EntityNotFoundException(entity_type="Inventory", entity_id=str(inventory_id))
        self._state.delete(inventory_id)
```

---

## Step E — Update `app/api/endpoints/inventory.py`

Rewrite the endpoint to use `InventoryService` with the new response shapes.
The endpoint is async because `InventoryService` methods are async (they call Core).

Key endpoints:
- `GET /inventory/` → `InventoryMerged` list for current user
- `GET /inventory/{id}` → single `InventoryMerged`
- `GET /inventory/low-stock` → items below reorder point
- `POST /inventory/` → `InventoryCreate` → `InventoryRead`
- `POST /inventory/{id}/adjust` → `InventoryAdjustment` → `InventoryRead`
- `DELETE /inventory/{id}` → 204

Inject `InventoryService` via a dependency that takes both `db` and
`primitive_repo`:

```python
from app.api.deps import get_primitive_repository, get_db
from app.services.inventory_service import InventoryService

def get_inventory_service(
    db: Session = Depends(get_db),
    primitive_repo: PrimitiveRepository = Depends(get_primitive_repository),
) -> InventoryService:
    return InventoryService(db=db, primitive_repo=primitive_repo)
```

---

## Test Gate

```bash
python -m pytest tests/services/test_inventory_service.py -v
python -m pytest tests/api/endpoints/test_inventory.py -v
python -m pytest -m "not integration" -q
```
