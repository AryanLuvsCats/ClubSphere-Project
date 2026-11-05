# ClubSphere — Security Hardening Extension Report

**Date:** 2026-11-05  
**Application:** ClubSphere University Club & Activity Lifecycle Management System  
**Stack:** React 19 + Vite (Frontend), FastAPI + SQLAlchemy (Backend), Neon PostgreSQL (Production DB)  

---

## 1. Architecture Inspection & Identified Security Weaknesses

1. **Rate Limiting Edge Case in Recovery**:
   - In `check_rate_limit()`, when `BlockedUntil` expired, if `WindowStartedAt + window_seconds` had not yet elapsed, `FailureCount` remained `>= max_attempts`, causing an immediate re-block for another `block_seconds` and preventing legitimate users from recovering after temporary restriction.
2. **CSRF Exposure on Cookie-Authenticated Endpoints**:
   - `/api/v1/auth/refresh` and `/api/v1/auth/logout` relied solely on origin checking, which could permit cross-site browser requests if Origin was omitted or spoofed via certain cross-site navigation contexts.
3. **Frontend Admin Route Exposure**:
   - `frontend/src/App.tsx` wrapped `<Route path="admin" element={<AdminDashboardPage />} />` only in `<RequireAuth>`. Any authenticated Student or Club Manager could access the admin frontend route.
4. **Missing Administrative User Management & Self-Role Escalation Controls**:
   - The platform lacked a dedicated administrative endpoint for reviewing and updating user roles. There was no explicit guard preventing administrators from changing their own roles or revoking existing sessions upon privilege modifications.
5. **Production Logging Information Leakage Risk**:
   - Standard logging had no redaction filter for Bearer tokens, passwords, cookies, or database connection strings.
6. **Vulnerable Dependency Identified via Audit**:
   - `pip-audit` detected a known vulnerability in `certifi 2026.7.22` (`PYSEC-2026-4320`). In `frontend/package.json`, `@types/three` was improperly listed in runtime `dependencies`.

---

## 2. Implementation Plan & Completed Changes

### Section 1: Login Rate Limiting & User Recovery
- **Legitimate User Recovery**: Updated `check_rate_limit()` in `backend/app/core/rate_limit.py`. When `row.BlockedUntil and row.BlockedUntil <= now`, the block period has expired; `FailureCount` is reset to 0, `BlockedUntil` cleared, and `WindowStartedAt` refreshed so legitimate users can immediately authenticate with their correct password.
- **Consistent Account Tracking**: Hashed scope and lowercased email ensure limits cannot be bypassed by altering letter casing.
- **Distributed Backend**: Backed by the PostgreSQL `AuthThrottle` table, operating consistently across multiple workers/nodes.

### Section 2: Secure Cookie Sessions & Anti-CSRF
- **Anti-CSRF Defense**: Enhanced `_assert_allowed_origin` in `backend/app/api/v1/auth.py`:
  - Rejects any request where `Sec-Fetch-Site` is `cross-site`.
  - Verifies `Origin` against the strict `CORS_ORIGINS` allowlist.
  - Verifies `Referer` prefix if `Origin` is omitted.
  - Applied to both `/api/v1/auth/refresh` and `/api/v1/auth/logout`.
- **Client Custom Headers**: Configured `frontend/src/services/apiClient.ts` to include `X-Requested-With: XMLHttpRequest` on cookie-bearing refresh requests, forcing CORS preflight checks for cross-origin callers.

### Section 3: Admin Page & API Protection
- **Frontend Route Protection**: Added `<RequireRoles allowedRoles={['Administrator', 'HOD', 'Faculty']}>` in `frontend/src/App.tsx`. Unauthorized users (Students, Club Managers) attempting to navigate to `/admin` are redirected to `/clubs`.
- **Administrative Role Management Endpoints**:
  - `GET /api/v1/admin/users`: Lists users with pagination and search; restricted to `Administrator`.
  - `PUT /api/v1/admin/users/{user_id}/role`: Updates a user's role; restricted to `Administrator`.
- **Privilege Escalation & Self-Modification Safeguards**:
  - Prohibits administrators from modifying their own role (`current_user.UserId == user_id`), preventing self-lockout or privilege tampering.
  - **Immediate Session Invalidation**: Upon role update, increments `target_user.TokenVersion` and marks all active `RefreshSession` rows as revoked. All outstanding JWT access tokens for that user immediately fail with HTTP 401, forcing re-authentication with new privileges.
  - Records an immutable audit log entry (`USER_ROLE_UPDATED`).

