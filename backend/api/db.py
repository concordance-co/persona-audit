"""Small shared database helpers for the serving layer.

Values are always parameterized in queries; identifiers (table names) come from
env config and must pass :func:`safe_identifier` before interpolation.
"""

from __future__ import annotations

import re

import psycopg

from backend.paths import DATABASE_URL_ENV, configured_database_url

__all__ = ["DATABASE_URL_ENV", "configured_database_url", "safe_identifier", "table_exists"]

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def safe_identifier(value: str) -> str:
    """Validate a SQL identifier (table/column name) sourced from configuration."""

    if not _IDENTIFIER_RE.match(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return value


def table_exists(conn: psycopg.Connection, table_name: str) -> bool:
    row = conn.execute("SELECT to_regclass(%s) AS table_name", (table_name,)).fetchone()
    return bool(row and row.get("table_name"))
