# Session 6 — Projects

**Goal:** Projects endpoint. Definitions live in makestack-core. User-owned
project schedules (for recurring projects) live in the Python DB if needed.

**Prerequisites:** Sessions 2–5 complete.

**Scope:**
- `app/api/endpoints/projects.py` (new)
- `app/db/models/project_schedule.py` (new, only if recurring is in scope)
- `app/api/api.py` (register router)

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_projects.py -v
```

---

## Step A — Key design decisions

### ProjectTemplate → tag convention
`ProjectTemplate` is gone as a separate model. Templates are projects tagged
with `"template"`:
```json
{ "type": "project", "tags": ["template", "bifold-wallet"] }
```
Filter them: `GET /api/v1/projects/?tag=template`

### RecurringProject → ProjectSchedule (Python DB)
If recurring project scheduling is in scope now, create a minimal model.
If it can be deferred, skip it and add a TODO. Do not create half-finished
models — either implement fully or skip entirely.

---

## Step B — Create `app/api/endpoints/projects.py`

```python
"""
Projects endpoint.

Project *definitions* live in makestack-core.
Project *schedules* (recurring run config) live in the Python DB.
ProjectTemplates are just projects tagged with "template".
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_primitive_repository
from app.repositories.primitive_repository import PrimitiveRepository
from app.schemas.primitives import ProjectPrimitive, PrimitiveCreate, PrimitiveUpdate

router = APIRouter()


@router.get("/", response_model=list[ProjectPrimitive])
async def list_projects(
    root: Optional[str] = Query(None),
    tag: Optional[str] = Query(None, description="Filter by tag (e.g. 'template')"),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    projects = await repo.list(type="project", root=root)
    if tag:
        projects = [p for p in projects if tag in p.tags]
    return projects


@router.get("/search", response_model=list[ProjectPrimitive])
async def search_projects(
    q: str = Query(..., min_length=1),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    results = await repo.search(q)
    return [r for r in results if r.type == "project"]


@router.get("/{path:path}", response_model=ProjectPrimitive)
async def get_project(
    path: str,
    at: Optional[str] = Query(None),
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.get(path, at=at)


@router.post("/", response_model=ProjectPrimitive, status_code=201)
async def create_project(
    body: PrimitiveCreate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    data = body.model_dump(exclude_none=True)
    data["type"] = "project"
    return await repo.create(data)


@router.put("/{path:path}", response_model=ProjectPrimitive)
async def update_project(
    path: str,
    body: PrimitiveUpdate,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    return await repo.update(path, body.model_dump(exclude_none=True))


@router.delete("/{path:path}", status_code=204)
async def delete_project(
    path: str,
    repo: PrimitiveRepository = Depends(get_primitive_repository),
):
    await repo.delete(path)
```

---

## Step C — `app/db/models/project_schedule.py` (if recurring needed)

```python
"""
User-owned project schedule for recurring projects.

If a user wants to run a project on a schedule (e.g. "make this wallet
every 2 weeks"), store the schedule here. The project definition itself
is in makestack-core at core_path.
"""

from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from app.db.models.base import AbstractBase


class ProjectSchedule(AbstractBase):
    __tablename__ = "project_schedules"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    core_path = Column(String, nullable=False)       # project definition path in Core
    commit_hash = Column(String, nullable=False)     # pinned definition version
    recurrence_rule = Column(String, nullable=False) # iCal RRULE string
    next_run = Column(DateTime, nullable=True)
    last_run = Column(DateTime, nullable=True)
    active = Column(Integer, default=1)              # 0 = paused
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

## Step D — Register in `app/api/api.py`

```python
from app.api.endpoints import projects
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
```

---

## Test Gate

```bash
python -m pytest tests/api/endpoints/test_projects.py -v
python -m pytest -m "not integration" -q
```
