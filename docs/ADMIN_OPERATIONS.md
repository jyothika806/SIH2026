# Phase 2 administration and re-verification

## Driver account handling

Existing driver users and profile rows are preserved. The upgrade marks unverified profiles `pending`; it does not delete or silently approve accounts. Dispatch checks the driver's active account, profile approval, licence evidence, applicable configured vehicle class, commercial endorsement policy, biometric consent, and active identity template.

Re-verify an existing driver before enabling dispatch:

1. Confirm the driver's account and profile identity through the organization's approved process.
2. Record informed biometric consent and its current text version.
3. Review the current licence through the authorized Parivahan/manual process. Record the source, reference, date/time, reviewer, outcome, class codes, endorsement, and expiry. A screenshot hash alone is not proof of validity.
4. Enroll and validate an identity template only through an authorized, configured model. No local or device-only check can approve identity.
5. Confirm the legal class mapping has been reviewed for the operating region and vehicle category.
6. Use the admin eligibility endpoint to inspect missing checks. Approve dispatch only after every check passes; record and retain the audit event.

An approved licence alone does not set the driver profile to verified. A rejected or unavailable verification remains non-dispatchable. Correct the underlying evidence and perform a new review rather than editing audit history.

## Admin API controls

The `/admin` endpoints require an authenticated account, then load the account from the database and verify its current role is `admin`; the JWT role claim alone is not authorization. Public registration accepts only passenger and driver roles. There is no public admin-registration endpoint.

Provisioning is an operator-only CLI action for an existing active account. Set `ADMIN_PROVISIONING_OPERATOR` to the operator's auditable identity and use the explicitly selected PostgreSQL URL:

```powershell
$env:ADMIN_PROVISIONING_OPERATOR = "operator-ticket-or-identity"
$env:ADMIN_PROVISION_DATABASE_URL = "<approved PostgreSQL DSN from secret storage>"
$env:ADMIN_PROVISION_TARGET_PHONE = "+14155552671"
python -m backend.scripts.provision_admin --confirm PROVISION-ADMIN
```

The command refuses missing operator identity, non-PostgreSQL URLs, unknown or inactive accounts, and missing confirmation. It writes an audit event in the same transaction as the role change. Keep the database URL in an approved secret store and never run this command against a production database without a separate operational authorization.

Licence review creates an evidence record with explicit `approved`, `rejected`, or `unavailable` outcome; it does not by itself enable dispatch. A licence review older than `LICENCE_REVALIDATION_DAYS` (default 180) blocks dispatch until reviewed again. Template activation requires an enrollment score at or above the configured threshold. Dispatch approval re-evaluates all eligibility rules server-side.

Revoking biometric consent atomically revokes active consent rows, cancels pending or prior verification attempts, deactivates templates, and invalidates outstanding ride OTP fields. The audit event is retained; raw face frames are not retained.

Restrict admin credentials, monitor audit events, and do not put licence numbers, birth dates, OTP values, embeddings, or raw image data in support tickets or logs. Manual review must follow the organization's legal and privacy retention policies.

## Unavailable dependencies

DigiLocker is disabled until authorized credentials and access are provisioned. The identity model is not configured in this repository; therefore, identity verification, OTP release, and dispatch remain blocked until an approved verifier is deployed and tested. Do not bypass these controls to onboard drivers.
