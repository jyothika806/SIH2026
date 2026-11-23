# 8. Technology stack with justifications

## 8.1 Decision: evolve this repo, do not rewrite

The brief lists React Native/Flutter and Next.js. This repository already has **React + Vite + Express + FastAPI**. Rewriting everything before a working trip loop would be the wrong architectural move.

| Layer | MVP (approved direction unless you override) | Production track |
|-------|----------------------------------------------|------------------|
| Passenger / Driver **demo & web** | React 18 + Vite + Tailwind + Lucide (existing) | Same for ops web; PWA optional |
| Passenger / Driver **store apps** | Not in MVP | Flutter (tree already under `mobile_app/`) **or** React Native — **need your pick** |
| Admin | FastAPI `/admin` + React admin routes in SPA for MVP | Next.js + TypeScript dashboard (P1) |
| BFF | Express 4 (`server.ts`) | Same + rate limit + JWT verify |
| Domain API | FastAPI + Pydantic v2 | Same |
| Workers | FastAPI BackgroundTasks / Redis consumer (P0 light) | Dedicated worker process |
| DB | PostgreSQL 16 + PostGIS 3 | Same + read replica |
| Cache / realtime | Redis 7 | Redis Cluster when needed |
| Routing | OSRM (existing client) | OSRM + Mapbox/Google basemap tiles |
| Optimization | Greedy insertion + optional OR-Tools | OR-Tools VRP |
| AI risk | XGBoost → ONNX (existing) | Retrain on labeled ops data |
| Liveness | MediaPipe + OpenCV (existing) | Add InsightFace/ArcFace embeddings + PAD model |
| Push | FCM | FCM + SMS (MSG91/Twilio) |
| Payments | Mock ledger P0 | Razorpay/Cashfree UPI |
| Observability | stdout + correlation IDs | OpenTelemetry + Grafana |
| Infra | Docker Compose | Compose → k8s later |

## 8.2 Why FastAPI (not NestJS)

- AI/CV/risk already in Python.
- Team can share `ai_engine` imports with API (already done in `main.py`).
- Async + Pydantic fits geo payloads.
- Nest would duplicate the existing service layer.

## 8.3 Why Express stays

- Already the public port (8080), SPA host, Helmet, CORS, Gemini chat, mock fallbacks for SIH demos.
- BFF can aggregate passenger/driver payloads without extra hops from the browser to many origins.

## 8.4 Why PostgreSQL + PostGIS, not Mongo

- Capacity, money, and consent need **transactions**.
- K-NN and corridor queries: `ST_DWithin`, `ST_LineLocatePoint`, GiST.
- Mongo geo is weaker for polyline overlap and FK integrity.

## 8.5 Why Redis

- Seat holds with TTL (`SETEX` + Lua compare-and-swap as belt-and-suspenders to SQL holds).
- Last GPS.
- Match candidate cache.
- Pub/sub for WS scale-out.

## 8.6 Why OSRM, not “just Google Directions”

- Cost at matching QPS.
- Self-hostable for SIH and air-gapped demos.
- Table service for matrices (group pickup sequences).
- Consumer map UI may still use Google/Mapbox **display** SDK (separate billed channel).

## 8.7 Maps display (open decision)

| Option | Pros | Cons |
|--------|------|------|
| Mapbox | Good GL, India coverage OK | Cost, token |
| Google Maps | Familiar | Cost, ToS on caching |
| Leaflet + OSM tiles | Free for demo | Attribution, less polish |

**Recommendation:** Leaflet + OSM for MVP web; Mapbox or Google when store apps ship.

## 8.8 Why not full microservices now

Matching + trip + consensus must share a transaction for seat holds. Network-split sagas at this stage increase “two passengers, one seat” risk.

## 8.9 Mobile recommendation (awaiting approval)

**Recommend Flutter** because `mobile_app/` already exists, camera/liveness plugins are mature, and one codebase covers Android/iOS for SIH field demo. React Native is acceptable if the web team must share TypeScript components — then extract a `packages/api-client`.

## 8.10 Explicitly rejected for MVP

- Kafka (Redis streams enough).
- Kubernetes (Compose first).
- Storing face images in Postgres BYTEA.
- Client-only matching (can be spoofed; seats would desync).
