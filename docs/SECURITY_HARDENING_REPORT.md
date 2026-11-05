# ClubSphere Security Hardening Report: Authentication, API Security & Database Protection

**Date:** 2026-11-05  
**Application:** ClubSphere University Club & Activity Lifecycle Management System  
**Stack:** React 19 + Vite (Frontend), FastAPI + SQLAlchemy (Backend), Neon PostgreSQL (Production DB)  

---

## 1. Summary of Security Vulnerabilities Identified in Initial Codebase

During the initial architecture and security audit (Phase 1), several critical and high-severity security vulnerabilities were identified:

1. **Insecure Password Storage (High / CWE-916)**:
   - Passwords were hashed using standard `bcrypt` without length validation or memory-hard hashing parameters. Passwords longer than 72 bytes were silently truncated by bcrypt, allowing potential credential collisions.
2. **Insecure Token Storage & Refresh Insecurity (High / CWE-922, CWE-613)**:
   - Both access tokens and refresh tokens were previously stored in browser `localStorage`. Any Cross-Site Scripting (XSS) vulnerability would allow trivial theft of long-lived tokens.
   - Refresh tokens lacked rotation, server-side session tracking, and replay detection mechanisms.
3. **No Brute-Force Rate Limiting (High / CWE-307)**:
   - Authentication endpoints (`/api/v1/auth/login`, `/api/v1/auth/register`) had no active rate limiting. An attacker could brute-force passwords or flood account creation without restriction.
4. **Insecure Direct Object References (IDOR) & Broken Object-Level Authorization (Critical / CWE-639, CWE-285)**:
   - Club managers and students could potentially read or mutate unapproved or private entities (proposals, draft events, outcomes, pending clubs).
   - Faculty and HOD members were not restricted to their own academic branch/department when reviewing club proposals, allowing cross-departmental approval/rejection.
   - HOD analytics exposed university-wide statistics instead of being strictly scoped to their assigned academic branch.
5. **Missing File Upload & MIME Magic-Byte Verification (High / CWE-434)**:
   - Upload endpoints accepted files relying solely on client-provided `Content-Type` headers without inspecting file signatures (magic bytes), enabling file upload masquerading.
   - File attachment lacked entity ownership validation, allowing users to attach arbitrary files to entities owned by other users.
6. **Missing Security Headers & Injection Safeguards (Medium / CWE-1021, CWE-693)**:
   - API endpoints lacked HTTP security headers (`Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`, `Referrer-Policy`).
   - Pydantic models allowed undeclared fields (`extra="allow"`), creating mass-assignment risks.
   - No body size limits were enforced at the application layer, exposing the service to request entity flooding Denial of Service (DoS).

---

## 2. Implemented Security Improvements

### Phase 2: Secure Authentication Hardening
- **Argon2id Password Hashing**: Upgraded primary password hasher to Argon2id (`Type.ID`, `m=65536` [64 MiB], `t=3`, `p=4`, 32-byte hash length, 16-byte salt). Implemented fallback support for legacy bcrypt hashes with automatic transparent rehash to Argon2id upon successful login.
- **Timing Attack Mitigation**: Added `verify_dummy_password` using a pre-computed hash to equalize response times when authenticating non-existent user accounts.
- **In-Memory Access Tokens**: Configured access tokens (15-minute expiry) to live strictly in JavaScript memory; they are never persisted to `localStorage` or `sessionStorage`.
- **HttpOnly Cookie Refresh Tokens**: Long-lived refresh tokens (7 days) are issued as `HttpOnly`, `SameSite=Strict`, `Path=/api/v1/auth`, `Secure` cookies.
- **Token Family Tracking & Replay Detection**: Refresh sessions are tracked in a dedicated `RefreshSessions` table. If a previously rotated refresh token is reused outside the 30-second concurrency grace window, the entire token family is immediately revoked.
- **Session Revocation & Logout**: Server-side logout revokes active refresh token sessions and increments the user's `TokenVersion`, invalidating all outstanding access tokens.
- **Database-Backed Rate Limiting**: Implemented `AuthThrottle` table and rate limiter (`app/core/rate_limit.py`) enforcing sliding-window rate limits on IP and email hashes, resisting multi-worker bypass.

