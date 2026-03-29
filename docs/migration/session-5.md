# Session 5 — Workflows

**Goal:** Workflows endpoint for primitive definitions + a minimal SQLAlchemy
model for user-owned workflow execution state.

**Prerequisites:** Sessions 2–4 complete.

**Scope:**
- `app/api/endpoints/workflows.py` (new)
- `app/db/models/workflow_execution.py` (new)
- `app/repositories/workflow_execution_repository.py` (new)
- `app/api/api.py` (register router)

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_workflows.py -v
```

---

## Step A — Create `app/api/endpoints/workflows.py`

```python
"""
Workflows endpoint.

Workflow *definitions* (steps, techniques used) live in makestack-core.
Workflow *execution state* (which step a user is on, run status)
lives in the Python DB — see WorkflowExecution model.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_primitive_repository, get_db
from app.repositories.primitive_repository import PrimitiveRepository
from app.repositories.workflow_execution_repository import WorkflowExecutionRepository
from app.schemas.primitives import WorkflowPrimitive, PrimitiveCreate, PrimitiveUpdate
from app.schemas.workflow_execution import (
    WorkflowExecutionCreate,
    WorkflowExecutionRead,
    WorkflowExecutionUpdate,
)
from sqlalchemy.orm import Session

router = APIRouter()


# ── Workflow definitions (via makestack-core) ──────────────────────────────

@router.get("/", response_model=list[WorkflowPrimitive])
async def list_workflows(
    root: Optional[str] = Query(None),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.list(type="workflow", root=root)


@router.get("/search", response_model=list[WorkflowPrimitive])
async def search_workflows(
    q: str = Query(..., min_length=1),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    results = await repo.search(q)
    return [r for r in results if r.type == "workflow"]


@router.get("/{path:path}/definition", response_model=WorkflowPrimitive)
async def get_workflow_definition(
    path: str,
    at: Optional[str] = Query(None),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.get(path, at=at)


@router.post("/", response_model=WorkflowPrimitive, status_code=201)
async def create_workflow(
    body: PrimitiveCreate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    data = body.model_dump(exclude_none=True)
    data["type"] = "workflow"
    return await repo.create(data)


@router.put("/{path:path}/definition", response_model=WorkflowPrimitive)
async def update_workflow(
    path: str,
    body: PrimitiveUpdate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.update(path, body.model_dump(exclude_none=True))


@router.delete("/{path:path}/definition", status_code=204)
async def delete_workflow(
    path: str,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    await repo.delete(path)


# ── Workflow execution state (via Python DB) ────────────────────────────────

@router.post("/{path:path}/executions", response_model=WorkflowExecutionRead, status_code=201)
async def start_execution(
    path: str,
    body: WorkflowExecutionCreate,
    db: Session = Depends(get_db),
):
    repo = WorkflowExecutionRepository(db)
    return repo.create(core_path=path, user_id=body.user_id, commit_hash=body.commit_hash)


@router.get("/{path:path}/executions/{execution_id}", response_model=WorkflowExecutionRead)
async def get_execution(
    path: str,
    execution_id: int,
    db: Session = Depends(get_db),
):
    repo = WorkflowExecutionRepository(db)
    return repo.get(execution_id)


@router.patch("/{path:path}/executions/{execution_id}", response_model=WorkflowExecutionRead)
async def update_execution(
    path: str,
    execution_id: int,
    body: WorkflowExecutionUpdate,
    db: Session = Depends(get_db),
):
    repo = WorkflowExecutionRepository(db)
    return repo.update(execution_id, body)
```

---

## Step B — Create `app/db/models/workflow_execution.py`

```python
"""User-owned workflow execution state."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.db.models.base import AbstractBase


class WorkflowExecution(AbstractBase):
    __tablename__ = "workflow_executions"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    core_path = Column(String, nullable=False)        # e.g. "workflows/wet-moulding"
    commit_hash = Column(String, nullable=False)      # pinned definition version
    current_step = Column(Integer, default=0)
    status = Column(String, default="in_progress")   # in_progress | paused | completed | abandoned
    started_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(String, nullable=True)
```

Add to `app/db/models/__init__.py`:
```python
from app.db.models.workflow_execution import WorkflowExecution
```

---

## Step C — Create `app/schemas/workflow_execution.py`

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class WorkflowExecutionCreate(BaseModel):
    user_id: int
    commit_hash: str


class WorkflowExecutionUpdate(BaseModel):
    current_step: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class WorkflowExecutionRead(BaseModel):
    id: int
    user_id: int
    core_path: str
    commit_hash: str
    current_step: int
    status: str
    started_at: datetime
    updated_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True
```

---

## Step D — Create `app/repositories/workflow_execution_repository.py`

```python
from sqlalchemy.orm import Session
from app.db.models.workflow_execution import WorkflowExecution
from app.schemas.workflow_execution import WorkflowExecutionUpdate


class WorkflowExecutionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, core_path: str, user_id: int, commit_hash: str) -> WorkflowExecution:
        obj = WorkflowExecution(core_path=core_path, user_id=user_id, commit_hash=commit_hash)
        self._db.add(obj)
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def get(self, execution_id: int) -> WorkflowExecution:
        from app.core.exceptions import EntityNotFoundException
        obj = self._db.get(WorkflowExecution, execution_id)
        if not obj:
            raise EntityNotFoundException(entity_type="WorkflowExecution", entity_id=str(execution_id))
        return obj

    def update(self, execution_id: int, data: WorkflowExecutionUpdate) -> WorkflowExecution:
        obj = self.get(execution_id)
        for field, value in data.model_dump(exclude_none=True).items():
            setattr(obj, field, value)
        self._db.commit()
        self._db.refresh(obj)
        return obj

    def list_for_user(self, user_id: int) -> list[WorkflowExecution]:
        return self._db.query(WorkflowExecution).filter_by(user_id=user_id).all()
```

---

## Step E — Register in `app/api/api.py`

```python
from app.api.endpoints import workflows
api_router.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
```

---

## Test Gate

```bash
python -m pytest tests/api/endpoints/test_workflows.py -v
python -m pytest -m "not integration" -q
```
