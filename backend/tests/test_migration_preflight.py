import sqlite3

from scripts.backup_phase2 import backup
from scripts.phase2_migration_preflight import _read_only_database


def test_sqlite_preflight_reports_counts_without_reading_plaintext_otp(tmp_path):
    database = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE rides (id INTEGER, otp TEXT)")
    connection.execute("INSERT INTO rides VALUES (1, 'secret-otp')")
    connection.commit()
    connection.close()

    report = _read_only_database(f"sqlite:///{database.as_posix()}")

    assert report["direct_phase2_upgrade_supported"] is False
    assert report["sensitive_value_counts"]["rides_plaintext_otp_values"] == 1
    assert "secret-otp" not in repr(report)


def test_sqlite_backup_is_non_overwriting_and_restorable(tmp_path):
    source = tmp_path / "source.sqlite"
    connection = sqlite3.connect(source)
    connection.execute("CREATE TABLE rides (id INTEGER, otp TEXT)")
    connection.execute("INSERT INTO rides VALUES (1, NULL)")
    connection.commit()
    connection.close()
    destination = tmp_path / "backup.sqlite"

    backup(f"sqlite:///{source.as_posix()}", destination)

    restored = sqlite3.connect(destination)
    assert restored.execute("SELECT COUNT(*) FROM rides").fetchone()[0] == 1
    restored.close()