### Phase 3: Secrets & API Key Isolation
- All sensitive credentials (`JWT_SECRET_KEY`, `DATABASE_URL`, `AZURE_STORAGE_CONNECTION_STRING`) remain strictly backend-side.
- Startup validation in `app/core/config.py` enforces minimum secret key length (>= 32 chars) and prevents insecure default secret keys in production.
- Sanitized `backend/.env.example` with placeholders; verified `.env` and `.env.local` are excluded via `.gitignore`.
- Zero frontend exposure: No `VITE_` private variables exist in frontend code.

### Phase 4: Database Access Control & Data Isolation
- Created centralized object-level authorization helpers (`app/core/authorization.py`):
  - `can_manage_club`: Restricts club mutations to assigned club managers or administrators.
  - `can_view_club`: Conceals pending/suspended clubs (returns 404 to unauthorized users).
  - `can_manage_event` & `can_view_event`: Conceals draft events from non-managers/non-admins.
  - `can_view_proposal`: Restricts proposal viewing and approval to the applicant, administrator, or faculty/HOD matching the exact academic branch.
  - `branch_id_for_user`: Scopes HOD analytics to the user's branch.
- Outcome Privacy: Restricted event outcome viewing to registered event attendees, club managers, or administrators.

### Phase 5: HTTPS, Security Headers & Network Controls
- Implemented `SecurityHeadersMiddleware`:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()`
  - `Cross-Origin-Opener-Policy: same-origin`
  - `Cross-Origin-Resource-Policy: same-origin`
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'` (on API endpoints)
  - `Cache-Control: no-store; Pragma: no-cache` (on authentication endpoints)
- HSTS & HTTPS Enforcement: Added `Strict-Transport-Security` header (when HTTPS is detected or proxy-forwarded via trusted reverse proxies) and optional HTTP-to-HTTPS redirect middleware.
- Request Body Size Limiting: `BodySizeLimitMiddleware` terminates requests exceeding maximum body sizes (1 MB for standard JSON, 11 MB for uploads) before parsing.
- Trusted Proxy IP filtering: Prevents IP spoofing via crafted `X-Forwarded-For` headers.

### Phase 6 & 7: Input Validation, XSS & SQL Injection Defense
- Strict Pydantic Schemas: Configured `ConfigDict(extra="forbid", str_strip_whitespace=True)` on request schemas.
- Anti-XSS Sanitization: Implemented input validators stripping or rejecting HTML tags (`<script>`, `<iframe`, etc.) in names, descriptions, and comments.
- Magic Byte Verification: Implemented file signature validation in `app/core/storage.py` and `app/api/v1/uploads.py` for JPEG (`\xFF\xD8\xFF`), PNG (`\x89PNG\r\n\x1a\n`), WEBP (`RIFF....WEBP`), PDF (`%PDF`), and DOCX (`PK\x03\x04`).
- Parameterized Queries: All database operations use SQLAlchemy ORM or explicitly bound parameters, preventing SQL injection.

---

## 3. Files Created, Modified, and Deleted

### Files Created
- `backend/app/core/authorization.py`: Reusable object-level authorization and branch-scoping logic.
- `backend/app/core/middleware.py`: Security headers, HTTPS redirect, and body size limiting middleware.
- `backend/app/core/rate_limit.py`: Database-backed brute-force throttling using SHA-256 hashed keys.
- `backend/app/schemas/common.py`: Shared Pydantic base models and XSS validation primitives.
- `backend/alembic.ini`: Alembic migration configuration.
- `backend/alembic/env.py`: Migration environment runner.
- `backend/alembic/versions/b3df5d5ed152_baseline_schema.py`: Baseline schema migration.
- `backend/alembic/versions/c4e9a1b2d3f4_auth_sessions_and_throttle.py`: Additive migration for `RefreshSessions` and `AuthThrottle`.
- `backend/tests/test_security_hardening.py`: 18 dedicated security hardening tests.
- `backend/.dockerignore`: Prevents sensitive files and virtual environments from leaking into containers.
- `docs/NEON_SETUP_REPORT.md`: Neon setup and verification documentation.
- `docs/SECURITY_HARDENING_REPORT.md`: Exported security hardening documentation.

