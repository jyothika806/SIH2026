"""Create a non-overwriting PostgreSQL or SQLite backup before migration."""

import argparse
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url


def _sqlite_table_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        counts = {}
        for name in sorted(names):
            quoted_name = name.replace('"', '""')
            counts[name] = connection.execute(
                f'SELECT COUNT(*) FROM "{quoted_name}"'
            ).fetchone()[0]
        return counts
    finally:
        connection.close()


def _verify_sqlite_backup(source: Path, backup_path: Path) -> None:
    connection = sqlite3.connect(f"file:{backup_path.resolve().as_posix()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if integrity != ("ok",) or _sqlite_table_counts(source) != _sqlite_table_counts(backup_path):
        raise RuntimeError("SQLite backup verification failed.")


def _verify_postgres_backup(path: Path) -> None:
    pg_restore = shutil.which("pg_restore")
    if not pg_restore:
        raise RuntimeError("pg_restore is required to verify PostgreSQL backups.")
    result = subprocess.run(
        [pg_restore, "--list", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    if path.stat().st_size == 0 or not result.stdout.strip():
        raise RuntimeError("PostgreSQL backup archive verification failed.")


def backup(database_url: str, output: Path) -> None:
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Backup destination already exists; choose a new path.")
    output.parent.mkdir(parents=True, exist_ok=True)
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        source = Path(url.database or "").resolve()
        if not source.is_file():
            raise FileNotFoundError("SQLite database file does not exist.")
        source_db = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        destination_db = sqlite3.connect(str(output))
        try:
            source_db.backup(destination_db)
        finally:
            destination_db.close()
            source_db.close()
        _verify_sqlite_backup(source, output)
        return

    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise RuntimeError("pg_dump is required for PostgreSQL backups.")
    if not url.host or not url.database or not url.username:
        raise ValueError("DATABASE_URL must include PostgreSQL host, database, and user.")
    env = os.environ.copy()
    if url.password:
        env["PGPASSWORD"] = url.password
    command = [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--host",
        url.host,
        "--port",
        str(url.port or 5432),
        "--username",
        url.username,
        "--file",
        str(output),
        url.database,
    ]
    subprocess.run(command, env=env, check=True)
    _verify_postgres_backup(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        parser.error("Set DATABASE_URL in the environment.")
    backup(database_url, args.output)
    print(f"Backup created at {args.output.resolve()}")


if __name__ == "__main__":
    main()
