# 19. Deployment architecture

## 19.1 Environments

| Env | Purpose | Data |
|-----|---------|------|
| local | Compose all deps | synthetic |
| staging | Prod-like | anonymized |
| prod | Single region MVP | real, encrypted |

## 19.2 Target Compose (to-be)

Services: `gateway`, `fastapi`, `worker`, `postgres` (PostGIS image), `redis`, `osrm`, `minio` (S3 compatible).  
Today Compose is only gateway + fastapi + SQLite — that is **demo**, not prod.

## 19.3 Production sketch

- TLS terminator / ALB
- Gateway n replicas
- FastAPI n replicas, CPU for ONNX
- Worker replicas for match + TTL sweeper
- Postgres primary + WAL backups
- Redis with persistence for holds (AOF) or accept hold loss with SQL as source of truth (**SQL is source of truth**)
- OSRM on SSD, city extract
- Object storage
- FCM / SMS / PG (Razorpay) as SaaS

## 19.4 DR

- Daily snapshots + PITR
- Document failover; OSRM rebuild from OSM PBF
- Secrets rotation

## 19.5 Config

- `DATABASE_URL` postgres
- `REDIS_URL`
- `OSRM_SERVER_URL`
- `JWT_SECRET` (replace `change-me-in-production`)
- Map tokens
- Feature flags: `sharing_enabled`, `liveness_required`, `payments_live`

## 19.6 SIH / jury mode

Flag `DEMO_MODE=true`: faster ETAs, labeled mock liveness if camera denied, **never** fake a successful police dispatch.
