# 16. Cybersecurity and privacy architecture

## 16.1 Threat model (abridged)

| Threat | Impact | Control |
|--------|--------|---------|
| Stolen JWT | Account takeover | Short access TTL, rotate refresh, device bind P1 |
| Seat race / join hijack | Overload vehicle | Authz + SQL holds + occupancy checks |
| OTP brute force | Start as wrong rider | 4–6 digit + lock + ride-scoped + rate limit |
| Fake driver | Passenger harm | KYC + liveness + plate OCR P1 |
| GPS spoof | Fake corridor | Map-match, accuracy, inertial P2, anomaly flags |
| PII scrape of co-riders | Harassment | Minimized cards, consent, rate limit search |
| Embedding leak | Biometric compromise | Encrypt, no raw storage, separate KMS |
| Admin abuse | Mass PII | RBAC, audit, break-glass |

## 16.2 AuthZ

- OAuth2-style passwordless OTP + JWT (not full OIDC until IdP exists).
- RBAC: passenger, driver, admin, safety_ops.
- Every ride-scoped call: `user is passenger_on_ride OR driver_on_ride OR admin`.
- Join offers: only searchers in geo cell, not global ride enumeration.

## 16.3 Transport and secrets

- TLS everywhere.
- Secrets in env / secret manager, never git.
- Gateway already has Helmet; add rate limit (express-rate-limit / reverse proxy).
- CORS: lock origins in production (`*` is demo-only).

## 16.4 Encryption

- At rest: Postgres TDE or disk encryption; column encryption for DL numbers and embeddings.
- In transit: TLS.
- OTP: hashed.
- Object storage: SSE, private buckets, short-lived signed URLs.

## 16.5 Privacy (DPDP)

- **Notice + consent** per purpose (`consents` table).
- **Minimization:** co-passenger card = display name, rating, verified, optional age **band**.
- **Retention:** see schema doc.
- **Rights:** export/erase APIs P1; legal hold on incidents.
- Risk model: no sensitive demographic features.
- Children’s data: no accounts under 18 without guardian flow (P1 policy).

## 16.6 Biometric policy

- Informed consent at enrollment.
- Purpose: driver identity match only.
- No sale, no ads, no sharing with occupants.
- Frames discarded after inference unless user opts into debug (24h).

## 16.7 Audit

- `audit_logs` for admin, verification outcomes, SOS, fare changes, consent.
- Correlation IDs from gateway through FastAPI.

## 16.8 Abuse and fraud

- Velocity: many SOS, many join rejects, many verify fails → queue for ops.
- Promo / payment fraud P1 with PG.
- Rating bombs: delay public rating, detect rings.

## 16.9 Legal feasibility flags (not legal advice)

- Taxi aggregator licences vary by state — launch city by city.
- Device biometrics APIs are OS-mediated; we never see fingerprint images (good).
- Face match **is** biometric processing under DPDP — DPIA before production.
- Emergency sharing with police: define lawful basis and minimization.
