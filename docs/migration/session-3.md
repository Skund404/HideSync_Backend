# Session 3 — Materials

**Goal:** Materials endpoint backed by makestack-core.

All legacy material sub-types (leather, hardware, supplies, wood) are gone.
Variation is expressed as tags on the manifest: `["leather", "vegetable-tan"]`,
`["hardware", "brass", "buckle"]`, etc.

**Prerequisites:** Session 2 complete. All tools tests passing.

**Scope:** `app/api/endpoints/materials.py` only.
Do not touch any other file except `app/api/api.py`.

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_materials.py -v
```

---

## Step A — Create `app/api/endpoints/materials.py`

```python
"""
Materials endpoint — serves material primitives from makestack-core.

All legacy material sub-types (leather, hardware, supplies, wood)
are now just Material primitives with descriptive tags.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_primitive_repository
from app.repositories.primitive_repository import PrimitiveRepository
from app.schemas.primitives import MaterialPrimitive, PrimitiveCreate, PrimitiveUpdate

router = APIRouter()


@router.get("/", response_model=list[MaterialPrimitive])
async def list_materials(
    root: Optional[str] = Query(None),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.list(type="material", root=root)


@router.get("/search", response_model=list[MaterialPrimitive])
async def search_materials(
    q: str = Query(..., min_length=1),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    results = await repo.search(q)
    return [r for r in results if r.type == "material"]


@router.get("/{path:path}", response_model=MaterialPrimitive)
async def get_material(
    path: str,
    at: Optional[str] = Query(None),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.get(path, at=at)


@router.post("/", response_model=MaterialPrimitive, status_code=201)
async def create_material(
    body: PrimitiveCreate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    data = body.model_dump(exclude_none=True)
    data["type"] = "material"
    return await repo.create(data)


@router.put("/{path:path}", response_model=MaterialPrimitive)
async def update_material(
    path: str,
    body: PrimitiveUpdate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.update(path, body.model_dump(exclude_none=True))


@router.delete("/{path:path}", status_code=204)
async def delete_material(
    path: str,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    await repo.delete(path)
```

---

## Step B — Register in `app/api/api.py`

```python
from app.api.endpoints import materials
api_router.include_router(materials.router, prefix="/materials", tags=["Materials"])
```

---

## Step C — Write `tests/api/endpoints/test_materials.py`

Follow the same pattern as `test_tools.py`. Use `MaterialPrimitive` with
`type="material"` and tags like `["leather", "vegetable-tan"]`.

Test all 6 endpoints: list, search, get, create, update, delete.

---

## Note on Tag Conventions

There is no enforced schema for material tags. Conventions used in HideSync:

| Old sub-type | Recommended tags |
|---|---|
| Leather | `["leather"]` + tannage, animal, finish as additional tags |
| Hardware | `["hardware"]` + material, finish, hardware type |
| Supplies | `["supplies"]` + thread/dye/adhesive type |
| Wood | `["wood"]` + species, grain, finish |

These are conventions only — Core does not validate them.
Document them in `docs/tag-conventions.md` when establishing data.

---

## Test Gate

```bash
python -m pytest tests/api/endpoints/test_materials.py -v
python -m pytest -m "not integration" -q
```
