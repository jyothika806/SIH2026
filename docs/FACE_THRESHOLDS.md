# Identity verification thresholds and fail-closed behavior

The configured defaults are:

| Setting | Default | Purpose |
|---|---:|---|
| `FACE_ENROLLMENT_THRESHOLD` | `0.363` | Minimum configured enrollment score before an admin may activate a template |
| `FACE_RIDE_THRESHOLD` | `0.363` | Minimum match score for ride OTP release |

These are application configuration values, not independently validated operating thresholds, biometric accuracy claims, or proof of identity. Before production use, the model owner must document the model/version, score direction and calibration, false-accept/false-reject measurements on representative authorized data, presentation-attack evaluation, accessibility and fallback policy, consent/retention basis, and a documented approval. Recalibrate per model version and deployment population; do not copy thresholds between incompatible models.

The repository does not include an authorized identity model or a trusted inference path. Verification requests therefore fail closed with service unavailable. Device biometrics and browser state do not unlock an OTP. Do not fabricate a positive match, use a canned score, or activate a test template in production. The application stores encrypted templates only when a permitted enrollment flow exists; raw face frames must not be logged or persisted.

Biometric templates have a default retention period of `BIOMETRIC_RETENTION_DAYS` (365 days from creation). The restart-safe maintenance task clears the stored encrypted embedding, marks the row `expired_retention`, and records a separate audit event; repeating the task does not repeat the purge event. Consent revocation immediately deactivates templates and invalidates outstanding verification attempts and ride OTPs. Audit evidence is retained without retaining raw frames or template bytes.

To enable a model, implement and independently review the server-side inference and liveness path, bind each result to the ride, driver, active template, nonce, score threshold, and expiry, then add behavioral tests using a controlled verifier contract. A test double may test endpoint failure handling but must never represent a successful biometric result.
