# Session 11 — Customers

**Goal:** Clean customer domain of deleted domain references.
Also fix the misnamed model file `customer_communication_service.py`.

**Prerequisites:** Session 10 complete.

**Scope:**
```
app/db/models/    customer.py,
                  customer_communication_service.py → rename to customer_communication.py
                  communication.py
app/repositories/ customer_repository.py, customer_communication_repository.py,
                  communication_repository.py
app/services/     customer_service.py, customer_communication_service.py
app/schemas/      customer.py
app/api/endpoints/ customers.py
```

**Test gate:**
```bash
python -m pytest tests/api/endpoints/test_customers.py -v
python -m pytest -m "not integration" -q
```

---

## Step A — Rename the misnamed model file

`app/db/models/customer_communication_service.py` is a model file with a
service-like name. This is a legacy naming error.

1. Read the file to confirm it contains model class definitions (not a service).
2. Rename to `app/db/models/customer_communication.py`.
3. Update all imports referencing the old filename throughout the codebase.

```bash
# Find all imports to update
grep -r "customer_communication_service" app/ --include="*.py"
```

---

## Step B — `app/db/models/customer.py`

Audit for:
- Any relationship to `Project` (customer's projects). Project is now a
  Core primitive. Remove the FK/relationship. If a customer ↔ project link
  is needed, store it as:
  ```python
  # In a new user_project_link table, or as a JSON list
  # Not a foreign key to a deleted projects table
  ```
  Defer this if not actively used.

- Any relationship to `Sale` — this is fine, Sale is still in Python DB.

- Any relationship to `Product` — fine, Product is still in Python DB.

---

## Step C — Communication models

`communication.py` and `customer_communication.py` (newly renamed) are
likely clean. Audit for any deleted model imports.

`CommunicationChannel` and `CommunicationType` enums were kept in `enums.py`
in session 0 — these should still work.

---

## Step D — Services, Repositories, Schemas, Endpoints

Standard cleanup:
1. Remove imports from deleted modules.
2. Remove methods querying deleted tables.
3. Update schemas to remove fields referencing deleted types.

---

## Test Gate

```bash
python -m pytest -m "not integration" -q
```
