# Session 4 — Techniques (Patterns)

**Goal:** Techniques endpoint. The old `Pattern` concept is renamed `technique`
in makestack-core. A technique includes an ordered `steps` list.

**Prerequisites:** Session 3 complete.

**Scope:** `app/api/endpoints/techniques.py` only.
Do not recreate `patterns.py` — it was deleted in session 0.

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_techniques.py -v
```

---

## Step A — Create `app/api/endpoints/techniques.py`

```python
"""
Techniques endpoint — serves technique primitives from makestack-core.

The old /patterns endpoint is gone. Patterns are now techniques.
A legacy redirect is provided for any client still calling /patterns.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse

from app.api.deps import get_primitive_repository
from app.repositories.primitive_repository import PrimitiveRepository
from app.schemas.primitives import TechniquePrimitive, PrimitiveCreate, PrimitiveUpdate

router = APIRouter()


@router.get("/", response_model=list[TechniquePrimitive])
async def list_techniques(
    root: Optional[str] = Query(None),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.list(type="technique", root=root)


@router.get("/search", response_model=list[TechniquePrimitive])
async def search_techniques(
    q: str = Query(..., min_length=1),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    results = await repo.search(q)
    return [r for r in results if r.type == "technique"]


@router.get("/{path:path}", response_model=TechniquePrimitive)
async def get_technique(
    path: str,
    at: Optional[str] = Query(None),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.get(path, at=at)


@router.post("/", response_model=TechniquePrimitive, status_code=201)
async def create_technique(
    body: PrimitiveCreate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    data = body.model_dump(exclude_none=True)
    data["type"] = "technique"
    return await repo.create(data)


@router.put("/{path:path}", response_model=TechniquePrimitive)
async def update_technique(
    path: str,
    body: PrimitiveUpdate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.update(path, body.model_dump(exclude_none=True))


@router.delete("/{path:path}", status_code=204)
async def delete_technique(
    path: str,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    await repo.delete(path)
```

---

## Step B — Legacy /patterns redirect

Add a separate mini-router for the old `/patterns` prefix.
Register it in `api.py` alongside techniques:

```python
# In app/api/endpoints/techniques.py — add at the bottom:

patterns_redirect_router = APIRouter()

@patterns_redirect_router.get("/{path:path}")
async def legacy_pattern_redirect(path: str):
    """301 redirect from old /patterns prefix to /techniques."""
    return RedirectResponse(url=f"/api/v1/techniques/{path}", status_code=301)
```

In `app/api/api.py`:
```python
from app.api.endpoints.techniques import router as techniques_router
from app.api.endpoints.techniques import patterns_redirect_router

api_router.include_router(techniques_router, prefix="/techniques", tags=["Techniques"])
api_router.include_router(patterns_redirect_router, prefix="/patterns", tags=["Patterns (deprecated)"])
```

---

## Step C — Write `tests/api/endpoints/test_techniques.py`

Same structure as `test_tools.py`. Use `TechniquePrimitive` with `type="technique"`
and a `steps` list. Test all 6 endpoints plus the legacy redirect.

---

## Test Gate

```bash
python -m pytest tests/api/endpoints/test_techniques.py -v
python -m pytest -m "not integration" -q
```
