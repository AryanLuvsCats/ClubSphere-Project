# ClubSphere — Azure Database for PostgreSQL Flexible Server Setup & Migration Guide

A comprehensive, beginner-friendly operational guide for provisioning, securing, and migrating the ClubSphere application from Neon PostgreSQL to **Microsoft Azure Database for PostgreSQL Flexible Server** utilizing **Azure for Students** credits.

---

## 1. Overview

### What is Azure Database for PostgreSQL Flexible Server?
Azure Database for PostgreSQL Flexible Server is a fully managed database service from Microsoft built on the community version of PostgreSQL. It provides granular control over database configuration, built-in high availability, customizable maintenance windows, connection pooling (via built-in PgBouncer), automated backups, and flexible compute scaling (from cost-effective Burstable instances to Memory-Optimized workloads).

### Why ClubSphere Uses PostgreSQL
ClubSphere is a university club and event lifecycle management platform requiring:
- **Strict Relational Integrity:** Complex relationships between students, clubs, role-based memberships, events, and academic branches.
- **Transactional Consistency:** ACID-compliant registration and financial workflows preventing race conditions in event capacities and proposal approvals.
- **Advanced Constraints:** Native support for quoted check constraints (`"Status" IN ('Draft', 'Submitted', 'Approved', 'Rejected')`) and enumerated domain types.
- **Enterprise Security:** Enforced TLS 1.2+ encryption in transit, storage encryption at rest, and row/column security features.

### Why Neon is Being Replaced
While Neon provided serverless branching during early development:
1. **Academic Cloud Alignment:** Microsoft Azure is the preferred institutional cloud for academic institutions, allowing universities to deploy the entire stack (FastAPI on Azure App Service / Container Apps, Azure Blob Storage for uploads, and Azure PostgreSQL) within a unified tenant.
2. **Predictable Performance:** Azure Flexible Server provides dedicated compute (e.g., Burstable B1ms) with consistent latency, avoiding serverless scale-from-zero connection cold starts.
3. **Azure for Students Utilization:** Students and educators receive \$100 in annual Azure credits without requiring a credit card, allowing zero-out-of-pocket development and deployment within a single unified cloud subscription.

### How Azure PostgreSQL Integrates with FastAPI
FastAPI interacts with Azure PostgreSQL through **SQLAlchemy 2.0** ORM and the modern **psycopg** (version 3) binary database adapter. Connection pooling is managed using SQLAlchemy's `QueuePool` configured with:
- Connection pre-ping (`pool_pre_ping=True`) to validate connection health before query execution.
- Connection recycling (`pool_recycle=300`) to prevent Azure firewall gateway drops on idle TCP connections.
- Connection timeout handling (`connect_timeout=10`) ensuring unreachable hosts fail immediately without freezing worker threads.
- Clean shutdown handlers (`close_db_connections()` during FastAPI application lifecycle shutdown).

---

## 2. Azure for Students Setup