### Files Modified
- `backend/app/core/security.py`: Argon2id hasher, token families, and dummy verification.
- `backend/app/core/config.py`: Security configuration settings, HSTS, trusted proxies, and environment precedence.
- `backend/app/core/database.py`: Safe URL handling, connection pooling, and connection recycling.
- `backend/app/core/storage.py`: Magic byte file inspection and path traversal protection.
- `backend/app/core/rbac.py`: Role enforcement and token version validation.
- `backend/app/models/models.py`: Added `RefreshSession` and `AuthThrottle` models; quoted check constraints.
- `backend/app/main.py`: Middleware registration, global exception sanitization, and route mounting.
- `backend/app/api/v1/auth.py`: HttpOnly cookie issuance, token rotation, and rate-limited endpoints.
- `backend/app/api/v1/clubs.py`: IDOR protection and status-filtered visibility.
- `backend/app/api/v1/events.py`: Draft event isolation and outcome privacy checks.
- `backend/app/api/v1/proposals.py`: Branch-scoped proposal review and access control.
- `backend/app/api/v1/admin.py`: Branch-scoped HOD analytics and admin authorization.
- `backend/app/api/v1/uploads.py`: Entity ownership validation and upload security checks.
- `backend/app/schemas/*.py`: Added `extra="forbid"` and string sanitization.
- `backend/requirements.txt`: Added `argon2-cffi`, `psycopg2-binary`, and `psycopg[binary]`.
- `backend/tests/conftest.py`: Updated fixtures for testing with isolated in-memory DB and mock headers.
- `frontend/src/services/apiClient.ts`: In-memory token management, cookie refresh flow, and token rotation.
- `frontend/src/services/authService.ts`: Session restoration and logout revocation.
- `frontend/src/context/AuthContext.tsx`: Transparent session bootstrapping on page reload.
- `package.json` & `.gitignore`: Added root build script and ignored `.neon` / `.env.local`.

---

## 4. Dependencies Added and Rationale

| Dependency | Purpose / Rationale |
| :--- | :--- |
| `argon2-cffi>=23.1.0` | Memory-hard, state-of-the-art password hashing conforming to OWASP and RFC 9106. |
| `psycopg2-binary>=2.9.10` | High-performance PostgreSQL database adapter for SQLAlchemy on Neon Lakebase Postgres. |
| `psycopg[binary]>=3.2.0` | Modern psycopg 3 driver for Python 3.15 runtime compatibility. |
| `alembic>=1.13.0` | Schema migration management ensuring additive, non-destructive database evolution. |

---

## 5. Database Migrations Created

1. **`b3df5d5ed152_baseline_schema.py`**:
   - Baseline migration snapshot capturing existing tables: `Branches`, `Programs`, `Roles`, `Users`, `Clubs`, `ClubMemberships`, `Events`, `EventRegistrations`, `Attendance`, `ClubProposals`, `Approvals`, `EventOutcomes`, `Notifications`, `AuditLogs`, `UploadedFiles`.
2. **`c4e9a1b2d3f4_auth_sessions_and_throttle.py`**:
   - Additive migration creating:
     - `RefreshSessions`: For single-use refresh token rotation, replay detection, and family revocation.
     - `AuthThrottle`: For rate limiting with sliding windows and hashed keys.
   - Successfully applied to production database on Neon (`alembic upgrade head`).

---

## 6. Environment Variables Required

