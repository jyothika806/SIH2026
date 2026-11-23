# 14. Route matching algorithm

## 14.1 Why not Haversine only

A 400 m straight-line neighbor may be 8 minutes away across a one-way river crossing. Pooling on Euclidean distance creates impossible pickups and angry detours. Haversine is a **cheap prefilter**, never the scorer.

## 14.2 Pipeline

```text
1. Geo prefilter (PostGIS ST_DWithin pickup, radius R)
2. Capacity + mode + share_opt_in + risk protocol filter
3. OSRM route(remaining_polyline + candidate pickup + candidate drop)
4. Score overlap, detour, walk, fare
5. Rank and offer top K
6. Seat hold on request
```

## 14.3 Mid-ride eligibility (formal)

Let `P` be remaining driver polyline. Candidate pickup `u`, drop `v`.

- `d_walk`: OSRM foot from searcher GPS to `u` (or snap `u` to P).
- `t_orig`: remaining duration on P.
- `t_new`: duration on P′ = insert `u` (and `v` if not already along P).
- `detour = t_new - t_orig`.
- Reject if `detour > max_detour` (default 300s) or `d_walk > 400m`.
- Overlap: fraction of candidate OD that lies within buffer of P (`ST_DWithin` 80–150 m) **or** path-length ratio.

**Overlap %** (production):

```text
overlap = length( intersection( buffer(P, 120m), path(u→v) ) ) / length(path(u→v))
```

MVP approximation: compare OSRM `u→v` vs via-corridor using duration ratio.

## 14.4 Pre-ride grouping

1. Cluster open `ride_requests` by pickup geohash (precision ~ 6–7) and time window (e.g. 4 minutes).
2. Pairwise overlap as above.
3. Greedy set cover into groups of size ≤ target vehicle capacity.
4. Sequence: cheapest insertion on OSRM table (pickup then drop with precedence constraints: pickup_i before drop_i).
5. Optional P1: Google OR-Tools PDPTW.

## 14.5 Modal consolidation

| Signal | Suggestion |
|--------|------------|
| 2 bike intents, overlap ≥ 0.7 | 1 auto, ~30% fare save, driver bonus |
| 5 bikes **or** 1 auto + 1 bike | cab or van |
| Group ≥ 6 | van |

Never auto-switch mode without user accept.

## 14.6 Algorithms used

| Step | Algorithm | MVP |
|------|-----------|-----|
| Prefilter | Haversine / ST_DWithin | Yes |
| Road distance | OSRM (Dijkstra on contraction hierarchies internally) | Yes |
| Map match | OSRM match | Yes |
| Sequence | Cheapest insertion | Yes |
| Sequence P1 | OR-Tools PDPTW / A* on custom graph | Later |
| Clustering | Grid / geohash, not k-means on latlng | Yes |

A* on a self-built road graph is **not** needed while OSRM exists.

## 14.7 Pseudocode

```text
function midRideOffers(searcher):
  candidates = sql"""
    SELECT rides.* FROM rides
    WHERE status = 'in_progress'
      AND mode != 'bike'
      AND ST_DWithin(corridor, searcher.pickup, 500)
      AND open_seats >= searcher.seats
  """
  offers = []
  for r in candidates:
    t0 = osrm.duration(r.remaining)
    t1 = osrm.duration(insert(r.remaining, searcher.pickup, searcher.drop))
    if t1 - t0 > MAX_DETOUR: continue
    if risk(r).level == red and not r.allow_pool_red: continue
    offers.append(score(r, t1-t0))
  return topK(offers)
```

## 14.8 Challenges

| Challenge | Solution |
|-----------|----------|
| OSRM down | Degraded Haversine + `degraded=true`; no auto-confirm |
| One-way streets | Always OSRM, never client polyline |
| Seat double book | SQL hold before notify |
| Unfair long drop | max extra destination beyond corridor |
| Compute cost | Cache corridors in Redis; matrix in batch for groups |
