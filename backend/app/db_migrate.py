"""
Minimal non-destructive schema migration for SQLite.

There's no Alembic in this project, and `Base.metadata.create_all()` only
creates tables that don't exist yet - it never alters an existing table, so
adding a column to a model (as this stage did for User and AuditLog) would
otherwise silently do nothing on a database file created before the change,
and every query touching the new column would fail. This adds exactly the
columns listed below when missing, and never drops or rewrites existing data.

This is a deliberate, scoped stand-in for a real migration tool - fine for a
handful of additive columns, not a substitute for Alembic if the schema
keeps evolving.
"""
import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# (table, column, DDL type + default). Order doesn't matter within a table.
ADDITIVE_COLUMNS = [
    ("users", "is_active", "BOOLEAN DEFAULT 1"),
    ("users", "failed_login_attempts", "INTEGER DEFAULT 0"),
    ("users", "locked_until", "TIMESTAMP"),
    ("users", "created_at", "TIMESTAMP"),
    ("audit_logs", "resource_type", "TEXT"),
    ("audit_logs", "resource_id", "TEXT"),
    ("audit_logs", "details", "TEXT"),
    ("audit_logs", "correlation_id", "TEXT"),
    ("evidence", "previous_hash", "TEXT DEFAULT ''"),
]


def run_additive_migration(engine: Engine):
    with engine.connect() as conn:
        existing_tables = {row[0] for row in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
        for table, column, ddl_type in ADDITIVE_COLUMNS:
            if table not in existing_tables:
                continue  # create_all() will have made it with the column already
            cols = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
            if column in cols:
                continue
            logger.warning(f"[MIGRATE] Adding missing column {table}.{column}")
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
        conn.commit()
