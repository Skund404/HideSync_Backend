# CLAUDE.md — HideSync Architectural Contract

Read this file in full at the start of every session.
Execution checklists live in `docs/migration/session-*.md`.

---

## Architecture

```
makestack-core  (Go — localhost:8420)
  └─ Physical domain: tools, materials, techniques, workflows, projects, events
  └─ JSON manifests in Git repos, SQLite read index, REST API

HideSync Backend  (Python / FastAPI — this repo)
  └─ Identity & auth: User, Role, PasswordReset
  └─ Personal state: Inventory (user_id + core_path + quantity)
  └─ Commerce: Sale, Purchase, Shipment, Refund, Product, PickingList
  └─ Relations: Customer, Supplier
  └─ Infrastructure: Storage, Tags, MediaAssets, Documentation
```

The Python backend holds **references** to makestack-core manifests via
`core_path` strings. It never stores physical domain data itself.

---

## The Six Primitives

| Primitive  | Replaces in HideSync                                   |
|------------|--------------------------------------------------------|
| `tool`     | Tool, ToolMaintenance, ToolCheckout                    |
| `material` | Material (leather, hardware, supplies, wood)           |
| `technique`| Pattern                                                |
| `workflow` | Workflow, WorkflowStep, ProjectTemplate                |
| `project`  | Project, RecurringProject                              |
| `event`    | TimelineTask                                           |

All property variation (leather type, hardware finish, etc.) becomes
`tags` or free-form fields on the manifest. No Python enum for it.

---

## Hard Constraints

1. **SQLAlchemy never holds physical domain data.**
   If a model describes a tool, material, technique, workflow, project,
   or event — delete it, do not migrate it.

2. **httpx belongs only in `MakestackClient`.**
   Call chain: Router → Service → PrimitiveRepository → MakestackClient.
   Routers and services never import httpx or call makestack-core directly.

3. **SQLCipher is gone entirely.**
   No `pragma key`, no `pysqlcipher3`, no key files.
   Use `sqlite:///./hidesync.db` (dev) or `postgresql://` (prod).

4. **One schema file for the physical domain: `app/schemas/primitives.py`.**
   `BasePrimitive` + six typed subclasses + `PrimitiveUnion`.
   All legacy domain schemas (tool.py, material.py, etc.) are deleted.

5. **No shim layers.**
   No `*Adapter`, `*Compat`, `*Bridge`, `*Wrapper`.
   Manifest JSON is the data shape — serve it directly.

6. **No partial deletes.**
   Files are deleted completely. Git history is the backup.

7. **One domain per session.**
   Do not touch files outside the declared scope even if broken.
   Document broken imports; fix them in their own session.

8. **Inventory stores references, not data.**
   `Inventory` model fields: `user_id`, `core_path`, `commit_hash`,
   `primitive_type`, `quantity`, `unit`, `storage_location`, `notes`.
   Name, description, supplier — fetched live from makestack-core.

---

## Request Flow

```
# Physical domain (tools, materials, etc.)
Router → Service → PrimitiveRepository → MakestackClient → makestack-core

# User state (inventory, execution, schedules)
Router → Service → StateRepository (SQLAlchemy) → SQLite

# Inventory read (merge flow)
InventoryService:
  1. state_repo.get_inventory_for_user(user_id)   → List[Inventory rows]
  2. primitive_repo.get_many(core_paths)           → List[manifest dicts]
  3. merge: attach quantity/unit onto each manifest
  4. return merged list
```

---

## File Layout After Migration

