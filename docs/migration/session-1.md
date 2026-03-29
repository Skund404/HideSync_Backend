# Session 1 — Foundation

**Goal:** Wire in the makestack-core integration layer:
`MakestackClient`, `PrimitiveRepository`, primitive Pydantic schemas,
and the `MakestackUnavailableException`. No endpoints yet — session 1 is
infrastructure only.

**Prerequisites:** Session 0 complete. All four test-gate commands pass.

**Test gate:**
```bash
python -m pytest tests/test_foundation.py -v
python -m pytest -m "not integration" -q   # zero failures
```

---

## Step A — Add `MakestackUnavailableException` to exceptions

Edit `app/core/exceptions.py`. Add after the existing exception classes:

```python
class MakestackUnavailableException(HideSyncException):
    """Raised when makestack-core is unreachable or returns 503."""

    def __init__(self, detail: str = "makestack-core is unavailable"):
        super().__init__(
            message=detail,
            error_code="MAKESTACK_UNAVAILABLE",
            status_code=503,
        )
```

---

## Step B — Create `app/core/makestack_client.py`

```python
"""
Async HTTP client for makestack-core.

This is the only file in the Python backend that is allowed to make
HTTP calls to makestack-core. All other code goes through PrimitiveRepository.
"""

import asyncio
import logging
from typing import Optional

import httpx

from app.core.config import settings
from app.core.exceptions import (
    EntityNotFoundException,
    ValidationException,
    BusinessRuleException,
    MakestackUnavailableException,
)

logger = logging.getLogger(__name__)


class MakestackClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self._base_url = (base_url or settings.MAKESTACK_CORE_URL).rstrip("/")
        headers: dict = {"Content-Type": "application/json"}
        key = api_key or settings.MAKESTACK_API_KEY
        if key:
            headers["Authorization"] = f"Bearer {key}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=10.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Map Core HTTP errors to HideSync domain exceptions."""
        if response.status_code == 404:
            raise EntityNotFoundException(
                entity_type="primitive",
                entity_id=str(response.url),
            )
        if response.status_code == 400:
            raise ValidationException(
                message=response.text,
                errors={"detail": response.text},
            )
        if response.status_code == 409:
            raise BusinessRuleException(
                message=f"Slug conflict: {response.text}",
                rule="unique_slug",
            )
        if response.status_code == 503:
            raise MakestackUnavailableException(
                detail=f"makestack-core returned 503: {response.text}"
            )
        response.raise_for_status()

    async def _get(self, path: str, **params) -> httpx.Response:
        try:
            response = await self._client.get(path, params={k: v for k, v in params.items() if v is not None})
            self._raise_for_status(response)
            return response
        except httpx.RequestError as exc:
            raise MakestackUnavailableException(detail=str(exc)) from exc

    async def _post(self, path: str, json: dict) -> httpx.Response:
        try:
            response = await self._client.post(path, json=json)
            self._raise_for_status(response)
            return response
        except httpx.RequestError as exc:
            raise MakestackUnavailableException(detail=str(exc)) from exc

    async def _put(self, path: str, json: dict) -> httpx.Response:
        try:
            response = await self._client.put(path, json=json)
            self._raise_for_status(response)
            return response
        except httpx.RequestError as exc:
            raise MakestackUnavailableException(detail=str(exc)) from exc

    async def _delete(self, path: str) -> httpx.Response:
        try:
            response = await self._client.delete(path)
            self._raise_for_status(response)
            return response
        except httpx.RequestError as exc:
            raise MakestackUnavailableException(detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_primitives(
        self,
        type: Optional[str] = None,
        root: Optional[str] = None,
    ) -> list[dict]:
        """List all primitives, optionally filtered by type and/or root."""
        response = await self._get("/api/primitives", type=type, root=root)
        return response.json()

    async def get_primitive(
        self,
        path: str,
        at: Optional[str] = None,
    ) -> dict:
        """Get a single primitive by manifest path. Optionally pin to commit hash."""
        response = await self._get(f"/api/primitives/{path}/manifest.json", at=at)
        return response.json()

    async def get_primitive_hash(self, path: str) -> str:
        """Return the commit hash of the last modification to this primitive."""
        response = await self._get(f"/api/primitives/{path}/manifest.json/hash")
        return response.json()["commit_hash"]

    async def get_primitive_history(
        self,
        path: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Return paginated commit history for a primitive."""
        response = await self._get(
            f"/api/primitives/{path}/manifest.json/history",
            limit=limit,
            offset=offset,
        )
        return response.json()

    async def get_primitive_diff(
        self,
        path: str,
        from_hash: Optional[str] = None,
        to_hash: Optional[str] = None,
    ) -> list[dict]:
        """Return field-level diff between two commits."""
        response = await self._get(
            f"/api/primitives/{path}/manifest.json/diff",
            **{"from": from_hash, "to": to_hash},
        )
        return response.json()

    async def create_primitive(self, data: dict) -> dict:
        """Create a new primitive. Returns full manifest including generated fields."""
        response = await self._post("/api/primitives", json=data)
        return response.json()

    async def update_primitive(self, path: str, data: dict) -> dict:
        """Replace a primitive manifest. Returns updated manifest."""
        response = await self._put(f"/api/primitives/{path}/manifest.json", json=data)
        return response.json()

    async def delete_primitive(self, path: str) -> None:
        """Delete a primitive. Commits removal to the data repo."""
        await self._delete(f"/api/primitives/{path}/manifest.json")

    async def search_primitives(self, q: str) -> list[dict]:
        """Full-text search across all primitives using Core FTS5."""
        response = await self._get("/api/search", q=q)
        return response.json()

    async def get_relationships(self, path: str) -> dict:
        """Return incoming and outgoing relationships for a primitive."""
        response = await self._get(f"/api/relationships/{path}/manifest.json")
        return response.json()

    async def list_roots(self) -> list[dict]:
        """Return all configured federated roots."""
        response = await self._get("/api/roots")
        return response.json()["roots"]

    async def health(self) -> bool:
        """Return True if makestack-core is reachable."""
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except httpx.RequestError:
            return False

    async def get_many(self, paths: list[str]) -> list[dict]:
        """
        Fetch multiple primitives concurrently.
        Missing paths (404) are logged and excluded from results.
        """
        tasks = [self.get_primitive(path) for path in paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = []
        for path, result in zip(paths, results):
            if isinstance(result, Exception):
                logger.warning("Failed to fetch primitive %s: %s", path, result)
            else:
                out.append(result)
        return out

    async def close(self) -> None:
        await self._client.aclose()
```

