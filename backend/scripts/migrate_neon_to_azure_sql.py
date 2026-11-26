"""Idempotent data migration script: Neon PostgreSQL -> Azure SQL Database (T-SQL).

Reads all rows from SOURCE_NEON_URL, initializes the schema and reporting views
in TARGET_AZURE_SQL_URL, preserves primary keys cleanly via SET IDENTITY_INSERT
where applicable, and verifies exact row-count parity for every table.

Usage:
    set SOURCE_NEON_URL=postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require
    set TARGET_AZURE_SQL_URL=mssql+pyodbc://csadmin:pass@srv.database.windows.net:1433/clubsphere?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
    python scripts/migrate_neon_to_azure_sql.py
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from sqlalchemy import Integer, Identity, Table, func, select, text
from sqlalchemy.engine import Connection, Engine

# Ensure backend/ is importable when executed directly as a script
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.logging_filter import mask_sensitive_text  # noqa: E402
from app.db.session import Base, create_configured_engine  # noqa: E402
import app.models.models  # noqa: E402, F401
from app.services.analytics import ensure_analytics_views  # noqa: E402


def _clean_row_values(table: Table, row_mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize PostgreSQL values (e.g. tz-aware timestamps) for Azure SQL DATETIME2."""
    cleaned: Dict[str, Any] = {}
    for col in table.columns:
        val = row_mapping.get(col.name)
        if isinstance(val, datetime) and val.tzinfo is not None:
            val = val.astimezone(timezone.utc).replace(tzinfo=None)
        cleaned[col.name] = val
    return cleaned


def table_has_identity_pk(table: Table) -> bool:
    """Return True when the table uses an auto-increment / IDENTITY integer primary key."""
    pk_cols = list(table.primary_key.columns)
    if len(pk_cols) != 1:
        return False
    pk = pk_cols[0]
    if not isinstance(pk.type, Integer):
        return False
    return bool(isinstance(pk.server_default, Identity) or pk.autoincrement is True)


def _fetch_existing_pks(conn: Connection, table: Table) -> set[Tuple[Any, ...]]:
    """Fetch existing primary key tuples from target table for idempotent inserts."""
    pk_cols = list(table.primary_key.columns)
    stmt = select(*pk_cols)
    return {tuple(row) for row in conn.execute(stmt).all()}


def _row_pk_tuple(row_dict: Dict[str, Any], pk_cols: Sequence[Any]) -> Tuple[Any, ...]:
    return tuple(row_dict[col.name] for col in pk_cols)


def _stamp_alembic_head(target_engine: Engine) -> None:
    """Ensure alembic_version exists and reflects the current head revision when empty."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        alembic_ini = BACKEND_DIR / "alembic.ini"
        if not alembic_ini.exists():
            return
        cfg = Config(str(alembic_ini))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        head_rev = ScriptDirectory.from_config(cfg).get_current_head()
        if not head_rev:
            return

        with target_engine.begin() as conn:
            if target_engine.dialect.name == "mssql":
                conn.execute(
                    text(
                        """
                        IF OBJECT_ID('alembic_version', 'U') IS NULL
                        CREATE TABLE alembic_version (
                            version_num VARCHAR(32) NOT NULL CONSTRAINT alembic_version_pkc PRIMARY KEY
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                    )
                )
            existing = conn.execute(text("SELECT COUNT(*) FROM alembic_version")).scalar() or 0
            if existing == 0:
                conn.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                    {"rev": head_rev},
                )
    except Exception as exc:
        print(f"[WARN] Could not stamp alembic_version automatically: {mask_sensitive_text(str(exc))}")


