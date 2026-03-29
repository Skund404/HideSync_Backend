# Session 12 — Auth / Users / Roles

**Goal:** Verify auth, user, and role domain. No changes expected.
Fix any import errors that surfaced from earlier sessions.

**Prerequisites:** Session 11 complete.

**Scope:**
```
app/db/models/    user.py, role.py, password_reset.py
app/repositories/ user_repository.py, role_repository.py,
                  password_reset_repository.py
app/services/     user_service.py, role_service.py
app/schemas/      user.py, token.py, role.py
app/api/endpoints/ auth.py, users.py, roles.py
app/core/         security.py
```

**Strategy:** Verify only. Make no changes unless there are import errors.

---

## Step A — Verify imports

```bash
python -c "from app.api.endpoints.auth import router; print('auth OK')"
python -c "from app.api.endpoints.users import router; print('users OK')"
python -c "from app.api.endpoints.roles import router; print('roles OK')"
python -c "from app.services.user_service import UserService; print('UserService OK')"
```

---

## Step B — Run auth-specific tests

```bash
python -m pytest tests/api/endpoints/test_auth.py -v
python -m pytest tests/services/test_user_service.py -v
```

---

## Step C — Verify token flow end-to-end

Start the app and confirm:
```bash
uvicorn app.main:app --reload &

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin@hidesync.com&password=admin" \
  -H "Content-Type: application/x-www-form-urlencoded"

# Should return access_token
```

---

## Common issues to look for

- `user.py` model may have a `role_id` FK or a roles relationship — fine.
- `user.py` may have had a `projects` relationship (to the deleted Project model).
  If so, remove it.
- `security.py` should have no domain model imports — verify.

---

## Test Gate

```bash
python -m pytest tests/ -k "auth or user or role" -v
python -m pytest -m "not integration" -q   # full suite, zero failures
```
