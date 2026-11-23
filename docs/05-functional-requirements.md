# 5. Functional requirements

IDs use `FR-<area>-<nn>`. Priority: **P0** MVP, **P1** production hardening, **P2** advanced.

## 5.1 Identity and profiles

| ID | Requirement | P |
|----|-------------|---|
| FR-ID-01 | Users register with phone OTP. Email optional. | P0 |
| FR-ID-02 | Roles: passenger, driver, admin, safety_ops. A person may hold passenger + driver with separate onboarding. | P0 |
| FR-ID-03 | Passenger profile: display name, photo optional, emergency contacts, sharing preferences, rating. | P0 |
| FR-ID-04 | Consent flags for showing age band, gender badge, and photo to co-passengers. Default **off** for gender and exact age. | P0 |
| FR-ID-05 | Driver onboarding: legal name, DL, vehicle RC, insurance, photo enrollment for face match. | P0 |
| FR-ID-06 | Admin can suspend accounts; suspension blocks dispatch. | P0 |
| FR-ID-07 | Profile photo moderation queue (P1 automated, P0 manual). | P1 |

## 5.2 Vehicle and capacity

| ID | Requirement | P |
|----|-------------|---|
| FR-VEH-01 | Modes: Bike (cap 1, no pool), Auto (3, open seats 1–2 in transit), Cab (4, open 1–3), Van (7–8). | P0 |
| FR-VEH-02 | Driver sets mode and vacant seats; system clamps to mode min/max. | P0 |
| FR-VEH-03 | `occupied + held + requested ≤ capacity` at all times. | P0 |
| FR-VEH-04 | Bike cannot receive mid-ride joins. | P0 |

## 5.3 Solo booking

| ID | Requirement | P |
|----|-------------|---|
| FR-BK-01 | Passenger sets pickup, dropoff, mode, seat count, depart-now (later: schedule). | P0 |
| FR-BK-02 | System returns fare estimate, ETA, risk card, consolidation offers. | P0 |
| FR-BK-03 | Dispatch offers to eligible online drivers; accept/reject with timeout. | P0 |
| FR-BK-04 | Assigned state shows driver, vehicle, plate, rating, live ETA. | P0 |
| FR-BK-05 | Trip start requires unlocked OTP after verification policy. | P0 |
| FR-BK-06 | Complete trip, fare capture, rating both ways. | P0 |
| FR-BK-07 | Cancel with published penalty windows. | P1 |

## 5.4 Mid-ride joining (Core 1)

| ID | Requirement | P |
|----|-------------|---|
| FR-MJ-01 | Searchers see “existing active ride” only if eligibility engine returns true. | P0 |
| FR-MJ-02 | Offer shows: display name, age **band** if consented, gender badge if consented, verified mark, rating, vehicle type, occupant count, extra fare, detour. | P0 |
| FR-MJ-03 | Joiner request creates a seat **hold** (TTL 45–90s) and a consent session. | P0 |
| FR-MJ-04 | Occupants vote accept/reject. Policy: **unanimous for MVP**; majority is a P1 config. | P0 |
| FR-MJ-05 | On occupant pass, driver sees waypoint modal: extra fare, +detour, map pin. Driver must accept. | P0 |
| FR-MJ-06 | Confirm updates polyline, ETAs, fares, occupant list. Joiner gets tracking. | P0 |
| FR-MJ-07 | Any reject/timeout: release hold, original ride unchanged, joiner continues search. | P0 |
| FR-MJ-08 | Safety eligibility can suppress offers (Red protocol, occupant opted out of sharing). | P0 |
| FR-MJ-09 | Immediate cancel for joiner before pickup; SOS always available. | P0 |

## 5.5 Pre-ride group matching (Core 2)

| ID | Requirement | P |
|----|-------------|---|
| FR-GR-01 | While searching, show nearby compatible intents with overlap %, walk-to-pickup, shared fare, extra time, capacity. | P0 |
| FR-GR-02 | Independent accept/reject per passenger. | P0 |
| FR-GR-03 | Optimizer returns pickup and drop sequence (OR-Tools / insertion heuristic for MVP). | P0 |
| FR-GR-04 | Driver offer includes bonus and full stop list. | P0 |
| FR-GR-05 | Modal prompts: 2 bikes → auto (~30% save); 5 bikes or auto+bike → cab/van. | P0 |
| FR-GR-06 | Group expires if not filled before TTL or if a member books solo. | P0 |

