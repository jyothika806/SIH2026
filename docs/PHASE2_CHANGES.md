# Phase 2 implementation summary

Phase 2 adds security and lifecycle foundations only. It does not implement ride sharing, pooling, or Phase 3 features.

## Added behavior

- OTP verification uses purpose-bound HMAC hashes; plaintext codes are not logged or migrated. OTP release is gated by a successful, unexpired server-side identity/liveness attempt. OTP status responses are non-cacheable.
- Login JWTs use the actual `sub` claim and validate signature, issuer, audience, type, issue time, and expiry. Access-token lifetime is configurable and defaults to 15 minutes. The frontend keeps the access token in memory only, clears it on logout or HTTP 401, and requires re-authentication after a page reload.
- Login phone numbers use canonical E.164 form. OTP issuance locks the registered user row and uses a database partial unique index for one active challenge; expired/outstanding challenges are invalidated before replacement. Migration preflight rejects duplicate active challenges and phone collisions.
- SMS delivery has no fake-success fallback. Production startup requires real provider credentials; the development OTP path is restricted to development/test.
- Driver licence records are encrypted and masked. Manual Parivahan reviews retain source, reference, timestamp, reviewer, and approved/rejected/unavailable outcome. Missing or incomplete evidence blocks dispatch. DigiLocker remains disabled pending authorized credentials.
- Vehicle-class mappings remain configurable. The reviewed flag defaults to false, so uncertain mappings block dispatch rather than silently approving drivers.
- Drivers whose existing profile is unverified remain present but are marked pending; re-verification of licence, consent, identity template, and profile approval is required before dispatch.
- Booking search expiry and the 60-second driver seat hold are separate states. A seat-hold expiry releases the driver and returns a still-valid passenger booking to search; it does not cancel that booking.
- Biometric operations fail closed when no authorized model is configured. Raw face frames are not logged or stored by the verification UI.
- Consent revocation cancels outstanding verification attempts and invalidates ride OTP state in the same database transaction. Biometric templates are purged after the configured retention period with restart-safe audit logging; licence evidence older than its configured revalidation period blocks dispatch.
- Admin routes check the account's current database role. Public admin registration is unavailable; provisioning is an operator-only, explicitly confirmed CLI operation with an audit event.
- Production requires Redis for authentication rate limiting and fails closed if Redis is missing or unavailable. Non-production may use the bounded database fallback, whose stale buckets are periodically removed.
- Gateway fallbacks for driver registration/status and ride start/verification do not report verification, dispatch, or trip-start success when FastAPI is unavailable; sample tracking marks liveness unavailable.
- Existing ride, pooling, and mid-route passenger API behavior is preserved; only the passenger OTP retrieval method was added.

## Configuration and dependencies

Production needs PostgreSQL with PostGIS, Redis for shared rate limits, a valid `JWT_SECRET_KEY`, `OTP_HMAC_KEY`, `LICENCE_HMAC_KEY`, `FERNET_KEY`, and real SMS provider credentials. Keep secrets in the deployment secret manager; `.env.example` contains placeholders only. DigiLocker client credentials and an authorized, validated identity model are not available in this repository.

`LICENCE_CLASS_MAP_REVIEWED` must remain false until a qualified reviewer signs off on the region- and category-specific mapping. Thresholds in `FACE_THRESHOLDS.md` are configuration, not certification or proof of identity.

## Operational limits

No positive biometric verification or real OTP-release flow can be demonstrated without the authorized model and credentials. Do not substitute fixture data or mock success. The backend tests exercise fail-closed verification/start behavior and lifecycle transitions; see the test report for the exact results and skipped integration checks. SQLite upgrades are intentionally unsupported; see `MIGRATION.md`.
