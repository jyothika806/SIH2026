# 4. Proposed system

## 4.1 One-sentence design

A modular mobility platform: **clients → Express BFF → FastAPI domain services → PostgreSQL/PostGIS + Redis + object storage**, with **OSRM** for road-network routes, **workers** for matching and risk, and **strict consent + seat transactions** around every shared trip.

## 4.2 Capability map

```text
[Passenger] [Driver] [Admin]
        \      |      /
         Express BFF / WS fan-in
                  |
         FastAPI domain API
         /    |     |     \      \
   Identity  Trip  Match  Safety  Money
      |       |      |      |       |
   Auth/KYC  Rides  OSRM  Risk   Payments
   Liveness  Seats  Group  SOS    Ledger
             Join   Modal  Dev.
```

## 4.3 Four core systems

### Core 1 — Dynamic mid-ride joining

When a vehicle is `IN_PROGRESS` and `open_seats > 0`, the matcher continuously evaluates nearby searchers against the **remaining polyline**, not the original origin. Eligibility:

- Capacity after a **temporary seat hold**.
- Pickup within a geofence of the live corridor (configurable, default 300–500 m road distance).
- Drop-off compatible (along remaining route or bounded extra destination).
- Detour ≤ `max_detour_seconds` (default 300s).
- Risk protocol allows pooling (e.g. not Red without extra controls).
- Joiner and occupants have sharing consent flags.

Then: joiner request → occupant vote (timeout) → driver waypoint approval → fare recalculation → confirm. Any reject or timeout **releases the seat hold** and leaves the original trip untouched.

### Core 2 — Intelligent pre-ride group matching

When several `SEARCHING` intents share a corridor, clustering + route overlap produces a **group offer**. Each passenger accepts independently. Driver is offered a multi-stop itinerary with bonus. Confirm only when:

- `accepted_passengers ≤ vehicle.capacity`
- All holds still valid
- Pickup sequence from optimizer is within detour budget

Modal consolidation (2 bikes → 1 auto; 5 bikes or auto+bike → cab/van) is a **specialization** of this engine, not a separate product.

### Core 3 — AI ride safety prediction

A model scores the trip **before confirm** and **on telemetry ticks**. Output is `{score, level, indicators[], recommended_protocol, uncertainty}`. Protocols change product behavior (OTP policy, tracking intensity, SOS hint). The UI must show: *“This is not a guarantee of safety.”* Features exclude gender, caste, religion, and raw age as risk inputs.

### Core 4 — Driver face verification with liveness

Enrollment at onboarding stores an encrypted embedding, not a public photo gallery. At pickup, passenger taps Verify → driver app runs liveness + match against enrollment. Success **unlocks hashed OTP** to both parties. Fail ×2 → support/cancel path. Device biometrics are **only** a degraded driver-app unlock after liveness failure in low light, and **never** shown to the passenger as “identity verified.”

## 4.4 Supporting systems

- Auth: phone OTP + JWT access/refresh, RBAC (passenger, driver, admin, safety_ops).
- Notifications: FCM + SMS fallback + in-app + WebSocket events.
- Payments: authorize on confirm, capture on complete, split fare per `fare_legs`.
- Emergency: 5s SOS, trusted contacts, incident case for ops.
- Admin: live map of rides, verification queues, incident desk.

## 4.5 Explicit non-goals for MVP

- Certified ISO 30107-3 PAD.
- Real municipal crime heatmaps without a data license.
- Fully automatic driver penalties from one GPS glitch.
- Cross-city roaming and intermodal transit tickets.
- Marketplace of third-party fleets (Phase 7+).
