# Gaps, legal limits, MVP vs production, and approval gates

**Stop here and approve before any implementation work.**

## 1. Missing requirements the brief did not fully specify

| Gap | Architect recommendation (default if you say “approve defaults”) |
|-----|------------------------------------------------------------------|
| Launch city / language | Bengaluru demo; EN + later HI |
| Consent policy for age/gender | Default hidden; age **band** only if opt-in |
| Occupant vote rule | **Unanimous** MVP; majority configurable later |
| When is liveness mandatory? | **Always** before OTP for auto/cab/van; bike too if camera safe |
| Device biometric fallback | **Does not unlock OTP** |
| Payments | Mock ledger MVP; Razorpay P1 |
| Map tiles | OSM + Leaflet MVP |
| Mobile | Keep React SPA for MVP; Flutter for store (need confirm) |
| Admin | SPA routes MVP; Next.js P1 |
| Max detour | 300 seconds |
| Corridor breach | 100 m for 20 s, accuracy &lt; 30 m |
| Seat hold TTL | 60 s |
| Min age | 18 |
| Cancellation penalties | P1 policy table |
| Women-only matching | **Out of MVP** pending legal |
| Child seats / extra riders | One account = seats_needed; no unregistered child policy yet |
| Helmet (bike) | Driver attestation checkbox P1 |
| Insurance | Document upload P1, not adjudication |
| State aggregator licence | Out of software scope; ops checklist |
| Crime data | OSM proxies only until license |
| Support / call center | Safety ops role + email/phone P1 |
| Idempotency keys | Required on book/join |
| Clock | Server time only for OTP/holds |

## 2. Not automatically feasible

| Idea | Reality |
|------|---------|
| “AI knows if a ride is safe” | Protocol score, not a guarantee; synthetic training today |
| “Unbeatable anti-spoof” | Heuristic MVP, not certified PAD |
| Device fingerprint = driver | Explicitly invalid as identity proof |
| Google-quality routing at zero cost | OSRM + OSM; degraded if extract stale |
| Instant police dispatch | We notify; we are not a PSAP |
| Perfect GPS corridor | Underpasses will false-positive; need accuracy gates |

## 3. MVP vs production

### MVP (implement after approval)

- Auth OTP, passenger + driver SPA, van in schema
- Solo book, track, SOS, risk card (ONNX + disclaimer)
- Mid-ride join with holds + unanimous consent + driver waypoint
- Pre-ride group **preview** + modal suggestion (full optimizer can be insertion heuristic)
- Liveness + OTP lock (fail closed)
- Postgres/PostGIS/Redis/OSRM in Compose
- Mock payments
- Gateway mocks labeled and contract-aligned

### Not MVP

- Next.js admin richness, live payments, certified PAD, licensed crime heatmaps, multi-region, Kafka, store apps, GST, full OIDC.

## 4. Decisions I am asking you to approve

Please reply with **Approve** or edits per item:

1. **Stack:** Keep Express + FastAPI + React SPA for MVP; Flutter later; no Nest rewrite.
2. **Data:** PostgreSQL + PostGIS + Redis as system of record (leave SQLite).
3. **Sharing vote:** Unanimous occupants + driver.
4. **OTP:** Unlock only on face match success; device biometric does not unlock.
5. **Risk:** No demographic features; disclaimer mandatory.
6. **Maps:** OSRM match + OSM display.
7. **Payments:** Mock until Phase 6/P1.
8. **Liveness mandatory:** All pooled modes before start.
9. **Detour cap:** 300s / ~100 m corridor siren rule.
10. **Admin:** Phase 6, not blocking MVP trip loop.

## 5. What I will not do until you approve

- Generate the rest of the application.
- Migrate schema or add Compose services.
- Change production security posture in code.

## 6. Suggested first implementation slice (after approval)

1. Compose: Postgres PostGIS, Redis, OSRM sample extract.  
2. Migrate `ride_passengers` + `seat_reservations`.  
3. Align gateway mocks with FastAPI contracts.  
4. Wire passenger book → driver accept → liveness → OTP → track.  
5. Then join + group.

---

If you approve the ten decisions, I will implement **Phase 2 only** first and stop again before sharing features unless you ask to continue.
