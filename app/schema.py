from __future__ import annotations

from sqlalchemy import text

from .extensions import db


def _sqlite_has_column(table: str, column: str) -> bool:
    rows = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def _sqlite_add_column(table: str, column: str, coldef: str) -> None:
    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}"))
    db.session.commit()


def ensure_sqlite_schema() -> None:
    """
    Minimal schema evolution helper for SQLite so existing demo DBs don't crash.
    Only adds missing columns (safe, additive).
    """
    uri = str(db.engine.url)
    if not uri.startswith("sqlite"):
        return

    # OrderFinance additive columns
    try:
        # table may not exist yet
        db.session.execute(text("SELECT 1 FROM order_finance LIMIT 1"))
    except Exception:
        db.session.rollback()
        return

    if not _sqlite_has_column("order_finance", "restaurant_settlement_status"):
        _sqlite_add_column("order_finance", "restaurant_settlement_status", "VARCHAR(40) NOT NULL DEFAULT 'pending'")
    if not _sqlite_has_column("order_finance", "rider_settlement_status"):
        _sqlite_add_column("order_finance", "rider_settlement_status", "VARCHAR(40) NOT NULL DEFAULT 'pending'")