## 5.6 Safety prediction (Core 3)

| ID | Requirement | P |
|----|-------------|---|
| FR-RS-01 | Pre-confirm risk card: score 0–100, level Low/Med/High (or Green/Yellow/Red internally), factor bars, recommendations, disclaimer. | P0 |
| FR-RS-02 | Features: verification, ratings, vehicle status, lighting index, isolation, time-of-day, historical **segment** incidents (not people), telemetry anomalies. | P0 |
| FR-RS-03 | Never use gender/age/religion as model features. | P0 |
| FR-RS-04 | In-trip: compare GPS to corridor; deviation &gt; 100 m for N seconds raises event, recalculates risk, may siren + prompt “Need help?”. | P0 |
| FR-RS-05 | Single anomaly must not auto-penalize driver; ops review for repeated events. | P0 |
| FR-RS-06 | Uncertainty flag upgrades protocol (conformal / entropy). | P1 |

## 5.7 Driver verification (Core 4)

| ID | Requirement | P |
|----|-------------|---|
| FR-VF-01 | Passenger “Verify Driver” starts a verification session bound to `ride_id` + `driver_id`. | P0 |
| FR-VF-02 | Driver app: live camera, liveness, match to enrollment. | P0 |
| FR-VF-03 | Two attempts, then low-light CLAHE, then **device** biometric as degraded **driver-app** unlock only. | P0 |
| FR-VF-04 | Success: both apps show “Identity Verified” and OTP unlocks. | P0 |
| FR-VF-05 | Persistent fail: no OTP; cancel or safety_ops assisted flow. | P0 |
| FR-VF-06 | Passenger cannot submit *their* biometric as driver proof. | P0 |
| FR-VF-07 | Biometric raw frames not stored by default; embeddings encrypted; retention documented. | P0 |

## 5.8 Tracking, SOS, notifications

| ID | Requirement | P |
|----|-------------|---|
| FR-TR-01 | Live map + ETA + geofence radius 50–1000 m (policy default 100–250 m corridor). | P0 |
| FR-TR-02 | POST location from driver (~2–5s) and passenger heartbeat. | P0 |
| FR-TR-03 | SOS 5s countdown, dual-oscillator siren optional, notify trusted contacts + ops. | P0 |
| FR-TR-04 | Share-trip link with token, revocable, no full PII. | P0 |
| FR-NT-01 | Push/SMS/in-app for assignment, join, vote, verify, SOS, fare. | P0 |

## 5.9 Driver app extras

| ID | Requirement | P |
|----|-------------|---|
| FR-DR-01 | Online/offline, mode, vacant seats, incoming list. | P0 |
| FR-DR-02 | Navigation, OTP entry, complete trip. | P0 |
| FR-DR-03 | Earnings and trip history. | P1 |
| FR-DR-04 | Driver SOS. | P0 |

## 5.10 Admin

| ID | Requirement | P |
|----|-------------|---|
| FR-AD-01 | CRUD-ish views: users, drivers, vehicles (no password display). | P1 |
| FR-AD-02 | Live ride and shared-ride monitor. | P1 |
| FR-AD-03 | Incident desk, verification failures, fraud flags. | P1 |
| FR-AD-04 | Complaints, ratings anomalies, audit log search. | P1 |
| FR-AD-05 | Analytics: occupancy, detour, SOS, match rate. | P2 |

## 5.11 Payments and ratings

| ID | Requirement | P |
|----|-------------|---|
| FR-PY-01 | Estimate, hold, capture, refund; split per occupant with published formula. | P1 (mock ledger P0) |
| FR-RT-01 | 1–5 stars + tags; after complete; abuse filters. | P0 |

## 5.12 User stories (selected)

- As a passenger, I can reject a joiner and my trip continues unchanged.
- As a joiner, I see detour and extra fare before I request.
- As a driver, I am paid for approved detours and can refuse a waypoint.
- As a passenger at night, I cannot start until the app says identity verified **or** I cancel.
- As safety ops, I see SOS with last GPS, ride id, occupants, and risk protocol — not a social-media dump of biometrics.
