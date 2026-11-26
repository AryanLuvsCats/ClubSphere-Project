"""Sensitive data masking filter for Python logging.

Prevents authentication tokens, passwords, cookies, and database credentials
from leaking into application logs, stdout, or APM collectors.
"""
import logging
import re
from typing import Any

# Regex patterns for sensitive credentials
SENSITIVE_PATTERNS = [
    # Bearer tokens (JWT or opaque tokens)
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    # Passwords in JSON / query / form structures
    (
        re.compile(
            r"""(["']?password["']?\s*[:=]\s*["'])[^"'\r\n]+(["'])""",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\2",
    ),
    # Refresh / session cookies
    (
        re.compile(r"(clubsphere_refresh=)[^;\s]+", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # Database URLs containing passwords (PostgreSQL & Azure SQL / MSSQL)
    (
        re.compile(
            r"((?:postgres(?:ql)?|mssql)(?:\+[a-z0-9]+)?://[^:]+:)([^@]+)(@)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\3",
    ),
    # ODBC PWD=... and Azure Storage AccountKey=... secrets
    (
        re.compile(r"((?:PWD|AccountKey)\s*=\s*)([^;\r\n]+)", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    # Secret keys in configs
    (
        re.compile(
            r"""(["']?jwt_secret_key["']?\s*[:=]\s*["'])[^"'\r\n]+(["'])""",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\2",
    ),
]


def mask_sensitive_text(text: str) -> str:
    """Apply regex masks to remove sensitive data from a string."""
    if not isinstance(text, str):
        return text
    masked = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked


class SensitiveDataFilter(logging.Filter):
    """Logging filter that redacts sensitive values from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_text(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (mask_sensitive_text(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_sensitive_text(arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


def setup_secure_logging() -> None:
    """Attach the SensitiveDataFilter to root and clubsphere loggers."""
    filter_instance = SensitiveDataFilter()
    root_logger = logging.getLogger()
    if not any(isinstance(f, SensitiveDataFilter) for f in root_logger.filters):
        root_logger.addFilter(filter_instance)

    app_logger = logging.getLogger("clubsphere")
    if not any(isinstance(f, SensitiveDataFilter) for f in app_logger.filters):
        app_logger.addFilter(filter_instance)