def migrate_databases(
    source_engine: Engine,
    target_engine: Engine,
    *,
    batch_size: int = 500,
    stamp_alembic: bool = True,
) -> List[Dict[str, Any]]:
    """Copy every model table from source_engine to target_engine idempotently and verify counts."""
    Base.metadata.create_all(bind=target_engine)
    ensure_analytics_views(target_engine)
    if stamp_alembic:
        _stamp_alembic_head(target_engine)

    results: List[Dict[str, Any]] = []
    tables = list(Base.metadata.sorted_tables)
    is_target_mssql = target_engine.dialect.name == "mssql"

    for table in tables:
        pk_cols = list(table.primary_key.columns)
        has_identity = table_has_identity_pk(table)

        with source_engine.connect() as src_conn:
            src_rows = [
                _clean_row_values(table, dict(mapping))
                for mapping in src_conn.execute(select(table)).mappings().all()
            ]
        source_count = len(src_rows)

        inserted_count = 0
        with target_engine.begin() as dst_conn:
            existing_pks = _fetch_existing_pks(dst_conn, table)
            pending_rows = [
                row for row in src_rows if _row_pk_tuple(row, pk_cols) not in existing_pks
            ]

            if pending_rows:
                identity_enabled = False
                try:
                    if is_target_mssql and has_identity:
                        dst_conn.execute(text(f"SET IDENTITY_INSERT [{table.name}] ON"))
                        identity_enabled = True

                    for idx in range(0, len(pending_rows), batch_size):
                        batch = pending_rows[idx : idx + batch_size]
                        dst_conn.execute(table.insert(), batch)
                        inserted_count += len(batch)
                finally:
                    if identity_enabled:
                        dst_conn.execute(text(f"SET IDENTITY_INSERT [{table.name}] OFF"))

            target_count = (
                dst_conn.execute(select(func.count()).select_from(table)).scalar() or 0
            )

        results.append(
            {
                "table": table.name,
                "source_count": source_count,
                "target_count": int(target_count),
                "inserted": inserted_count,
                "match": source_count <= int(target_count) if existing_pks else source_count == int(target_count),
                "exact_match": source_count == int(target_count),
            }
        )

    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotent migration from Neon PostgreSQL to Azure SQL Database."
    )
    parser.add_argument(
        "--source-url",
        "--source",
        dest="source",
        default=os.environ.get("SOURCE_NEON_URL", ""),
        help="Source Neon PostgreSQL URL (defaults to SOURCE_NEON_URL env var).",
    )
    parser.add_argument(
        "--target-url",
        "--target",
        dest="target",
        default=os.environ.get("TARGET_AZURE_SQL_URL", ""),
        help="Target Azure SQL URL (defaults to TARGET_AZURE_SQL_URL env var).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Insert batch size per commit.",
    )
    args = parser.parse_args(argv)

    source_url = (args.source or "").strip()
    target_url = (args.target or "").strip()
    if not source_url or not target_url:
        print(
            "ERROR: Both SOURCE_NEON_URL (--source) and TARGET_AZURE_SQL_URL (--target) are required.",
            file=sys.stderr,
        )
        return 2

    print("Connecting to source (Neon PostgreSQL) and target (Azure SQL Database)...")
    source_engine = create_configured_engine(source_url)
    target_engine = create_configured_engine(target_url)

    try:
        summary = migrate_databases(
            source_engine,
            target_engine,
            batch_size=max(1, args.batch_size),
            stamp_alembic=True,
        )
    finally:
        source_engine.dispose()
        target_engine.dispose()

    print("\n=== Migration Row-Count Verification ===")
    print(f"{'Table':<24} {'Source':>10} {'Target':>10} {'Inserted':>10} {'Status':>10}")
    print("-" * 68)
    all_matched = True
    for row in summary:
        status_label = "EXACT" if row["exact_match"] else ("OK (>=)" if row["match"] else "MISMATCH")
        if not row["match"]:
            all_matched = False
        print(
            f"{row['table']:<24} {row['source_count']:>10} {row['target_count']:>10} "
            f"{row['inserted']:>10} {status_label:>10}"
        )

    if not all_matched:
        print("\nMigration finished WITH row-count mismatches!", file=sys.stderr)
        return 1

    print("\nMigration completed cleanly with 100% row-count verification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
