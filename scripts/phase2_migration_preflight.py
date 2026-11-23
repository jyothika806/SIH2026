"""Read-only inventory and Phase 2 migration preflight; never applies a migration."""

import argparse
import json
import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from backend.app.api.v1.core.config import get_settings
from backend.app.services.phone_numbers import normalize_phone


def _account_phone_counts(rows) -> dict[str, int]:
    region = get_settings().phone_default_region
    normalized_user_ids = {}
    changed = 0
    invalid = 0
    collision_rows = set()
    for user_id, phone in rows:
        try:
            normalized = normalize_phone(phone, region)
        except (TypeError, ValueError):
            invalid += 1
            continue
        if normalized != phone:
            changed += 1
        previous_user_id = normalized_user_ids.get(normalized)
        if previous_user_id is not None and previous_user_id != user_id:
            collision_rows.update((previous_user_id, user_id))
        normalized_user_ids[normalized] = user_id
    return {
        "account_phone_normalization_needed": changed,
        "invalid_account_phones": invalid,
        "account_phone_collision_rows": len(collision_rows),
    }


def _read_only_sqlite(path: Path) -> dict:
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in sorted(tables)
        }
        sensitive_counts = {}
        for table in ("rides", "otp_logs"):
            if table in counts:
                columns = {
                    row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
                }
                for column, label in (("otp", "plaintext_otp_values"), ("otp_hash", "otp_hash_values")):
                    if column in columns:
                        sensitive_counts[f"{table}_{label}"] = connection.execute(
                            f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NOT NULL'
                        ).fetchone()[0]
                if table == "otp_logs" and {"phone", "otp_hash", "consumed_at"}.issubset(columns):
                    sensitive_counts["duplicate_active_otp_phone_groups"] = connection.execute(
                        "SELECT COUNT(*) FROM (SELECT phone FROM otp_logs "
                        "WHERE consumed_at IS NULL AND otp_hash IS NOT NULL "
                        "GROUP BY phone HAVING COUNT(*) > 1)"
                    ).fetchone()[0]
                if table == "rides" and "otp_unlocked" in columns:
                    sensitive_counts["rides_unlocked_otp_states"] = connection.execute(
                        'SELECT COUNT(*) FROM "rides" WHERE otp_unlocked = 1'
                    ).fetchone()[0]
        if "users" in counts and "phone" in {
            row[1] for row in connection.execute('PRAGMA table_info("users")')
        }:
            sensitive_counts.update(
                _account_phone_counts(
                    connection.execute("SELECT id, phone FROM users").fetchall()
                )
            )
        return {
            "dialect": "sqlite",
            "direct_phase2_upgrade_supported": False,
            "tables": counts,
            "sensitive_value_counts": sensitive_counts,
            "migration_action": "export and convert to a fresh PostgreSQL/PostGIS database",
        }
    finally:
        connection.close()


def _read_only_database(url: str) -> dict:
    parsed = make_url(url)
    if parsed.drivername.startswith("sqlite"):
        sqlite_path = Path(parsed.database or "")
        if not sqlite_path.is_absolute():
            sqlite_path = Path.cwd() / sqlite_path
        if not sqlite_path.exists():
            raise FileNotFoundError("SQLite database file does not exist")
        return _read_only_sqlite(sqlite_path)
    sync_url = url.replace("+asyncpg", "")
    engine = create_engine(sync_url, pool_pre_ping=True)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        counts = {}
        with engine.connect() as connection:
            for table in sorted(tables):
                counts[table] = connection.execute(
                    text(f'SELECT COUNT(*) FROM "{table}"')
                ).scalar_one()
            sensitive_counts = {}
            for table in ("rides", "otp_logs"):
                if table not in tables:
                    continue
                columns = {
                    item["name"] for item in inspector.get_columns(table)
                }
                for column, label in (
                    ("otp", "plaintext_otp_values"),
                    ("otp_hash", "otp_hash_values"),
                ):
                    if column in columns:
                        sensitive_counts[f"{table}_{label}"] = connection.execute(
                            text(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" IS NOT NULL')
                        ).scalar_one()
                if table == "otp_logs" and {"phone", "otp_hash", "consumed_at"}.issubset(columns):
                    sensitive_counts["duplicate_active_otp_phone_groups"] = connection.execute(
                        text(
                            "SELECT COUNT(*) FROM (SELECT phone FROM otp_logs "
                            "WHERE consumed_at IS NULL AND otp_hash IS NOT NULL "
                            "GROUP BY phone HAVING COUNT(*) > 1) AS active_otp_conflicts"
                        )
                    ).scalar_one()
                if table == "rides" and "otp_unlocked" in columns:
                    sensitive_counts["rides_unlocked_otp_states"] = connection.execute(
                        text('SELECT COUNT(*) FROM "rides" WHERE otp_unlocked IS TRUE')
                    ).scalar_one()
            if "users" in tables and "phone" in {
                item["name"] for item in inspector.get_columns("users")
            }:
                sensitive_counts.update(
                    _account_phone_counts(
                        connection.execute(text("SELECT id, phone FROM users")).all()
                    )
                )
        return {
            "dialect": parsed.drivername,
            "tables": counts,
            "sensitive_value_counts": sensitive_counts,
            "has_alembic_version": "alembic_version" in tables,
            "migration_action": "review schema, restore a verified backup, then plan the upgrade",
        }
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required acknowledgement: this command only reads database metadata and counts.",
    )
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("Pass --dry-run; this tool has no migration/apply mode.")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("Set DATABASE_URL without placing it in command-line arguments.")
    print(json.dumps(_read_only_database(database_url), indent=2))


if __name__ == "__main__":
    main()
