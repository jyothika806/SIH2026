# 18. Testing strategy

## 18.1 Layers

| Layer | What | Tooling |
|-------|------|---------|
| Unit | Fare, overlap score, capacity clamp, OTP hash | pytest, vitest |
| Contract | OpenAPI vs gateway mocks | schemathesis / Dredd |
| Integration | Postgres testcontainer: seat race | pytest-asyncio |
| API | Authz matrix, liveness state machine | pytest + httpx |
| Property | Never `confirmed_passengers > capacity` | hypothesis |
| Load | 1k concurrent location posts, 100 join races | k6 / locust |
| Security | OWASP API, JWT, IDOR on ride_id | ZAP + manual |
| Mobile / UI | Verify, SOS, vote, book | Playwright on SPA; later Maestro |
| Model | Feature-blocklist test (no gender column) | pytest |
| Liveness | Photo / video replay fixtures | pytest + sample media **internal** |

## 18.2 Seat race test (mandatory)

Two clients, one seat, simultaneous `mid-ride/request` → exactly one `held`, the other `409 SEAT_UNAVAILABLE`. Repeat 1e4 times in CI nightly.

## 18.3 Safety tests

- OTP remains hashed in DB.
- Unverified ride rejects `start-ride`.
- Passenger biometric cannot call driver verify success.
- SOS creates incident even if FCM fails.

## 18.4 Definition of done per feature

Code + schema migration + contract test + observability + privacy review checkbox for PII fields.