| Variable | Description | Recommended / Default Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | Neon pooled PostgreSQL connection string | `postgresql://...` |
| `JWT_SECRET_KEY` | Cryptographic secret for signing access tokens | 32+ random characters |
| `JWT_ALGORITHM` | Algorithm for JWT signature | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Lifetime of in-memory access tokens | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Lifetime of HttpOnly refresh cookies | `7` |
| `ARGON2_TIME_COST` | Iterations for Argon2id hashing | `3` |
| `ARGON2_MEMORY_COST` | Memory cost (in KiB) for Argon2id hashing | `65536` (64 MiB) |
| `ARGON2_PARALLELISM` | Parallel threads for Argon2id hashing | `4` |
| `CORS_ORIGINS` | Explicit frontend origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `FORCE_HTTPS` | Redirect HTTP requests to HTTPS | `false` in dev; `true` in prod |
| `HSTS_SECONDS` | HSTS max-age seconds | `0` in dev; `31536000` (1 yr) in prod |
| `TRUSTED_PROXY_IPS` | Reverse proxy IPs trusted for `X-Forwarded-*` | `127.0.0.1` |
| `REFRESH_COOKIE_SECURE` | Enforce `Secure` flag on refresh cookie | `false` in dev; `true` in prod |

---

## 7. Tests Executed & Results

- **Backend Pytest Suite**:
  - Command: `pytest`
  - Result: **80 passed** (including all 18 new security hardening tests).
- **Frontend Linter (`oxlint`)**:
  - Command: `npm run lint`
  - Result: **0 errors, 0 warnings** across 47 files.
- **Frontend Production Build**:
  - Command: `npm run build`
  - Result: **Passed** (`dist/` successfully generated with zero TypeScript compilation errors).
- **Live End-to-End Application Security Test**:
  - Tested live against Neon PostgreSQL with running FastAPI and Vite servers:
    - `/health` responded with `database: connected` and security headers.
    - User registration generated an `$argon2id$` hash on Neon PostgreSQL.
    - Login returned in-memory access token and issued `clubsphere_refresh` HttpOnly cookie.
    - Security headers (`nosniff`, `DENY`, `no-referrer`, API CSP) confirmed present in HTTP responses.

---

## 8. Remaining Security Risks & Recommended Next Steps

1. **Email Verification**: User registration currently creates active accounts directly. If email confirmation links/OTPs are introduced, an unverified state should gate access.
2. **Multi-Factor Authentication (MFA)**: Administrative and HOD roles would benefit from TOTP (RFC 6238) authentication for sensitive actions.
3. **Cloud Object Storage**: File uploads currently use local disk storage when Azure/S3 connection strings are unset. In production, configure object storage with private bucket policies and presigned URLs.
4. **WAF / Edge Protection**: For enterprise scale, deploy behind Cloudflare or AWS CloudFront with WAF rules for Layer 7 DDoS mitigation.

---

## 9. Manual Deployment Steps Required

1. **Set Environment Variables**: Ensure `JWT_SECRET_KEY` is set to a cryptographically secure random string (`openssl rand -hex 32`) on the hosting provider.
2. **Apply Migrations**: Run `python -m alembic upgrade head` as part of the deployment pipeline before starting Uvicorn workers.
3. **Enable Production Security Flags**: Set `FORCE_HTTPS=true`, `REFRESH_COOKIE_SECURE=true`, and `HSTS_SECONDS=31536000` in the production environment.
4. **Configure Reverse Proxy**: Add your reverse proxy (e.g. Nginx, Traefik, or Caddy) IP to `TRUSTED_PROXY_IPS`.

---

## 10. Security Verification Checklist

- [x] Passwords hashed using Argon2id with OWASP-recommended parameters.
- [x] Legacy bcrypt hashes verified and automatically upgraded on login.
- [x] Access tokens short-lived (15 min) and held in memory only.
- [x] Refresh tokens stored in HttpOnly, SameSite=Strict cookies.
- [x] Single-use refresh token rotation with token family replay detection.
- [x] Server-side logout revoking refresh sessions and invalidating tokens via `TokenVersion`.
- [x] Brute-force rate limiting active on `/auth/login` and `/auth/register`.
- [x] Object-level authorization enforcing ownership and academic branch boundaries (IDOR prevention).
- [x] Pydantic schemas reject undeclared extra fields (`extra="forbid"`).
- [x] Input validation strips/rejects malicious HTML and script tags.
- [x] File uploads verified via file signatures (magic bytes) and MIME allowlist.
- [x] Security headers and API Content Security Policy emitted on all responses.
- [x] CORS restricted to configured frontend origins; credentials disallowed on wildcards.
- [x] All 80 backend tests, frontend linting, and build pass cleanly.

