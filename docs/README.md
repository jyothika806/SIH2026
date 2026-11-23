# OptimalRide — Architecture Documentation

**Project:** OptimalRide – Smarter, Safer & More Efficient Rides  
**Problem context:** Smart India Hackathon / intelligent commutation (PS 26203)  
**Status:** Architecture and requirements only. **No implementation in this phase.**  
**Date:** 2026-11-14

This directory is the source of truth for product, architecture, data, APIs, AI, security, and delivery planning. Read in order. Implementation starts only after explicit approval of the decisions in [21-gaps-mvp-and-approval.md](./21-gaps-mvp-and-approval.md).

## Deliverable map

| # | Deliverable | Document |
|---|-------------|----------|
| 1 | Project overview | [01-project-overview.md](./01-project-overview.md) |
| 2 | Problem statement | [02-problem-statement.md](./02-problem-statement.md) |
| 3 | Existing system limitations | [03-existing-limitations.md](./03-existing-limitations.md) |
| 4 | Proposed system | [04-proposed-system.md](./04-proposed-system.md) |
| 5 | Functional requirements | [05-functional-requirements.md](./05-functional-requirements.md) |
| 6 | Non-functional requirements | [06-non-functional-requirements.md](./06-non-functional-requirements.md) |
| 7 | System architecture | [07-system-architecture.md](./07-system-architecture.md) |
| 8 | Technology stack | [08-technology-stack.md](./08-technology-stack.md) |
| 9 | Database schema | [09-database-schema.md](./09-database-schema.md) |
| 10 | API contracts | [10-api-contracts.md](./10-api-contracts.md) |
| 11 | UML diagrams | [11-uml-diagrams.md](./11-uml-diagrams.md) |
| 12 | User workflows | [12-user-workflows.md](./12-user-workflows.md) |
| 13 | AI/ML model design | [13-ai-ml-design.md](./13-ai-ml-design.md) |
| 14 | Route matching algorithm | [14-route-matching.md](./14-route-matching.md) |
| 15 | Driver verification architecture | [15-driver-verification.md](./15-driver-verification.md) |
| 16 | Cybersecurity and privacy | [16-security-privacy.md](./16-security-privacy.md) |
| 17 | Development roadmap | [17-development-roadmap.md](./17-development-roadmap.md) |
| 18 | Testing strategy | [18-testing-strategy.md](./18-testing-strategy.md) |
| 19 | Deployment architecture | [19-deployment-architecture.md](./19-deployment-architecture.md) |
| 20 | Future enhancements | [20-future-enhancements.md](./20-future-enhancements.md) |
| — | Gaps, legal limits, MVP vs production, approval gates | [21-gaps-mvp-and-approval.md](./21-gaps-mvp-and-approval.md) |

## How to use this pack

1. Confirm product scope (MVP vs production) in document 21.
2. Confirm stack choices in document 08 (especially mobile vs current React SPA).
3. Confirm database target (PostgreSQL + PostGIS + Redis) vs current SQLite default.
4. Approve API and schema, then proceed phase-by-phase per document 17.

## Grounding in this repository

The architecture is not a greenfield fantasy. This repo already contains:

- Express gateway (`server.ts`) + Vite React SPA (`src/`)
- FastAPI domain services (`backend/app/`)
- Matching / OSRM (`backend/app/services/matching_service.py`)
- XGBoost/ONNX risk engine (`ai_engine/risk_engine/`)
- MediaPipe liveness (`ai_engine/liveness_detection/`)
- Partial ORM (`backend/app/db/models.py`)
- Docker Compose for gateway + FastAPI only (no Postgres, Redis, OSRM, or object storage yet)

Documents call out **as-is vs to-be** so we do not silently replace working modules.
