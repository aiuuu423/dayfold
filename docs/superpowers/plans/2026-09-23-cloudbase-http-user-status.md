# CloudBase HTTP User Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fail-closed CloudBase PostgreSQL HTTP status store and a self-read-only RLS policy for the Dayfold auth probe.

**Architecture:** FastAPI verifies the CloudBase AccessToken first, then passes the verified subject and original token to the selected `UserStatusStore`. The HTTP implementation queries `public.users` through PostgREST with the user token; PostgreSQL RLS remains the authorization boundary. The existing direct PostgreSQL implementation stays available behind an explicit backend setting.

**Tech Stack:** Python 3, FastAPI, httpx, pytest, CloudBase PostgreSQL/PostgREST, PostgreSQL RLS

---

### Task 1: Extend the status-store contract

**Files:**
- Modify: `apps/api/auth/user_status.py`
- Modify: `apps/api/tests/test_user_status.py`

- [ ] **Step 1: Write failing HTTP adapter tests**

Add tests using `httpx.MockTransport` that require:

```python
status = await store.get_status("fictional-user", "opaque-test-token")
```

Verify the request uses:

```text
Authorization: Bearer opaque-test-token
select=status
auth_subject=eq.fictional-user
deleted_at=is.null
limit=1
```

Cover successful `active`, empty result, `401`, `403`, `500`, network error,
malformed JSON, duplicate rows and an invalid status field.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run:

```bash
python3 -m pytest apps/api/tests/test_user_status.py -q
```

Expected: failure because `CloudBaseHttpUserStatusStore` does not exist and the
store contract does not accept an AccessToken.

- [ ] **Step 3: Implement the minimal adapter**

Add:

```python
class CloudBaseHttpUserStatusStore:
    def __init__(
        self,
        environment_id: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (
            f"https://{environment_id}.api.tcloudbasegateway.com"
        )
        self._transport = transport

    async def get_status(
        self,
        auth_subject: str,
        access_token: str,
    ) -> str | None:
        ...
```

Use a three-second timeout, `httpx.AsyncClient`, query parameters rather than
string concatenation, and normalize all provider details to
`UserStatusStoreUnavailable`.

Change the protocol and PostgreSQL implementation to:

```python
async def get_status(
    self,
    auth_subject: str,
    access_token: str,
) -> str | None:
```

The PostgreSQL implementation intentionally ignores `access_token`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest apps/api/tests/test_user_status.py -q
```

Expected: all status-store tests pass.

### Task 2: Select and call the HTTP backend

**Files:**
- Modify: `apps/api/main.py`
- Modify: `apps/api/tests/test_auth_probe.py`

- [ ] **Step 1: Write failing configuration and token-flow tests**

Cover:

```text
DAYFOLD_USER_STATUS_BACKEND=cloudbase_http
DAYFOLD_CLOUDBASE_ENV_ID=<environment>
```

and:

```text
DAYFOLD_USER_STATUS_BACKEND=postgres
DATABASE_URL=<connection string>
```

Verify unknown backends and missing required variables return no store. Update
the probe stub to assert both `auth_subject` and the original AccessToken.

- [ ] **Step 2: Run focused tests and confirm failure**

Run:

```bash
python3 -m pytest apps/api/tests/test_auth_probe.py -q
```

Expected: configuration-selection tests fail and the current probe omits the
AccessToken argument.

- [ ] **Step 3: Implement explicit backend selection**

Use:

```python
backend = os.getenv("DAYFOLD_USER_STATUS_BACKEND")
```

Rules:

```text
cloudbase_http + environment ID -> CloudBaseHttpUserStatusStore
postgres + DATABASE_URL -> PostgresUserStatusStore
unset backend + DATABASE_URL -> PostgresUserStatusStore for compatibility
anything else -> None
```

Pass the original token:

```python
user_status = await user_status_store.get_status(
    identity.auth_subject,
    token,
)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest apps/api/tests/test_auth_probe.py -q
```

Expected: all auth-probe tests pass.

### Task 3: Add the RLS migration

**Files:**
- Create: `infra/cloudbase/migrations/20260923_users_select_self.sql`

- [ ] **Step 1: Add idempotent SQL**

The migration must:

```sql
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.users FROM anon;
GRANT SELECT (status, deleted_at, auth_subject)
ON TABLE public.users TO authenticated;
DROP POLICY IF EXISTS users_select_self ON public.users;
CREATE POLICY users_select_self
ON public.users
FOR SELECT
TO authenticated
USING (
    auth_subject = (SELECT auth.uid())::text
    AND deleted_at IS NULL
);
```

Do not grant write privileges or access to unrelated columns.

- [ ] **Step 2: Apply in the CloudBase SQL editor**

Run the migration in the `dayfold-p1-probe` PostgreSQL SQL editor as an
administrator. Do not paste tokens or passwords.

- [ ] **Step 3: Verify policy metadata**

Query only policy metadata:

```sql
SELECT schemaname, tablename, policyname, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename = 'users'
ORDER BY policyname;
```

Expected: one `users_select_self` SELECT policy for `authenticated`, with
subject equality and `deleted_at IS NULL`.

### Task 4: Document deployment configuration

**Files:**
- Modify: `apps/api/README.md`
- Modify: `docs/p3/p3-auth-02-validation-progress.md`

- [ ] **Step 1: Update configuration documentation**

Document:

```text
DAYFOLD_USER_STATUS_BACKEND=cloudbase_http
DAYFOLD_CLOUDBASE_ENV_ID=<environment id>
```

State that no `DATABASE_URL`, database password or API Key is required for this
backend, and that the current user AccessToken is forwarded only to CloudBase.

- [ ] **Step 2: Record the architecture decision**

Update the validation progress from the obsolete external-database path to the
personal-plan HTTP API path, including the fail-closed semantics and remaining
online acceptance work.

### Task 5: Verify the complete change

**Files:**
- Verify all changed files

- [ ] **Step 1: Run the full API test suite**

Run:

```bash
python3 -m pytest apps/api/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax and whitespace checks**

Run:

```bash
python3 -m compileall -q apps/api
git diff --check
```

Expected: both commands exit successfully.

- [ ] **Step 3: Review the final diff**

Confirm:

- no Token, password, Cookie, API Key or connection string is present;
- no anonymous table access was granted;
- PostgreSQL direct mode still works;
- all provider failures remain fail closed.