---

## Step C — Create `app/schemas/primitives.py`

```python
"""
Pydantic schemas for makestack-core primitives.

This is the only schema file for physical domain data. All six primitive
types are defined here. Legacy domain schemas (tool.py, material.py, etc.)
have been deleted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    type: str
    target: str


class Step(BaseModel):
    order: int
    description: str


class BasePrimitive(BaseModel):
    id: str
    type: str
    name: str
    slug: str
    description: Optional[str] = None
    tags: List[str] = []
    created: datetime
    modified: datetime
    relationships: List[Relationship] = []

    class Config:
        from_attributes = True


class ToolPrimitive(BasePrimitive):
    type: Literal["tool"]


class MaterialPrimitive(BasePrimitive):
    type: Literal["material"]


class TechniquePrimitive(BasePrimitive):
    type: Literal["technique"]
    steps: List[Step] = []


class WorkflowPrimitive(BasePrimitive):
    type: Literal["workflow"]
    steps: List[Step] = []


class ProjectPrimitive(BasePrimitive):
    type: Literal["project"]
    parent_project: Optional[str] = None


class EventPrimitive(BasePrimitive):
    type: Literal["event"]


PrimitiveUnion = Annotated[
    Union[
        ToolPrimitive,
        MaterialPrimitive,
        TechniquePrimitive,
        WorkflowPrimitive,
        ProjectPrimitive,
        EventPrimitive,
    ],
    Field(discriminator="type"),
]


# Request bodies for create/update (id, slug, created, modified are set by Core)
class PrimitiveCreate(BaseModel):
    type: str
    name: str
    description: Optional[str] = None
    tags: List[str] = []
    relationships: List[Relationship] = []
    steps: Optional[List[Step]] = None
    parent_project: Optional[str] = None


class PrimitiveUpdate(PrimitiveCreate):
    id: str
    slug: str
```

---

## Step D — Create `app/repositories/primitive_repository.py`

```python
"""
PrimitiveRepository — wraps MakestackClient with typed responses.

This is the only repository allowed to call MakestackClient.
Services call this repository; they never call MakestackClient directly.
"""

from typing import Optional

from app.core.makestack_client import MakestackClient
from app.schemas.primitives import BasePrimitive, PrimitiveUnion
from pydantic import TypeAdapter

_adapter = TypeAdapter(PrimitiveUnion)


def _parse(data: dict) -> BasePrimitive:
    return _adapter.validate_python(data)


class PrimitiveRepository:
    def __init__(self, client: MakestackClient) -> None:
        self._client = client

    async def list(
        self,
        type: Optional[str] = None,
        root: Optional[str] = None,
    ) -> list[BasePrimitive]:
        items = await self._client.get_primitives(type=type, root=root)
        return [_parse(i) for i in items]

    async def get(self, path: str, at: Optional[str] = None) -> BasePrimitive:
        data = await self._client.get_primitive(path, at=at)
        return _parse(data)

    async def create(self, data: dict) -> BasePrimitive:
        result = await self._client.create_primitive(data)
        return _parse(result)

    async def update(self, path: str, data: dict) -> BasePrimitive:
        result = await self._client.update_primitive(path, data)
        return _parse(result)

    async def delete(self, path: str) -> None:
        await self._client.delete_primitive(path)

    async def search(self, q: str) -> list[BasePrimitive]:
        items = await self._client.search_primitives(q)
        return [_parse(i) for i in items]

    async def get_many(self, paths: list[str]) -> list[BasePrimitive]:
        items = await self._client.get_many(paths)
        return [_parse(i) for i in items]

    async def get_hash(self, path: str) -> str:
        return await self._client.get_primitive_hash(path)
```

