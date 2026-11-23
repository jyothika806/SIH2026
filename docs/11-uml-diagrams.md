# 11. UML diagrams

Rendered in Mermaid. These are design artifacts, not generated from code.

## 11.1 Use case

```mermaid
usecaseDiagram
  actor Passenger
  actor Driver
  actor Occupant
  actor Admin
  actor SafetyOps

  Passenger --> (Register / login)
  Passenger --> (Book ride)
  Passenger --> (View risk card)
  Passenger --> (Join mid-ride)
  Passenger --> (Vote on joiner)
  Passenger --> (Verify driver)
  Passenger --> (Track ride)
  Passenger --> (SOS)
  Driver --> (Go online)
  Driver --> (Accept trip)
  Driver --> (Face liveness)
  Driver --> (Accept waypoint)
  Driver --> (Navigate / complete)
  Occupant --> (Vote on joiner)
  Admin --> (Manage users / vehicles)
  SafetyOps --> (Handle SOS / incidents)
```

## 11.2 Component

```mermaid
graph LR
  subgraph Client
    UI[React/Flutter UI]
  end
  subgraph BFF
    GW[Express Gateway]
  end
  subgraph API
    R[FastAPI routers]
  end
  subgraph Domain
    M[Matching]
    T[Trip/Seats]
    L[Liveness]
    K[Risk]
  end
  subgraph Infra
    PG[(Postgres)]
    RD[(Redis)]
    O[OSRM]
  end
  UI --> GW --> R
  R --> M --> O
  R --> T --> PG
  T --> RD
  R --> L
  R --> K
```

## 11.3 Class (domain, simplified)

```mermaid
classDiagram
  class User {
    +id
    +phone
    +roles
  }
  class Ride {
    +id
    +status
    +capacity
    +corridor
    +otpUnlocked
  }
  class RidePassenger {
    +seatNo
    +role
    +pickup
    +dropoff
  }
  class SeatReservation {
    +state
    +expiresAt
  }
  class JoinRequest {
    +detourSeconds
    +status
  }
  class ConsentVote {
    +decision
  }
  class SafetyAssessment {
    +score
    +level
  }
  Ride "1" --> "*" RidePassenger
  Ride "1" --> "*" SeatReservation
  Ride "1" --> "*" JoinRequest
  JoinRequest "1" --> "*" ConsentVote
  Ride "1" --> "*" SafetyAssessment
  User --> RidePassenger
```

## 11.4 Sequence — mid-ride join

```mermaid
sequenceDiagram
  participant J as Joiner
  participant API as Trip API
  participant H as Seat hold
  participant O as Occupants
  participant D as Driver
  J->>API: POST mid-ride/request
  API->>H: HOLD seat TTL 60s
  API->>O: consent required
  O->>API: accept
  API->>D: waypoint offer
  D->>API: accept-waypoint
  API->>H: COMMIT seat
  API->>J: confirmed + tracking
```

## 11.5 Sequence — verify then OTP

```mermaid
sequenceDiagram
  participant P as Passenger
  participant API as Liveness
  participant Dr as Driver app
  P->>API: verify-driver
  API->>Dr: session REQUESTED
  Dr->>API: frames
  API->>API: liveness + match
  alt pass
    API->>P: Identity Verified + OTP
    API->>Dr: OTP unlocked
  else fail x2
    API->>P: cannot start — cancel/support
  end
```

## 11.6 Activity — group match

```mermaid
flowchart TD
  A[Search intents in cell] --> B[Cluster pickup geo]
  B --> C[OSRM overlap]
  C --> D{overlap >= threshold and detour OK?}
  D -->|no| E[Solo dispatch]
  D -->|yes| F[Propose group + modal]
  F --> G[Independent accepts]
  G --> H{capacity and holds valid?}
  H -->|no| E
  H -->|yes| I[Driver offer]
  I --> J[Confirm multi-stop ride]
```

## 11.7 Deployment (target)

```mermaid
flowchart TB
  subgraph VPC
    ALB[Load balancer]
    GW[Gateway replicas]
    API[FastAPI replicas]
    WK[Workers]
    PG[(Postgres primary)]
    RD[(Redis)]
    OSRM[OSRM]
  end
  Users --> ALB --> GW --> API
  API --> PG
  API --> RD
  WK --> RD
  API --> OSRM
```

## 11.8 ERD

See [09-database-schema.md](./09-database-schema.md) §9.2.
