# 6. Non-functional requirements

## 6.1 Availability and reliability

| ID | Requirement |
|----|-------------|
| NFR-AV-01 | API availability 99.9% monthly for booking/matching (excluding map vendor). |
| NFR-AV-02 | Degraded mode: if OSRM down, Haversine + cached polylines with `degraded=true` on offers (never silent). |
| NFR-AV-03 | Gateway already mocks FastAPI; **production must fail closed on payments and verification**, fail open only on non-critical suggestions. |
| NFR-AV-04 | RPO 15 min, RPO/RTO documented; DB PITR for production. |

## 6.2 Performance and realtime

| ID | Target |
|----|--------|
| NFR-PR-01 | Booking create p95 &lt; 400ms excluding dispatch wait. |
| NFR-PR-02 | Match query p95 &lt; 800ms (OSRM cached). |
| NFR-PR-03 | Risk inference p95 &lt; 25ms in-process ONNX (engine claims &lt;5ms). |
| NFR-PR-04 | Location ingest 2–5s/driver; fan-out to ride room &lt; 200ms in-region. |
| NFR-PR-05 | Push for vote/SOS p95 &lt; 2s when FCM healthy. |

## 6.3 Scalability

- Stateless FastAPI behind gateway; WebSockets via Redis pub/sub (not in-process dict).
- Matching workers scale on Redis geo queues.
- Telemetry write path: Redis last-known + batched Postgres.
- Horizontal seats: cell-based sharding later (city_id); MVP single region.

## 6.4 Concurrency (seat race)

**Scenario:** two joiners, one remaining seat.

Required:

1. `BEGIN`
2. `SELECT … FOR UPDATE` on `rides` or `seat_inventory`
3. Insert `seat_reservations` with unique `(ride_id, seat_index)` where status=`held`
4. Commit
5. TTL job expires holds → seat returns

Idempotency: `Idempotency-Key` on book/join. Replay returns the same `request_id`.

## 6.5 Security NFRs

See [16-security-privacy.md](./16-security-privacy.md). Summary: TLS 1.2+, JWT, RBAC, encryption at rest for PII/biometrics, rate limits, audit, no secrets in git.

## 6.6 Privacy NFRs

- DPDP lawful basis + consent records.
- Purpose limitation: embeddings only for driver match.
- Data minimization on co-passenger cards.
- Right to erasure with legal hold exception for incidents/payments.

## 6.7 Observability

- Correlation ID already on gateway — propagate to FastAPI.
- Metrics: match latency, hold collisions, verify success, SOS, risk distribution.
- Structured logs; no raw OTP or embeddings in logs.

## 6.8 Localization and accessibility (often missed)

| ID | Requirement | P |
|----|-------------|---|
| NFR-I18N-01 | English + Hindi strings for P0 screens. | P1 |
| NFR-A11Y-01 | SOS contrast, 44px targets, screen-reader labels on verify/SOS. | P1 |

## 6.9 Compliance and payments reliability

- PCI: never store PAN; use PG tokenization.
- GST invoice generation P1.
- Clock sync (NTP) for OTP and hold TTL.
