# 15. Driver verification architecture

## 15.1 Why OTP is insufficient

OTP proves the passenger and the person with the phone agree on a number. It does **not** prove the face in the driver’s seat matches the licensed partner.

## 15.2 Two different authentications (do not conflate)

| Mechanism | Proves | Allowed as “Driver Identity Verified”? |
|-----------|--------|----------------------------------------|
| Liveness + match to **enrollment embedding** | The operator is likely the enrolled driver | **Yes** |
| Device biometric (fingerprint / OS FaceID) | Someone who can unlock **that phone** | **No** (fallback only to continue *driver-app* session, passenger still sees not verified) |
| Passenger’s own biometric | Passenger identity | **Never** for this flow |

The current `low_light_fallback.py` device-biometric path is useful for **driver app unlock in the dark**. It must **not** set `otp_unlocked` unless product policy explicitly allows a **manual safety_ops override** (P1, audited).

**MVP recommendation:** OTP unlocks only on `liveness_passed && match_score ≥ threshold`. Fallback does not unlock OTP. Passenger is offered cancel + support.

## 15.3 Enrollment (onboarding)

1. Capture N frames with liveness (blink / pose).
2. Extract embedding (InsightFace/ArcFace P1; MVP: landmark-based template + stored reference frame **encrypted**, hashed).
3. Store embedding in KMS-encrypted blob; not in logs.
4. Binding: `driver_id` + `device_attestation` optional P1.

## 15.4 Trip-time state machine (already in liveness API)

`PENDING → REQUESTED → IN_PROGRESS → SUCCESS | FAILED`  
Low light: `LOW_LIGHT_DETECTED → CLAHE retry → FALLBACK_REQUIRED` (app unlock only).

Passenger `Verify Driver` creates `REQUESTED`. Driver app cannot self-start success.

## 15.5 Liveness (existing stack)

- MediaPipe 468 landmarks
- EAR blink
- Head pose PnP
- Texture / depth variance anti-print
- Multi-face reject
- CLAHE in low light

**Limits:** not ISO PAD. Printed video with a wiggle can still fool heuristics. Disclose as **best-effort MVP**, plan a PAD model (P2).

## 15.6 Matching

```text
score = cosine(embed_live, embed_enrolled)
pass if liveness_ok and score >= T (e.g. 0.35–0.45 depending on model)
```

Two attempts. Then fail closed.

## 15.7 OTP lock

- Generate OTP at assign; store **only hash** (argon2/bcrypt).
- `otp_unlocked=false` until SUCCESS.
- Passenger UI shows masked `••••` until unlock.
- 5-minute validity after unlock (existing README).
- Single use.

## 15.8 Challenges

| Attack / issue | Mitigation |
|----------------|------------|
| Replay video | Challenge: random head turn / blink prompt (P1 active liveness) |
| Deepfake | PAD model P2; device attestation |
| Photo of driver | Texture + depth + blink |
| Passenger verifies themselves | Session bound to driver device push; camera on driver app only |
| Embedding theft | Encrypt at rest; no export API |
| False reject in helmet/mask | Bike: still require face; allow one extra attempt; then cancel |
