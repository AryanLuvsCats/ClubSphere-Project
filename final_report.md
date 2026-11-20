# ClubSphere — Deployment Readiness Report

## Verdict: ⚠️ Not production-ready yet

The **backend is well-hardened**, but the **frontend has no production hosting path**, and there are **secrets/environment gaps** that must be closed before a real deploy. This assessment is based on source inspection plus prior build/test evidence in the docs; live builds, tests, and `git status` could not be run because the shell tool is unavailable in this environment (see Appendix A).

---

## ✅ What's ready

- **Strong production config validation** (`backend/app/core/config.py:222-254`): in production/staging it rejects weak or placeholder JWT secrets, `DEBUG=true`, `AUTO_CREATE_SCHEMA=true`, wildcard CORS/ALLOWED_HOSTS, and wildcard hosts. Fail-safe by design.
- **Security middleware stack** (`backend/app/main.py:100-123`): CORS allowlist, TrustedHost, body-size limit, security headers, HTTPS redirect; docs/OpenAPI auto-disabled in production.
- **Health probes** at both `/health` and `/api/v1/health`, returning 503 when the DB is disconnected — suitable for container/orchestrator probes.
- **Database migrations in place**: two Alembic revisions, head `c4e9a1b2d3f4` (baseline + auth sessions/throttle).
- **Backend Dockerfile** is reasonable: `0.0.0.0:8000`, `HEALTHCHECK`, and a `.dockerignore` that correctly excludes `.env`, `.env.*`, `*.db`, and `uploads/` — secrets are **not** baked into the image.
- **Remote-only database policy** enforced (`config.py:84-113`); local file SQLite is rejected at startup.
- **Test suite present** and prior evidence of a passing build (75 modules, `dist/` produced) and 58 pytest tests (`docs/NEON_SETUP_REPORT.md:79-119`).

## ❌ Blockers

1. **Frontend has no production serving configuration.** `frontend/src/services/apiClient.ts:3` hardcodes `API_BASE = '/api/v1'` (relative), which only works through the Vite **dev** proxy in `frontend/vite.config.ts:12-21`. There is no frontend Dockerfile, no nginx/Caddy/Traefik config, no reverse-proxy manifest, and no SPA fallback for React Router. If you deploy `frontend/dist/` to a static host, every API call will 404. **Fix:** serve the built SPA and backend behind one reverse proxy that routes `/api` and `/health` to Uvicorn, with `try_files … /index.html` for client-side routes.

2. **Live database credentials are in plaintext config files.** `backend/.env:11-12` and `.env.local:1-2` contain a real Neon credential (`npg_…`) pointing at the **production** branch (`NEON_BRANCH=production`). They are gitignored, but development is writing to the production database, and anyone with workspace access holds full DB access. **Fix:** inject these via the deployment platform's secret store, use a separate staging branch, and rotate the password if it was ever committed or logged.

3. **`docker-compose.yml` is development-only.** It sets `ENVIRONMENT=development`, `DEBUG=true`, a hardcoded placeholder JWT secret (`docker-compose.yml:15`), localhost-only CORS, a source-code bind mount, and has **no frontend or reverse-proxy service**. Deploying it as-is would leave the fail-safe validators disabled. Treat it strictly as a local devtool.

## ⚠️ Should address

4. **No production env manifest / CI-CD.** There's no `.github/workflows`, no deploy script, and no `.env.production.example`. You need to define and inject: `ENVIRONMENT=production`, `DEBUG=false`, `AUTO_CREATE_SCHEMA=false`, a strong 32+ char `JWT_SECRET_KEY`, explicit `CORS_ORIGINS` and `ALLOWED_HOSTS`, `FORCE_HTTPS=true`, and `TRUSTED_PROXY_IPS`. Also automate `alembic upgrade head` as a pre-deploy step.

5. **Uploads use local disk** (`AZURE_STORAGE_CONNECTION_STRING` empty, `AZURE_STORAGE_USE_EMULATOR=true`, `LOCAL_UPLOAD_DIR=./uploads`). In a container/cloud deploy without a persistent volume, uploaded files will be lost on restart and won't work across replicas. Configure Azure Blob Storage (or equivalent) before going live.

6. **Dockerfile runs as root** (no `USER` directive). Add a non-root user for defense in depth.

7. **Docs mention manual post-deploy steps** (`docs/SECURITY_HARDENING_REPORT.md:197-199`): set `FORCE_HTTPS`, secure refresh cookies, HSTS, and register the reverse proxy IP in `TRUSTED_PROXY_IPS` so rate limiting sees real client IPs. Most are already auto-enabled by environment in `config.py`, but `TRUSTED_PROXY_IPS` still needs a real value.

---

## Minimum checklist before deploy

- [ ] Add a reverse proxy / SPA hosting setup (static `dist/` + `/api` proxy + router fallback)
- [ ] Move DB credentials into platform secrets; rotate the exposed password; use a staging DB branch
- [ ] Create a production env template with all required production values
- [ ] Set `AUTO_CREATE_SCHEMA=false` and run `alembic upgrade head` in the pipeline
- [ ] Configure cloud object storage for uploads
- [ ] Add a CI workflow (lint → test → build → migrate → deploy) and re-run `npm run build` + `pytest` on the final state
- [ ] Verify `git ls-files` confirms no `.env` files are tracked (couldn't run git here)

---

## Appendix A — Tooling error encountered during review

Attempts to run shell commands (e.g. `git status --short`, `echo test`) failed with:

```
Command failed: <command>: failed to spawn C:\Users\Aryan\AppData\Local\Microsoft\WindowsApps\pwsh.exe: Access is denied. (os error 5)
```

Because of this, no live `git status`, `npm run build`, `npm run lint`, or `pytest` run was performed. All findings above come from static file inspection and previously recorded evidence in `docs/`.
