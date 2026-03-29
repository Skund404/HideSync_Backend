# Session 2 — Tools

**Goal:** First primitive vertical slice. Create the `/tools` endpoint backed
entirely by makestack-core via `PrimitiveRepository`. No SQLAlchemy involved.

**Prerequisites:** Session 1 complete. Unit and integration tests passing.

**Scope:** `app/api/endpoints/tools.py` only. Do not touch any other file
except `app/api/api.py` (to register the router).

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_tools.py -v
```

---

## Step A — Create `app/api/endpoints/tools.py`

```python
"""
Tools endpoint — serves tool primitives from makestack-core.

All data comes from PrimitiveRepository. No SQLAlchemy.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_primitive_repository
from app.repositories.primitive_repository import PrimitiveRepository
from app.schemas.primitives import PrimitiveCreate, PrimitiveUpdate, ToolPrimitive

router = APIRouter()


@router.get("/", response_model=list[ToolPrimitive])
async def list_tools(
    root: Optional[str] = Query(None, description="Filter by federated root slug"),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.list(type="tool", root=root)


@router.get("/search", response_model=list[ToolPrimitive])
async def search_tools(
    q: str = Query(..., min_length=1),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    results = await repo.search(q)
    return [r for r in results if r.type == "tool"]


@router.get("/{path:path}", response_model=ToolPrimitive)
async def get_tool(
    path: str,
    at: Optional[str] = Query(None, description="Pin to commit hash"),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.get(path, at=at)


@router.post("/", response_model=ToolPrimitive, status_code=201)
async def create_tool(
    body: PrimitiveCreate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    data = body.model_dump(exclude_none=True)
    data["type"] = "tool"
    return await repo.create(data)


@router.put("/{path:path}", response_model=ToolPrimitive)
async def update_tool(
    path: str,
    body: PrimitiveUpdate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.update(path, body.model_dump(exclude_none=True))


@router.delete("/{path:path}", status_code=204)
async def delete_tool(
    path: str,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    await repo.delete(path)
```

---

## Step B — Register in `app/api/api.py`

Add to imports: `from app.api.endpoints import tools`

Add router:
```python
api_router.include_router(tools.router, prefix="/tools", tags=["Tools"])
```

---

## Step C — Write `tests/api/endpoints/test_tools.py`

```python
"""Unit tests for the /tools endpoint. PrimitiveRepository is mocked."""

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_primitive_repository
from app.schemas.primitives import ToolPrimitive
from datetime import datetime, timezone

TOOL = ToolPrimitive(
    id="abc123",
    type="tool",
    name="Swivel Knife",
    slug="swivel-knife",
    description="For carving.",
    tags=["carving"],
    created=datetime(2026, 1, 1, tzinfo=timezone.utc),
    modified=datetime(2026, 1, 1, tzinfo=timezone.utc),
    relationships=[],
)


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[TOOL])
    repo.get = AsyncMock(return_value=TOOL)
    repo.create = AsyncMock(return_value=TOOL)
    repo.update = AsyncMock(return_value=TOOL)
    repo.delete = AsyncMock(return_value=None)
    repo.search = AsyncMock(return_value=[TOOL])
    return repo


@pytest.fixture
def client(mock_repo):
    app.dependency_overrides[get_primitive_repository] = lambda: mock_repo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_list_tools(client):
    response = client.get("/api/v1/tools/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["slug"] == "swivel-knife"


def test_get_tool(client):
    response = client.get("/api/v1/tools/tools/swivel-knife")
    assert response.status_code == 200
    assert response.json()["name"] == "Swivel Knife"


def test_create_tool(client):
    response = client.post("/api/v1/tools/", json={
        "type": "tool",
        "name": "Wing Divider",
        "tags": ["marking"],
    })
    assert response.status_code == 201
    assert response.json()["type"] == "tool"


def test_update_tool(client):
    response = client.put("/api/v1/tools/tools/swivel-knife", json={
        "id": "abc123",
        "type": "tool",
        "name": "Swivel Knife",
        "slug": "swivel-knife",
        "tags": ["carving", "tooling"],
    })
    assert response.status_code == 200


def test_delete_tool(client):
    response = client.delete("/api/v1/tools/tools/swivel-knife")
    assert response.status_code == 204


def test_search_tools(client):
    response = client.get("/api/v1/tools/search?q=carving")
    assert response.status_code == 200
    assert response.json()[0]["type"] == "tool"
```

---

## Test Gate

All 6 tests must pass:
```bash
python -m pytest tests/api/endpoints/test_tools.py -v
```

No regressions in other tests:
```bash
python -m pytest -m "not integration" -q
```