---

## Step E — Update `app/api/deps.py`

Add these dependency functions:

```python
from functools import lru_cache
from app.core.makestack_client import MakestackClient
from app.repositories.primitive_repository import PrimitiveRepository


@lru_cache(maxsize=1)
def get_makestack_client() -> MakestackClient:
    """Return a singleton MakestackClient instance."""
    return MakestackClient()


def get_primitive_repository(
    client: MakestackClient = Depends(get_makestack_client),
) -> PrimitiveRepository:
    return PrimitiveRepository(client)
```

---

## Step F — Add `httpx` to `requirements.txt`

Add: `httpx>=0.27.0`

---

## Step G — Write `tests/test_foundation.py`

```python
"""Unit tests for MakestackClient and PrimitiveRepository (mocked)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.makestack_client import MakestackClient
from app.repositories.primitive_repository import PrimitiveRepository
from app.core.exceptions import EntityNotFoundException, MakestackUnavailableException


TOOL_MANIFEST = {
    "id": "abc123",
    "type": "tool",
    "name": "Swivel Knife",
    "slug": "swivel-knife",
    "description": "For carving leather.",
    "tags": ["carving"],
    "created": "2026-01-01T00:00:00Z",
    "modified": "2026-01-01T00:00:00Z",
    "relationships": [],
}


@pytest.fixture
def mock_http_client():
    with patch("app.core.makestack_client.httpx.AsyncClient") as mock:
        yield mock


class TestMakestackClientErrorMapping:
    async def test_404_raises_entity_not_found(self):
        client = MakestackClient()
        response = MagicMock()
        response.status_code = 404
        response.url = "http://localhost:8420/api/primitives/tools/x/manifest.json"
        with pytest.raises(EntityNotFoundException):
            client._raise_for_status(response)

    async def test_503_raises_unavailable(self):
        client = MakestackClient()
        response = MagicMock()
        response.status_code = 503
        response.text = "git repo not found"
        with pytest.raises(MakestackUnavailableException):
            client._raise_for_status(response)


class TestPrimitiveRepository:
    @pytest.fixture
    def repo(self):
        client = AsyncMock(spec=MakestackClient)
        client.get_primitives = AsyncMock(return_value=[TOOL_MANIFEST])
        client.get_primitive = AsyncMock(return_value=TOOL_MANIFEST)
        client.create_primitive = AsyncMock(return_value=TOOL_MANIFEST)
        client.delete_primitive = AsyncMock(return_value=None)
        return PrimitiveRepository(client)

    @pytest.mark.asyncio
    async def test_list_returns_parsed_primitives(self, repo):
        result = await repo.list(type="tool")
        assert len(result) == 1
        assert result[0].name == "Swivel Knife"
        assert result[0].type == "tool"

    @pytest.mark.asyncio
    async def test_get_returns_parsed_primitive(self, repo):
        result = await repo.get("tools/swivel-knife")
        assert result.slug == "swivel-knife"

    @pytest.mark.asyncio
    async def test_create_returns_parsed_primitive(self, repo):
        result = await repo.create({"type": "tool", "name": "Swivel Knife"})
        assert result.id == "abc123"

    @pytest.mark.asyncio
    async def test_delete_calls_client(self, repo):
        await repo.delete("tools/swivel-knife")
        repo._client.delete_primitive.assert_called_once_with("tools/swivel-knife")
```

---

## Integration Tests (requires live makestack-core)

Create `tests/integration/test_makestack_integration.py`:

```python
"""
Integration tests — require a running makestack-core instance.
Run with: pytest -m integration
"""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
async def client():
    from app.core.makestack_client import MakestackClient
    c = MakestackClient()
    yield c
    await c.close()


@pytest.fixture
async def repo(client):
    from app.repositories.primitive_repository import PrimitiveRepository
    return PrimitiveRepository(client)


async def test_health(client):
    assert await client.health() is True


async def test_create_get_delete_tool(repo):
    created = await repo.create({
        "type": "tool",
        "name": "Integration Test Tool",
        "tags": ["test"],
    })
    path = f"tools/{created.slug}"
    try:
        fetched = await repo.get(path)
        assert fetched.name == "Integration Test Tool"
    finally:
        await repo.delete(path)


async def test_list_filters_by_type(repo):
    items = await repo.list(type="tool")
    assert all(i.type == "tool" for i in items)


async def test_search(repo):
    results = await repo.search("test")
    assert isinstance(results, list)
```

---

## Test Gate

```bash
# Unit tests (no live Core needed)
python -m pytest tests/test_foundation.py -v

# Full suite without integration tests
python -m pytest -m "not integration" -q

# Integration tests (requires live makestack-core at localhost:8420)
MAKESTACK_API_KEY=testkey python -m pytest -m integration -v
```
