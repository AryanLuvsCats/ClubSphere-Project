"""Cross-dialect SQLAlchemy column types and SQL expressions for Azure SQL (T-SQL), PostgreSQL, and SQLite."""

from sqlalchemy import DateTime, JSON, String, Text, Uuid
from sqlalchemy.dialects import mssql
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql import expression


def TSQLUnicode(length: int):
    """Variable-length Unicode string compiling to NVARCHAR(length) on Azure SQL."""
    return String(length).with_variant(mssql.NVARCHAR(length), "mssql")


TSQLText = Text().with_variant(mssql.NVARCHAR(None), "mssql")
TSQLDateTime = DateTime().with_variant(mssql.DATETIME2(), "mssql")
TSQLJson = JSON()
TSQLUuid = Uuid(as_uuid=False).with_variant(mssql.CHAR(36), "mssql")


class utcnow_sql(expression.FunctionElement):
    """Cross-dialect server-side UTC timestamp expression."""

    type = DateTime()
    inherit_cache = True


@compiles(utcnow_sql, "mssql")
def _compile_utcnow_mssql(element, compiler, **kw):
    return "SYSUTCDATETIME()"


@compiles(utcnow_sql, "postgresql")
def _compile_utcnow_postgresql(element, compiler, **kw):
    return "(NOW() AT TIME ZONE 'utc')"


@compiles(utcnow_sql, "sqlite")
def _compile_utcnow_sqlite(element, compiler, **kw):
    return "CURRENT_TIMESTAMP"


@compiles(utcnow_sql)
def _compile_utcnow_default(element, compiler, **kw):
    return "CURRENT_TIMESTAMP"
