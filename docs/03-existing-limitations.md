# 3. Existing system limitations

This section covers **market incumbents** and **this repository’s current codebase**. Both matter: we are evolving an existing SIH stack, not starting from a blank Git history.

## 3.1 Incumbent ride-hailing limitations

| Limitation | Why it hurts |
|------------|----------------|
| OTP is the start gate | Does not bind the human operator to the enrolled driver identity |
| Pool products are pre-trip only | Empty seats after start stay empty |
| Sharing UX is driver- or platform-imposed | Passengers feel unsafe or ambushed |
| Safety is reactive SOS | No pre-ride protocol, little explainability |
| Matching opacity | Users cannot see delay, detour, or fare delta before they accept |
| Profile oversharing | Full identities in pool cars increase harassment risk |
| Single-occupancy economics | Cost and congestion do not improve |

## 3.2 Limitations in this repository (as-is)

Honest inventory of what exists today versus a production mobility platform.

### Frontend

- React/Vite SPA for passenger and driver (`src/`), useful for SIH demo, **not** a store-grade mobile client.
- Nested-router / mock-engine patterns exist; live map is radar-style, not a licensed SDK map.
- Flutter tree exists under `mobile_app/` but is not the documented system of record.
- No Next.js admin dashboard.

### Gateway

- Express (`server.ts`) reverse-proxies `/api/v1/*` to FastAPI with **standalone mock fallbacks**.
- Gateway fallbacks can diverge from FastAPI contracts (field names, IDs).
- No API gateway auth (JWT validation at edge), no WAF, no per-route rate limits beyond Helmet/CORS.

### FastAPI backend

- Routers exist: auth, rides, liveness, risk, consensus, fare, emergency, driver, dispatch, payment, notification, rating.
- `Ride` model is **1 driver + 1 primary `passenger_id`**. Extra occupants are not first-class `ride_passengers` rows with seat locks.
- `VehicleType` enum is `bike | auto | cab` — **van is missing**.
- Seat fields exist (`seats_total`, `seats_occupied`) but no reservation table / `SELECT … FOR UPDATE` story in schema comments.
- Default `DATABASE_URL` in Compose is **SQLite**, which cannot host PostGIS.

### Data & realtime

- Compose has **no PostgreSQL, Redis, OSRM, object store, or worker**.
- WebSocket manager in `rides.py` is in-process memory — not horizontally scalable.
- Telemetry table exists; streaming volume and retention policy are undefined.

### AI

- Risk engine: XGBoost + conformal uncertainty + ONNX — strong direction, currently trained on **synthetic** features unless real crime/lighting feeds are licensed.
- Liveness: MediaPipe + EAR + pose + texture heuristics — good MVP, **not** a certified PAD (presentation attack detection) product. Device biometric fallback authenticates the **device owner**, which the product spec itself says is not driver identity.

### Product / legal gaps

- No DPDP consent ledger, no biometric retention clock, no DPIA.
- Payment module is a stub relative to Razorpay/Cashfree + UPI + refunds + GST.
- Admin, fraud, complaints, and audit log tables are incomplete relative to the 20-entity target list.

## 3.3 What we keep vs replace

| Keep and harden | Replace / add |
|-----------------|---------------|
| FastAPI as domain API | PostgreSQL + PostGIS as system of record |
| Express as BFF/gateway | Redis for live state + seat holds |
| OSRM matching service | Dedicated OSRM container + map tiles |
| Risk + liveness engines | Enrollment gallery + cosine match; SHAP explanations |
| Consensus + mid-route request models | `ride_passengers` + seat reservations |
| React SPA for web/demo | Flutter/RN for production apps; Next.js admin |

## 3.4 Architectural debt that will break sharing if ignored

1. **One passenger column on `rides`.** Sharing requires a child table and a capacity check in the same transaction as insert.
2. **In-memory WebSockets.** Two FastAPI replicas will split ride rooms.
3. **SQLite.** No geography, weak concurrency for seat races.
4. **OTP stored in ride row.** Must be hashed, short-TTL, and gated on verification state machine.
5. **JSON blobs for votes and consent.** Acceptable for MVP, must become row-level votes for audit.