### Section 4: Production Debugging & Secure Logging
- **Sensitive Data Masking**: Created `backend/app/core/logging_filter.py` with `SensitiveDataFilter`. Redacts:
  - Bearer tokens (`Bearer [REDACTED]`)
  - Passwords in JSON/query/form data (`password: "[REDACTED]"`)
  - Refresh cookie values (`clubsphere_refresh=[REDACTED]`)
  - PostgreSQL database connection strings (`postgresql://[REDACTED]@...`)
- Wired `setup_secure_logging()` into `backend/app/main.py`.
- Enforced `DEBUG=False`, `DOCS_ENABLED=False`, and explicit host/CORS allowlists in production mode via `Settings` validators.

### Section 5: Dependency Security & Cleanup
- **Python Security Fix**: Upgraded `certifi` from `2026.7.22` to `2026.10.23` (resolves `PYSEC-2026-4320`). Pinned in both `requirements.txt` and `pyproject.toml`.
- **Frontend Dependency Cleanup**: Moved `@types/three` from runtime `dependencies` to `devDependencies` in `frontend/package.json`.
- **Audits**:
  - `python -m pip_audit`: **0 known vulnerabilities**.
  - `npm audit`: **0 vulnerabilities** (both root and `frontend`).

---

## 3. Files Created, Modified, and Deleted

### Files Created
- `backend/app/core/logging_filter.py`: Log filtering and sensitive data redaction.
- `docs/SECURITY_HARDENING_EXTENSION_REPORT.md`: Exported hardening extension report.

### Files Modified
- `backend/app/core/rate_limit.py`: Implemented temporary block recovery logic.
- `backend/app/api/v1/auth.py`: Added Sec-Fetch-Site and Referer CSRF checks; applied to logout.
- `backend/app/api/v1/admin.py`: Added `GET /admin/users` and `PUT /admin/users/{id}/role` with self-modification prevention and session invalidation.
- `backend/app/schemas/auth.py`: Added `UserRoleUpdateRequest` and `UserAdminListResponse`.
- `backend/app/main.py`: Initialized `setup_secure_logging()`.
- `backend/requirements.txt`: Added `certifi>=2026.10.18`.
- `backend/pyproject.toml`: Added `certifi>=2026.10.18` and `email-validator>=2.0.0`.
- `backend/tests/conftest.py`: Ensured token fixtures include `token_version`.
- `backend/tests/test_security_hardening.py`: Added 7 new test cases for rate limit recovery, CSRF rejection, admin authorization, self-role protection, session revocation on role change, log filtering, and production debug validation.
- `frontend/src/App.tsx`: Added `RequireRoles` route guard on `/admin`.
- `frontend/src/services/apiClient.ts`: Added `X-Requested-With` header on cookie requests.
- `frontend/package.json`: Moved `@types/three` to `devDependencies`.

---

## 4. Verification & Test Evidence

### Backend Pytest Suite
```text
============================= test session starts =============================
platform win32 -- Python 3.15.0, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\e\backend
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, platformdirs-4.14.5
collected 87 items

tests\test_attendance_outcomes.py .                                      [  1%]
tests\test_audit_sync.py ..                                              [  3%]
tests\test_auth.py .........                                             [ 13%]
tests\test_clubs.py .........                                            [ 24%]
tests\test_events.py ........                                            [ 33%]
tests\test_health.py ..                                                  [ 35%]
tests\test_meta.py .....                                                 [ 41%]
tests\test_notifications_analytics.py ..                                 [ 43%]
tests\test_proposals.py ...                                              [ 47%]
tests\test_rbac_matrix.py .............                                  [ 62%]
tests\test_security_hardening.py .........................               [ 90%]
tests\test_uploads_security.py ........                                  [100%]

======================== 87 passed, 1 warning in 2.46s ========================
```

### Dependency Audit Outputs
- **Python**: `python -m pip_audit` -> `No known vulnerabilities found`
- **Frontend**: `npm audit` -> `found 0 vulnerabilities`

### Frontend Linter & Build
- `oxlint`: `Found 0 warnings and 0 errors.`
- `npm run build`: Production build succeeded in 289ms with zero errors.

---

## 5. Remaining Security Risks & Operational Guidance

1. **Email Delivery & Password Resets**: Currently, password resets are not exposed over public email. When email reset flows are added, use single-use HMAC tokens with 15-minute expirations.
2. **Reverse Proxy Configuration**: Ensure production reverse proxies (Nginx/Cloudflare) are listed in `TRUSTED_PROXY_IPS` so client IPs are resolved correctly for rate limiting.
3. **MFA**: Multi-Factor Authentication (TOTP) is recommended for Administrator accounts managing user roles.

