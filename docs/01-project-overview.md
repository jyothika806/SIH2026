# 1. Professional project overview

## 1.1 What OptimalRide is

OptimalRide is a production-oriented ride-booking platform for Indian urban and peri-urban mobility. It is inspired by Uber, Ola, and Rapido, but it is not a clone. The product thesis is:

**Use existing vehicle capacity, match people who are already going the same way, and raise the safety bar before a trip starts and while it is in motion.**

The platform has four product surfaces:

1. **Passenger application** — search, book, share, track, verify, SOS.
2. **Driver application** — go online, accept, navigate, verify identity, complete, earn.
3. **Admin / safety operations console** — users, vehicles, live rides, incidents, fraud, verification.
4. **Backend + AI platform** — matching, routing, risk, liveness, payments, notifications.

## 1.2 Product principles

1. **Safety is a control plane, not a banner.** OTP is locked until identity verification succeeds. Risk scores drive *protocol* (tracking intensity, verification, SOS readiness), never a label that a person is “dangerous.”
2. **Sharing is opt-in, never injected.** Mid-ride joins and pre-ride groups require explicit passenger and driver consent. A rejection must not cancel the original ride.
3. **Capacity is a transactional invariant.** Seats are reserved with expiry and idempotency. Two joiners cannot occupy the last seat.
4. **Route truth is the road network.** Matching uses OSRM / road-network distance, not Haversine alone.
5. **Privacy by default.** Age, gender, live location, and biometrics are consent-gated, minimized, encrypted, and retention-bounded.
6. **Explainability over magic.** Risk and matching outputs must be inspectable by ops and, in simplified form, by the rider.
7. **MVP honesty.** Features that require licensed crime data, certified anti-spoofing, or RBI-grade payments are staged, not faked as production-ready.

## 1.3 Who it serves

| Persona | Goal | Failure we must not cause |
|---------|------|---------------------------|
| Daily commuter | Cheaper, reliable shared trip | Forced pooling, unsafe joiners |
| Late-night traveler | Verified driver, monitored corridor | False sense of guaranteed safety |
| Driver partner | Fair payout, fewer empty seats | Unpaid detours, biometric misuse |
| Safety operator | Fast incident response | Alert fatigue, un-auditable actions |
| City / SIH evaluator | Fewer vehicles for same demand | Demo-only logic that cannot scale |

## 1.4 Success metrics (product, not vanity)

- Share of trips that complete with ≥2 paying occupants without exceeding capacity.
- Median extra delay introduced by sharing (target: ≤ 5 minutes vs solo path).
- Percentage of trips with successful driver liveness before OTP unlock.
- SOS-to-ack time for safety ops (target: p95 &lt; 30s in a metro cell).
- Match latency p95 for pre-ride grouping (target: &lt; 800ms excluding map vendor).
- Seat-double-booking incidents: **zero** in production.

## 1.5 Positioning vs incumbents

| Capability | Typical incumbent | OptimalRide |
|------------|-------------------|-------------|
| Pool / share | Pre-trip pool products, limited mid-trip | Pre-trip group match **and** mid-ride join with dual consent |
| Start verification | OTP only | Liveness + enrolled face match, then OTP |
| Safety score | Mostly reactive SOS | Pre-ride + in-trip risk protocol with explanations |
| Capacity use | One booking ≈ one vehicle | Modal consolidation (bike cluster → auto/cab/van) |
| Consent | Driver-centric | Occupants + driver; original trip protected |

## 1.6 What this architecture phase will not do

- Generate full application code.
- Claim legal clearance for biometric processing without DPDP-compliant consent and DPIA.
- Treat device biometrics (driver unlocking their own phone) as proof they are the enrolled driver.
- Use protected demographic attributes as risk features.
