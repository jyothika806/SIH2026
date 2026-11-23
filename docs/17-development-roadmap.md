# 17. Development roadmap

Implementation **starts only after approval** of [21-gaps-mvp-and-approval.md](./21-gaps-mvp-and-approval.md).

## Phase 1 — Requirements and design (this pack)

- Architecture, schema, APIs, MVP cut. **Current phase.**

## Phase 2 — Core ride booking

- Postgres + PostGIS + Redis in Compose.
- Auth OTP, profiles, vehicles including **van**.
- `rides` + `ride_passengers` + dispatch accept.
- Map display + location WS.
- React SPA wired to **real** APIs (retire silent mock divergence).

## Phase 3 — Intelligent sharing

- Seat reservations + idempotency.
- Mid-ride join + unanimous consent + driver waypoint.
- Pre-ride group preview + modal consolidation.
- Fare split display.

## Phase 4 — AI safety engine

- Persist assessments; wire pre-ride card to ONNX.
- Deviation monitor + siren protocol.
- SHAP/text explanations; disclaimer copy.
- Stop claiming production crime AI until data license.

## Phase 5 — Driver verification

- Enrollment + trip liveness.
- OTP hash + lock UI both apps.
- Fail-closed fallback policy as approved.
- Support/cancel path.

## Phase 6 — Admin and analytics

- Next.js or SPA admin: rides, incidents, verify queue.
- Audit search, basic occupancy dashboards.

## Phase 7 — Test and deploy

- See [18-testing-strategy.md](./18-testing-strategy.md) and [19-deployment-architecture.md](./19-deployment-architecture.md).

## Suggested calendar (indicative, 1 squad)

| Phase | Time |
|-------|------|
| 1 | Done when you approve |
| 2 | 3–4 weeks |
| 3 | 3 weeks |
| 4 | 2 weeks (model already exists) |
| 5 | 2 weeks |
| 6 | 2 weeks |
| 7 | 2 weeks parallel from phase 2 |

SIH demo slice: Phase 2+3+5 happy paths on Compose, mocks only when upstream down **and labeled**.
