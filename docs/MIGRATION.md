# Phase 2 database migration and recovery

This guide covers a fresh PostgreSQL/PostGIS installation, an existing PostgreSQL database, and SQLite. No migration has been run against an existing or production database by this implementation.

## Before any database change

1. Identify the exact environment and database; never use production credentials for tests.
2. Run `python scripts/phase2_migration_preflight.py` with the target `DATABASE_URL`. The command is read-only. Save its JSON output and review the schema, table counts, and sensitive-value counts. It does not print OTP or licence values.
3. Make a separate, access-controlled backup with `python scripts/backup_phase2.py --output <new-backup-path>`. The script refuses to overwrite a file. PostgreSQL backups use `pg_dump`; SQLite backups use the SQLite backup API. Backups may contain legacy plaintext OTPs and licence identifiers: encrypt and tightly restrict them.
4. Restore the backup to an isolated database and verify that it is readable before requesting approval for a migration. Do not set migration acknowledgement variables without explicit approval and a verified backup.
5. Test the exact procedure against a staging clone and record row counts before and after. No production migration is authorized by this document.

## Fresh PostgreSQL/PostGIS database

Use an empty database with PostGIS installed and the production secrets configured. `0001_fresh_baseline` refuses to run when user tables already exist; do not treat that refusal as an invitation to drop tables. On a confirmed empty database, run `alembic upgrade head`. The baseline creates the existing ORM schema and the Phase 2 migration adds its tables and constraints. The application does not create schema on startup.

## Existing PostgreSQL database

The migration requires the legacy `users`, `rides`, `otp_logs`, and `driver_profiles` tables and validates active-booking, seat-count, duplicate active OTP, and phone-normalization invariants before changing data. It is not a general schema reconciler. The read-only preflight counts plaintext OTP values, OTP hashes, unlocked ride OTP states, legacy licence values, and account phone numbers requiring canonicalization without printing their contents. Duplicate active challenges, invalid phone values, and phone collisions fail preflight; the migration never deletes accounts or resolves conflicts automatically.

Do not run the fresh baseline against an existing populated database. Inspect the preflight report and schema manually, confirm that it matches the migration's expected legacy schema, and test against a restored clone. If an existing database has no Alembic revision, an operator must separately verify its schema before stamping it as `0001_fresh_baseline`; stamping is not schema validation. If the schema differs, stop and write/review a dedicated conversion migration rather than guessing.

When existing OTP plaintext, hashes, unlocked ride OTP states, licence values, or non-canonical account phones are found, the migration requires both `PHASE2_BACKUP_ACKNOWLEDGED=YES` and `PHASE2_ALLOW_IRREVERSIBLE_MIGRATION=YES`. These flags are deliberate operator gates, not routine deployment settings. The migration nulls outstanding OTP credentials and unlock state and never copies plaintext OTPs to hashed fields. It canonicalizes account phone numbers only after proving the values are valid and collision-free. It encrypts legacy licence values using `FERNET_KEY` and writes only the last four characters separately. Any malformed or undecryptable value aborts the transaction.

Before editing or applying migration `0002`, verify its revision history in every shared environment. If it has been applied outside a disposable test database, do not rewrite it; preserve it and create a new forward-only migration. Never automatically delete duplicate active OTP challenges.

## SQLite

SQLite is inspected by the read-only preflight and can be backed up, but direct Phase 2 upgrades are unsupported. Alembic deliberately refuses SQLite because its schema, PostGIS geometry, constraints, and legacy data cannot be safely converted by this migration. No automatic SQLite-to-PostgreSQL converter is included. Preserve the SQLite source and backup, map and validate every table in an isolated conversion project, invalidate OTPs, encrypt licence data, compare row counts and application invariants, and obtain review before cutover. Never point the PostgreSQL baseline at a SQLite or populated database.

## Disposable tests (no Alembic migration)

Backend integration tests accept only the loopback `phase2_test` database on port `55432`; they create a unique temporary schema from ORM metadata and drop that schema after each test. Browser tests accept only the loopback `phase2_e2e` database on the same port. Their test-only backend setting creates ORM tables in that disposable database at startup; it does not run Alembic. The Playwright configuration also starts loopback-only Redis, SMS capture, and a deterministic OSRM fixture. Do not point either suite at a project, shared, or production database.

Once those disposable services are running, the exact commands are:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://phase2_test:phase2-test-only@127.0.0.1:55432/phase2_test"
python -m pytest -q backend/tests
$env:PHASE2_E2E_READY = "1"
npm run test:e2e
```

## Rollback and recovery

Alembic downgrade is intentionally disabled: invalidated OTPs must never be restored, and the migration cannot safely reconstruct the previous application state. Recovery means restoring a verified backup to a separate, isolated database and applying a sanitization/conversion procedure before any application can connect:

```sql
UPDATE otp_logs
SET otp = NULL, otp_hash = NULL, consumed_at = CURRENT_TIMESTAMP;

UPDATE rides
SET otp = NULL, otp_hash = NULL, otp_unlocked = FALSE,
    otp_expires_at = NULL, otp_consumed_at = CURRENT_TIMESTAMP;
```

These statements illustrate the Phase 2 schema. Before running them, inspect the restored schema and adapt for columns that are absent; clear every plaintext or hashed OTP field, expiry, and unlocked state that exists. Independently verify the sanitized rows before any application can connect. Re-encrypt any restored plaintext licence data before service resumes. Keep the original backup quarantined under the retention policy; do not use it as an online rollback target.