```
app/
├── api/
│   └── endpoints/
│       ├── auth.py, users.py, roles.py           # unchanged
│       ├── tools.py, materials.py                # NEW (primitives via Core)
│       ├── techniques.py, workflows.py           # NEW
│       ├── projects.py                           # NEW
│       ├── inventory.py                          # REWRITTEN
│       ├── sales.py, purchases.py, products.py   # cleaned
│       ├── suppliers.py, customers.py            # cleaned
│       └── storage.py, tags.py, ...              # cleaned
├── core/
│   ├── config.py             # simplified, + MAKESTACK_CORE_URL/API_KEY
│   ├── exceptions.py         # + MakestackUnavailableException
│   ├── makestack_client.py   # NEW — async httpx
│   └── security.py           # unchanged
├── db/
│   └── models/
│       ├── base.py, user.py, role.py             # unchanged
│       ├── password_reset.py, settings.py        # unchanged
│       ├── enums.py                              # PRUNED (userDB enums only)
│       ├── inventory.py                          # REWRITTEN
│       ├── customer.py, supplier.py, ...         # cleaned (remove domain FKs)
│       ├── sales.py, purchase.py, ...            # cleaned
│       └── storage.py, tag.py, ...              # cleaned
├── repositories/
│   ├── base_repository.py                        # unchanged
│   ├── primitive_repository.py                   # NEW
│   ├── state_repository.py                       # NEW
│   ├── user_repository.py, role_repository.py    # unchanged
│   └── [commerce/supplier/customer repos]        # cleaned
├── schemas/
│   ├── primitives.py                             # NEW
│   ├── user.py, token.py, role.py                # unchanged
│   └── [commerce/supplier/customer schemas]      # cleaned
└── services/
    ├── makestack_service.py                      # NEW
    ├── inventory_service.py                      # REWRITTEN
    ├── user_service.py                           # unchanged
    └── [commerce/supplier/customer services]     # cleaned
```

---

## makestack-core API Reference

Full contract: `MAKESTACK_CORE_API.md`

```
Base URL : http://localhost:8420        (env: MAKESTACK_CORE_URL)
Auth     : Authorization: Bearer <key> (env: MAKESTACK_API_KEY)
Public   : GET /health only
```

| Method | Endpoint | Notes |
|--------|----------|-------|
| GET    | `/api/primitives` | `?type=tool` `?root=primary` |
| GET    | `/api/primitives/{path}/manifest.json` | `?at={hash}` pins version |
| GET    | `/api/primitives/{path}/manifest.json/hash` | last-modified hash |
| GET    | `/api/primitives/{path}/manifest.json/history` | paginated commits |
| GET    | `/api/primitives/{path}/manifest.json/diff` | field-level diff |
| POST   | `/api/primitives` | 201 + full manifest |
| PUT    | `/api/primitives/{path}/manifest.json` | |
| DELETE | `/api/primitives/{path}/manifest.json` | 204 |
| GET    | `/api/search?q=` | FTS5 across all primitives |
| GET    | `/api/roots` | federated roots |

Error mapping:
- `404` → `EntityNotFoundException`
- `400` → `ValidationException`
- `409` → `BusinessRuleException` (slug conflict)
- `503` → `MakestackUnavailableException`
- Network error → `MakestackUnavailableException`

---

## Session Index

| # | Name | Strategy | Doc |
|---|------|----------|-----|
| 0 | SQLCipher + Physical Domain Removal | Delete | [session-0.md](docs/migration/session-0.md) |
| 1 | Foundation | Create MakestackClient, PrimitiveRepository, schemas | [session-1.md](docs/migration/session-1.md) |
| 2 | Tools | First primitive vertical slice | [session-2.md](docs/migration/session-2.md) |
| 3 | Materials | Second atom | [session-3.md](docs/migration/session-3.md) |
| 4 | Techniques | Pattern → technique | [session-4.md](docs/migration/session-4.md) |
| 5 | Workflows | First molecule | [session-5.md](docs/migration/session-5.md) |
| 6 | Projects | Second molecule | [session-6.md](docs/migration/session-6.md) |
| 7 | Inventory | Schema rewrite + merge flow | [session-7.md](docs/migration/session-7.md) |
| 8 | Storage | Remove DMMS property refs | [session-8.md](docs/migration/session-8.md) |
| 9 | Commerce | Replace domain FKs with core_path | [session-9.md](docs/migration/session-9.md) |
| 10 | Suppliers | Cleanup | [session-10.md](docs/migration/session-10.md) |
| 11 | Customers | Cleanup | [session-11.md](docs/migration/session-11.md) |
| 12 | Auth / Users | Verify only | [session-12.md](docs/migration/session-12.md) |
| 13 | Infrastructure | Search fanout, factories, analytics | [session-13.md](docs/migration/session-13.md) |
| 14 | Final Audit | Grep checks, smoke test | [session-14.md](docs/migration/session-14.md) |

---

## Guardrails

If a proposed change would:
- Put tool/material/workflow data in a SQLAlchemy model → wrong, use core_path
- Put httpx calls in a router or service → wrong, move to MakestackClient
- Keep a deleted file renamed as `.bak` → wrong, delete completely
- Create a new schema mirroring an old SQLAlchemy model → wrong, use primitives.py
- Fix a broken import by recreating a deleted module → wrong, remove the import

Stop and re-read CLAUDE.md.
