# 10. API endpoint documentation

Base: `https://{gateway}/api/v1`  
Auth: `Authorization: Bearer <access_jwt>` unless noted.  
Idempotency: `Idempotency-Key` on POST book, join, pay.  
Errors: `{ "error": { "code", "message", "details" } }` with stable codes.

Existing FastAPI routers remain; names below are the **target contract**. Where current paths differ, both are listed.

## 10.1 Auth

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/otp/request` | Send login OTP |
| POST | `/auth/otp/verify` | Returns access + refresh |
| POST | `/auth/refresh` | Rotate tokens |
| POST | `/auth/logout` | Revoke refresh |
| GET | `/auth/me` | Current user + roles |

## 10.2 Passenger profile

| Method | Path | Purpose |
|--------|------|---------|
| GET/PATCH | `/passenger/profile` | Display name, consents |
| PUT | `/passenger/emergency-contacts` | Trusted contacts |

## 10.3 Booking and trip (passenger)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/passenger/book` | Solo or group-accept. Body: pickup, dropoff, mode, seats. Returns `ride_id` or `request_id` |
| GET | `/passenger/quotes` | Fare + risk + consolidation |
| GET | `/passenger/active-rides` | Eligible mid-ride offers |
| POST | `/passenger/mid-ride/request` | Join; creates hold |
| POST | `/passenger/mid-ride/consent` | Occupant vote |
| GET | `/passenger/risk-score` | Pre-ride assessment |
| POST | `/passenger/status` | Location heartbeat |
| GET | `/passenger/rides/{id}` | Status (replaces ad-hoc GET `/passenger/status/:id`) |
| POST | `/passenger/sos` | Emergency |
| POST | `/passenger/verify-driver` | Starts liveness session for assigned ride |

## 10.4 Driver

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/driver/status` | online + mode |
| POST | `/driver/seats` | vacant 1–7 clamped |
| POST | `/driver/location` | GPS stream |
| GET | `/driver/offers` | Incoming books + joins |
| POST | `/driver/offers/{id}/accept` | Accept dispatch |
| POST | `/driver/accept-waypoint` | After occupant consent |
| POST | `/driver/verify-identity` | Frame or session token |
| POST | `/driver/start-ride` | OTP |
| POST | `/driver/complete` | End trip |
| POST | `/driver/sos` | Driver emergency |
| GET | `/driver/earnings` | P1 |

## 10.5 Liveness (existing, keep)

| Method | Path |
|--------|------|
| POST | `/liveness/request-verification` |
| POST | `/liveness/verify-driver-scan` |
| POST | `/liveness/biometric-fallback` |
| GET | `/liveness/otp-status/{ride_id}` |
| WS | `/liveness/ws/verification/{verification_id}` |

**Rule:** `/driver/verify-identity` is a BFF facade over `/liveness/*` so mobile has one verb; it must not bypass the state machine.

## 10.6 Matching / groups

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/match/preview` | Group + modal suggestions for a search |
| POST | `/match/groups/{id}/decide` | accept/reject |
| GET | `/rides/{id}/corridor` | Remaining polyline |

## 10.7 Risk, consensus, fare, emergency (existing)

Keep:

- `POST /risk/evaluate-advanced`, `POST /risk/evaluate-batch`
- `POST /consensus/...` (internal; passenger consent is the public API)
- `POST /fare/...`
- `POST /emergency/...`
- `POST /payment/...` (mock until PG)
- `POST /notification/...`
- `POST /rating/...`

## 10.8 Admin (P1)

`/admin/users`, `/admin/drivers`, `/admin/rides`, `/admin/incidents`, `/admin/verifications`, `/admin/audit` — role `admin` or `safety_ops`.

## 10.9 Realtime events (WS)

`WS /realtime/rides/{ride_id}`

Events: `location`, `eta`, `geofence`, `consent_required`, `waypoint_offer`, `otp_unlocked`, `risk_update`, `sos`.

## 10.10 Representative payloads

### POST `/passenger/book`

```json
{
  "pickup": { "lat": 12.9716, "lng": 77.5946, "address": "MG Road" },
  "dropoff": { "lat": 12.9352, "lng": 77.6245, "address": "Indiranagar" },
  "vehicle_type": "cab",
  "seats_required": 1,
  "group_id": null
}
```

### GET `/passenger/active-rides` item

```json
{
  "ride_id": "…",
  "vehicle_type": "cab",
  "open_seats": 2,
  "detour_seconds": 120,
  "extra_fare_inr": 48,
  "driver": { "display_name": "Rajesh", "age_band": "30-35", "rating": 4.8, "verified": true },
  "occupants_count": 1,
  "safety_level": "low"
}
```

### POST `/passenger/mid-ride/consent`

```json
{ "request_id": "…", "ride_id": "…", "decision": "accept" }
```

## 10.11 Versioning

`/api/v1` only. Breaking changes require `/v2`. Gateway mock handlers must be updated in the same PR as FastAPI or demos desync (current debt).
