# 12. Complete user workflows

## 12.1 Passenger registration

1. Enter phone → OTP → JWT.
2. Set display name; optional photo.
3. Default consents: location for trip **yes**; age/gender share **no**; biometrics N/A.
4. Add ≥1 emergency contact (soft-required before first book at night — P1).

## 12.2 Driver registration and verification

1. Phone OTP, role=driver.
2. Legal name, DL, RC, insurance upload → object storage, status `pending`.
3. **Enrollment**: guided liveness + store embedding. No enrollment ⇒ cannot go online.
4. Admin or automated checks → `kyc_status=verified`.
5. Register vehicle mode and capacity.

## 12.3 Normal (solo) booking

1. Pickup/dropoff/mode.
2. Quote: fare, ETA, risk card, optional consolidation.
3. Confirm → `ride_requests` + dispatch.
4. Driver accept → assigned; passenger sees plate and photo.
5. Driver arrives → passenger Verify Driver (policy: required for P0 night and Yellow/Red; required always on cab/auto MVP if you approve).
6. OTP unlock → passenger shares / driver enters → `in_progress`.
7. Track, optional SOS, complete, pay, rate.

## 12.4 Dynamic mid-ride joining

As specified in the brief, plus **seat hold**:

1. Primary trip in progress with open seats.
2. Joiner search → eligibility (capacity, overlap, detour, risk, consents).
3. Card with privacy-minimized occupant/driver info.
4. Request → hold + occupant notifications.
5. Occupants accept/reject (unanimous MVP).
6. Driver waypoint (extra fare, +2 min class detour, pin).
7. Commit → joiner tracking. Reject → original untouched.

**Challenge:** occupant phone in tunnel misses vote. **Solution:** TTL 45–90s, default **reject** (fail safe), hold release, optional “driver-only approve if occupants unreachable” is **not** MVP (privacy/safety).

## 12.5 Pre-ride group matching

1. Multiple open requests in a geo cell.
2. Engine builds offer with overlap %, walk, fare, extra time, capacity.
3. Each user accepts/rejects independently.
4. Pickup sequence computed.
5. Driver accepts consolidated offer + bonus.
6. If someone times out, remaining may still fit a smaller vehicle (modal downshift).

## 12.6 Driver face verification

See [15-driver-verification.md](./15-driver-verification.md). Passenger never scans their own face for this step.

## 12.7 AI safety prediction

1. Pre-ride: compute assessment, show disclaimer.
2. On tick: features from GPS vs corridor, stop duration, OTP state, time.
3. If Yellow: banner + “Need help?”
4. If Red or SOS: ops + contacts.
5. No auto-ban from one event.

## 12.8 Route deviation

1. Map-match GPS to corridor (`match_trajectory`).
2. If perpendicular distance &gt; 100 m for T seconds (default 20s) **and** accuracy &lt; 30 m: raise event.
3. Recalculate risk; siren on passenger/driver if protocol says so.
4. Allow driver to tag “traffic diversion / official detour” to suppress repeat siren (logged).

## 12.9 Emergency SOS

1. 5s countdown, cancelable.
2. On fire: last GPS, ride id, occupants, audio siren local, FCM to contacts, incident row, SMS fallback.
3. Safety ops ack SLA.

## 12.10 Payment and fare split

**P0:** compute and display; mark `mock_paid`.  
**P1:** authorize at confirm, capture at complete.

Split model (published):

- Solo: quoted fare.
- Shared: `alpha * (occupant's OD shortest path) + beta * (shared trunk) + detour surcharge on the causer`.
- Primary receives a **visible credit** if joiner shortens their effective cost — never a surprise hike without accept.

## 12.11 Admin incident

SOS → incident `open` → ops map + call mask → resolve with notes → audit log.