### Activating Azure for Students
1. Navigate to the official [Azure for Students Portal](https://azure.microsoft.com/en-us/free/students/).
2. Click **Start free**.
3. Sign in using your university/academic email address (`.edu`, `.ac.uk`, `.edu.in`, etc.).
4. Complete the academic verification step (via institutional email code verification or GitHub Student Developer Pack).
5. **No credit card is required** for activation. Upon successful verification, an **Azure for Students** subscription with **\$100 in cloud credits** valid for 12 months will be provisioned.

### Accessing the Azure Portal
Open your web browser and navigate to:
```
https://portal.azure.com/
```
Ensure you are signed in under the Azure Active Directory directory that holds your Student subscription (visible in the top-right account menu).

### Verifying Student Credit Availability
1. In the global search bar at the top of the Azure Portal, type **Subscriptions** and press Enter.
2. Select **Azure for Students**.
3. Verify that the **Status** displays **Active**.
4. To view remaining balances, search for **Cost Management + Billing** or visit the [Microsoft Azure Sponsorships Portal](https://www.microsoftazuresponsorships.com/) to view your exact credit balance and expiration date.

### Creating a Resource Group
A Resource Group is a logical container for related Azure resources.
1. In the Azure Portal search bar, type **Resource groups** and click **Create**.
2. Configure the following details:
   - **Subscription:** `Azure for Students`
   - **Resource group:** `rg-clubsphere-dev`
   - **Region:** Select the region closest to your campus or target users (e.g., `East US`, `Central India`, or `West Europe`).
3. Click **Review + create**, then click **Create**.

### Verifying Service Quotas & Region Availability
> [!IMPORTANT]
> Azure for Students credit does **not** grant unlimited access to all Azure compute sizes. Burstable tiers (such as `Standard_B1ms`) are widely supported, but quota limits vary per Azure region.

To verify that Azure Database for PostgreSQL is registered and available in your subscription:
1. In your **Subscription** overview, click **Resource providers** in the left menu.
2. Search for `Microsoft.DBforPostgreSQL`.
3. If the status is `NotRegistered`, select it and click **Register**. Wait 1–2 minutes until it changes to `Registered`.

---

## 3. Create Azure PostgreSQL Flexible Server

Follow these step-by-step instructions to create your database server using the Azure Portal:

### Step 3.1: Navigate to PostgreSQL Flexible Server
1. In the Azure Portal search bar, search for **Azure Database for PostgreSQL flexible servers**.
2. Click **+ Create**.

### Step 3.2: Configure Basics
- **Subscription:** Select `Azure for Students`.
- **Resource Group:** Select `rg-clubsphere-dev`.
- **Server Name:** Enter a globally unique DNS name, such as:
  ```
  clubsphere-pg-yourname
  ```
  *(Final hostname will be `clubsphere-pg-yourname.postgres.database.azure.com`)*
- **Region:** Choose the same region as your resource group (e.g., `East US`).
- **PostgreSQL Version:** Select **16** (or **15**; both are 100% compatible with ClubSphere's schema).
- **Workload Type:** Select **Development** (this pre-configures cost-effective burstable defaults).

### Step 3.3: Configure Compute + Storage
Click **Configure server** to select the development compute tier:
- **Compute Tier:** Select **Burstable**.
- **Compute Size:** Select **Standard_B1ms** (1 vCore, 2 GiB RAM).
- **Storage:** Select **32 GiB** (the lowest available tier).
- **Storage Auto-grow:** Optional (disable to prevent unintentional storage scaling).
- **Backup Retention:** Set to **7 days** (minimum allowed; backup storage within the provisioned database size is included at no extra charge).
- **High Availability:** Leave **Disabled** (saves 50% on compute costs; not required for student development).
- Click **Save**.

> [!NOTE]
> **Cost & Performance Tradeoffs:**
> `Standard_B1ms` costs approximately \$12–\$15/month when running 24/7, easily fitting within the \$100 student allowance for the semester. Note that B1ms has a maximum limit of 50 concurrent connections; our backend connection pool is explicitly configured (`DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=20`) to prevent exhausting this threshold.

### Step 3.4: Configure Administrator Credentials
- **Authentication Method:** Select **PostgreSQL authentication only** (or PostgreSQL and Microsoft Entra ID).
- **Admin Username:** `csadmin`
- **Admin Password:** Enter a strong password (minimum 16 characters, mix of uppercase, lowercase, numbers, and symbols).
  > [!TIP]
  > Avoid characters that require complex URI escaping (such as `@`, `:`, or `/`) in connection strings. If your password contains `@` or `%`, it must be URL-encoded (e.g., `@` becomes `%40`, `%` becomes `%25`).

### Step 3.5: Configure Networking
1. Click the **Networking** tab.
2. **Connectivity method:** Select **Public access (allowed IP addresses)**.
   *(Private access via VNet integration is optimal for enterprise production, but public access with strict firewall rules is recommended for local and student development).*
3. **Allow public access from any Azure service:** Check this box if you plan to host the FastAPI backend on Azure App Service or Container Apps.
4. **Firewall rules:**
   - Click **+ Add current client IP address** to automatically add your local computer's public IP.
   - Rule Name: `dev-workstation`
   - Start IP / End IP: Your current public IP address.
5. Click **Next: Security**.

### Step 3.6: Configure Security & TLS
1. **Data encryption:** Leave at service-managed key default.
2. In Server Parameters (accessible after provisioning), verify that **`require_secure_transport`** is set to **`ON`** (enforcing TLS 1.2+).

### Step 3.7: Review + Create
1. Click **Review + create**.
2. Review the summary and estimated monthly cost.
3. Click **Create**. Deployment typically takes 3 to 6 minutes.

### Step 3.8: Create the Application Database
Once the server deployment finishes:
1. Navigate to the newly created resource (`clubsphere-pg-yourname`).
2. In the left-hand navigation under **Settings**, click **Databases**.
3. Click **+ Add**.
4. Database name: `clubsphere`
5. Collation: `utf8_general_ci` or `DEFAULT`
6. Charset: `UTF8`
7. Click **Save**.

---

## 4. Networking and Security

### Public Access vs. Private Networking
- **Private Endpoints (VNet):** Recommended for production enterprise environments. The database has no public IP address and is accessible only from resources inside an Azure Virtual Network.
- **Public Access with Firewall Rules:** Recommended for university development. The database resolves to a public DNS address, but Azure's perimeter firewall drops all incoming TCP packets on port 5432 unless the client's public IP address is explicitly whitelisted.

### Firewall Rules: Why 0.0.0.0/0 is Dangerous
> [!CAUTION]
> Never add a firewall rule with Start IP `0.0.0.0` and End IP `255.255.255.255`. Exposing port 5432 to the entire internet exposes your database to continuous brute-force attacks, port scans, and credential stuffing. Always restrict access to your specific ISP/home IP address and trusted CI/CD ranges.

### Updating Your Firewall Rule When Your IP Changes
If your home or campus Wi-Fi IP address changes:
1. Open the Azure Portal and navigate to your PostgreSQL Flexible Server.
2. In the left menu, select **Networking**.
3. Click **+ Add current client IP address** or update the existing rule.
4. Click **Save**.

### TLS Certificate Verification
Azure PostgreSQL requires encrypted TLS connections by default.
- **Root CA:** Azure uses the **DigiCert Global Root G2** certificate authority.
- Modern OS trust stores (Windows, macOS, Ubuntu) already trust this root certificate authority.
- For maximum security in production, you can download the root certificate:
  [Download DigiCertGlobalRootG2.crt.pem](https://cacerts.digicert.com/DigiCertGlobalRootG2.crt.pem)
- Set `sslmode=verify-full` and configure `AZURE_POSTGRES_SSLROOTCERT=/path/to/DigiCertGlobalRootG2.crt.pem`.

### Creating a Least-Privilege Application User
It is a security best practice not to run application queries as the server admin (`csadmin`). Connect via `psql` and create a dedicated application user:
```sql
-- Connect as csadmin to the clubsphere database
CREATE USER clubsphere_app WITH PASSWORD 'StrongAppPasswordHere123!';
GRANT CONNECT ON DATABASE clubsphere TO clubsphere_app;
GRANT USAGE ON SCHEMA public TO clubsphere_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO clubsphere_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO clubsphere_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO clubsphere_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO clubsphere_app;
```

---

## 5. Database Connection Setup

### Gathering Connection Parameters
From the Azure Portal overview page of your PostgreSQL Flexible Server, note down:
- **Server Name:** `clubsphere-pg-yourname.postgres.database.azure.com`
- **Server Admin Login Name:** `csadmin`
- **Database Name:** `clubsphere`
- **Port:** `5432`
- **SSL:** Enabled (`require` or `verify-full`)

### Configuring `backend/.env`
Update your local `backend/.env` file (which is excluded from Git):

```ini
# Primary Connection String (PostgreSQL with psycopg3 driver)
DATABASE_URL=postgresql+psycopg://csadmin:YourSecurePassword123%21@clubsphere-pg-yourname.postgres.database.azure.com:5432/clubsphere?sslmode=require

# Direct Endpoint for Alembic Migrations
DATABASE_URL_UNPOOLED=postgresql+psycopg://csadmin:YourSecurePassword123%21@clubsphere-pg-yourname.postgres.database.azure.com:5432/clubsphere?sslmode=require

# Optional component breakdown (auto-assembled with proper escaping if DATABASE_URL is unset)
# AZURE_POSTGRES_HOST=clubsphere-pg-yourname.postgres.database.azure.com
# AZURE_POSTGRES_PORT=5432
# AZURE_POSTGRES_USER=csadmin
# AZURE_POSTGRES_PASSWORD=YourSecurePassword123!
# AZURE_POSTGRES_DB=clubsphere
# AZURE_POSTGRES_SSLMODE=require

# Connection Pool Settings
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=300
DB_CONNECT_TIMEOUT=10
```

### Testing the Connection Safely
You can test the connectivity using the Python runtime directly from `backend/`:
```bash
cd backend
python -c "from app.core.database import SessionLocal, check_db_health; db = SessionLocal(); print('Connected!' if check_db_health(db) else 'Connection Failed!'); db.close()"
```
Or via the PostgreSQL command-line client:
```bash
psql "host=clubsphere-pg-yourname.postgres.database.azure.com port=5432 dbname=clubsphere user=csadmin sslmode=require"
```

---

## 6. Neon to Azure Migration

Follow this safe, 4-step data migration procedure to move all existing data from Neon to Azure PostgreSQL without data loss.

### Step 6.1: Export Existing Neon Data using `pg_dump`
Create a clean logical backup of your Neon database. Note that the existing Neon database remains completely untouched and active as a fallback.

Run in your terminal (replacing with your Neon connection string):
```bash
# Dump the Neon database into a compressed custom-format archive:
pg_dump --clean --if-exists --no-owner --no-privileges -Fc \
  -d "postgresql://user:password@ep-xxx-pooler.region.aws.neon.tech/neondb?sslmode=require" \
  -f clubsphere_neon_backup.dump
```
*Why these flags:*
- `--clean --if-exists`: Emits DROP statements only if tables exist.
- `--no-owner --no-privileges`: Omits Neon-specific superuser ownership commands so the dump imports cleanly into Azure without role permission conflicts.
- `-Fc`: Custom compressed binary archive supporting selective restore and integrity checking.

### Step 6.2: Inspect the Dump File
Verify that the dump file contains the expected schema and data:
```bash
pg_restore -l clubsphere_neon_backup.dump | head -n 30
```

### Step 6.3: Restore Data to Azure PostgreSQL Flexible Server
Ingest the dump file into your Azure database:
```bash
pg_restore --no-owner --no-privileges \
  -d "postgresql://csadmin:YourPassword@clubsphere-pg-yourname.postgres.database.azure.com:5432/clubsphere?sslmode=require" \
  clubsphere_neon_backup.dump
```

If your dump is in plain `.sql` format, ingest via `psql`:
```bash
psql -d "postgresql://csadmin:YourPassword@clubsphere-pg-yourname.postgres.database.azure.com:5432/clubsphere?sslmode=require" -f clubsphere_neon_backup.sql
```

### Step 6.4: Synchronize Alembic Migrations
Ensure Alembic migration state is synchronized on Azure:
```bash
cd backend
python -m alembic upgrade head
```
*(If the tables and data were restored directly with `alembic_version` included in the dump, verify with `python -m alembic current` to confirm the revision is stamped at `c4e9a1b2d3f4_auth_sessions_and_throttle`).*

### Step 6.5: Verify Tables and Row Counts
Run this SQL query against both Neon and Azure to verify row count parity across all tables:
```sql
SELECT 'Roles' AS table_name, count(*) FROM "Roles"
UNION ALL SELECT 'Branches', count(*) FROM "Branches"
UNION ALL SELECT 'Programs', count(*) FROM "Programs"
UNION ALL SELECT 'Users', count(*) FROM "Users"
UNION ALL SELECT 'Clubs', count(*) FROM "Clubs"
UNION ALL SELECT 'ClubMemberships', count(*) FROM "ClubMemberships"
UNION ALL SELECT 'Events', count(*) FROM "Events"
UNION ALL SELECT 'EventRegistrations', count(*) FROM "EventRegistrations"
UNION ALL SELECT 'Proposals', count(*) FROM "Proposals"
UNION ALL SELECT 'AuditLogs', count(*) FROM "AuditLogs"
UNION ALL SELECT 'AuthThrottle', count(*) FROM "AuthThrottle"
UNION ALL SELECT 'RefreshSessions', count(*) FROM "RefreshSessions";
```

### Step 6.6: Switch Application & Verify
1. Update `DATABASE_URL` in `backend/.env` with the Azure PostgreSQL connection string.
2. Start the backend:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```
3. Check the health endpoint:
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/health
   ```
   Expected response:
   ```json
   {
     "status": "healthy",
     "app": "ClubSphere",
     "environment": "development",
     "database": "connected",
     "timestamp": "2026-11-17T..."
   }
   ```

---

## 7. Troubleshooting

| Issue | Root Cause | Solution |
|---|---|---|
| **Connection Refused (`connection to server at ... failed`)** | Server is stopped or port 5432 is blocked by a local network firewall. | Check server status in Azure Portal (ensure it is **Ready**). Ensure you are connecting to port 5432. |
| **Firewall Error (`Client with IP address '...' is not allowed`)** | Your workstation's public IP address is not whitelisted in Azure Firewall rules. | In Azure Portal, navigate to **Networking** on the server, click **+ Add current client IP address**, and click **Save**. |
| **TLS/SSL Error (`SSL error: certificate verify failed`)** | Root certificate missing or invalid `sslmode` specified. | Use `sslmode=require` for standard TLS encryption. If using `sslmode=verify-full`, download `DigiCertGlobalRootG2.crt.pem` and provide `AZURE_POSTGRES_SSLROOTCERT`. |
| **Authentication Failed (`FATAL: password authentication failed`)** | Wrong username/password, or special characters unescaped. | Azure Flexible Server uses username format `csadmin` (unlike Single Server, Flexible Server does not require `@servername`). URL-encode special characters in the password (`@` -> `%40`, `#` -> `%23`). |
| **Driver Scheme Error (`ValueError: DATABASE_URL must use postgresql:// or postgresql+psycopg://`)** | Legacy `postgres://` or incompatible driver scheme in `.env`. | Use `postgresql+psycopg://` or `postgresql://`. The app automatically normalizes `postgres://` to `postgresql://`. |
| **Missing Database Error (`FATAL: database "clubsphere" does not exist`)** | Connecting before creating the database. | Open Azure Portal > PostgreSQL Server > **Databases** > **+ Add** and create `clubsphere`. |
| **Check Constraint / Migration Failure** | PostgreSQL case-sensitivity differences during restore. | All constraints in ClubSphere are double-quoted (`"Status" IN (...)`). Ensure `pg_restore` is run with `--no-owner --no-privileges`. |
| **Connection Pool Exhaustion (`Timeout: QueuePool limit of size 10 overflow 20 reached`)** | Leaked database sessions in route handlers or long-running tasks. | All endpoints must use `db: Session = Depends(get_db)` to guarantee sessions are closed via the generator's `finally` block. Our app configures `pool_recycle=300` and `pool_pre_ping=True`. |

---

## 8. Cost Management

### How Azure for Students Credit Works
- When you activate Azure for Students, you receive **\$100 in credit** valid for 12 months.
- There is **no automatic credit card billing**. If your credit is exhausted, resources are stopped rather than billed to a personal account.
- However, if credits run out, your database stops running until renewed or upgraded.

### Inspecting Remaining Credits
- Check your balance in the Azure Portal by navigating to **Cost Management + Billing**.
- Or visit [www.microsoftazuresponsorships.com](https://www.microsoftazuresponsorships.com/) for detailed per-day spending breakdowns.

### Setting Up Budget Alerts
> [!IMPORTANT]
> Budget alerts notify you via email when spending reaches specific thresholds. **Budget alerts do NOT automatically shut down resources.** You must manually stop or delete resources when notified.

To set up an alert:
1. Search for **Subscriptions** in the Azure Portal > select **Azure for Students**.
2. Click **Budgets** in the left sidebar.
3. Click **+ Add**.
4. Set Budget Name: `clubsphere-monthly-budget`
5. Reset Period: `Monthly`
6. Amount: `$20`
7. Set Thresholds:
   - `50%` (\$10) -> Alert Email
   - `75%` (\$15) -> Alert Email
   - `90%` (\$18) -> Alert Email
8. Enter your university email address and click **Create**.

### Stopping Development Resources When Idle
When not developing (e.g., weekends or vacations):
1. Navigate to your PostgreSQL server in the Azure Portal.
2. Click **Stop** on the top toolbar.
3. Compute billing stops immediately.
4. **Note:** Stopped servers can remain stopped for up to 7 consecutive days, after which Azure automatically restarts them to apply critical maintenance patches. You can stop them again after restart.
5. **What continues to incur cost:** Provisioned disk storage (32 GiB is approximately \$3.50/month) and public IP retention incur minimal charges even while compute is stopped.

---

## 9. Deployment

### Connecting Hosted Backend to Azure PostgreSQL
When deploying ClubSphere to Azure App Service or Azure Container Apps:
1. Configure Environment Variables in the App Service **Configuration / Environment variables** blade:
   - `DATABASE_URL`: `postgresql+psycopg://csadmin:PASSWORD@clubsphere-pg-yourname.postgres.database.azure.com:5432/clubsphere?sslmode=require`
   - `ENVIRONMENT`: `production`
   - `DEBUG`: `false`
   - `AUTO_CREATE_SCHEMA`: `false`
2. **Networking:** In Azure PostgreSQL Flexible Server **Networking**, ensure **Allow public access from any Azure service within Azure to this server** is enabled, or configure a **Virtual Network Subnet Integration** between the App Service and the PostgreSQL server.
3. **Automated Migrations:** In production CI/CD pipelines (e.g., GitHub Actions), run `alembic upgrade head` as a pre-deployment migration step before swapping production slots.

---

## 10. Verification Checklist

Before considering the migration complete, verify each of the following:

- [ ] **Azure PostgreSQL Server Provisioned:** Server is in `Ready` state in `rg-clubsphere-dev`.
- [ ] **Database Created:** Database `clubsphere` exists on the server.
- [ ] **Firewall Whitelist Active:** Development IP is whitelisted under Server Networking.
- [ ] **TLS 1.2+ Enforced:** `require_secure_transport=ON` in Server Parameters.
- [ ] **No Hardcoded Secrets:** `backend/.env` is ignored by Git (`git status` shows clean).
- [ ] **Data Consistency Verified:** Row counts match across all 11 tables between Neon and Azure.
- [ ] **Alembic Synchronized:** `python -m alembic current` reports `head` revision.
- [ ] **Backend Health Probe Passed:** `GET /api/v1/health` returns `status: healthy`, `database: connected`.
- [ ] **Backend Test Suite Passed:** All 94 Pytest unit and integration tests pass cleanly (`pytest backend/tests`).
- [ ] **Frontend Build Passed:** Frontend production build completes cleanly (`npm run build`).
- [ ] **Cost Budget Configured:** Monthly budget alert configured for student credits.
- [ ] **Neon Backup Retained:** Original Neon database remains intact and untouched as a cold rollback target.
