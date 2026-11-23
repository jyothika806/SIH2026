# 13. AI/ML model design

## 13.1 What exists

`ai_engine/risk_engine`: feature pipeline, XGBoost multiclass, conformal uncertainty, ONNX &lt;5ms, protocols Green/Yellow/Red. Training data is **synthetic unless replaced**.

## 13.2 Problem formulation

**Not:** “Is this person dangerous?”  
**Yes:** “Given *this trip context*, how aggressive should safety *protocol* be?”

Labels (ops, not demographics):

- 0 Green — completed, no incident, no severe deviation
- 1 Yellow — deviation/stop/help prompt, no SOS
- 2 Red — SOS, verified incident, or forced cancel for safety

## 13.3 Allowed features

| Family | Examples | Source |
|--------|----------|--------|
| Temporal | hour cyclical, late-night window | clock |
| Route | lighting index, isolation, crime **segment** index | licensed GIS / OSM proxies |
| Driver **behavior** | rating drift, completion rate, harsh brake rate | telemetry + history |
| Verification | driver kyc, liveness this trip | fleet |
| Journey | drift_m, stop_s, gps_hdop | live |
| Occupants | count, verification **level** (not gender) | trip |

## 13.4 Forbidden features

Gender, exact age, name, religion, caste, device language as proxy, unverified allegations, raw complaint text without review.

## 13.5 Model

- **MVP:** keep XGBoost + ONNX (already integrated).
- **Explain:** tree SHAP on server; map to human indicators (“Poor lighting on this segment”, “Night window”, “Verified driver”).
- **Uncertainty:** entropy &gt; 0.45 upgrades protocol (already in README).
- **Calibration:** ECE logged; do not show 99% confidence on synthetic models.

## 13.6 Training and leakage

- Split by **time** and **city**, not random rows.
- Do not include post-treatment features (e.g. “SOS happened”) in pre-ride model.
- Separate `pre` and `in_trip` heads or a `phase` feature that is set correctly.

## 13.7 Serving

- FastAPI loads ONNX at startup (`get_predictor()` today).
- Cache assessment per ride+phase for N seconds.
- Store `safety_assessments` row every pre-ride and on protocol change.

## 13.8 Challenges and mitigations

| Challenge | Mitigation |
|-----------|------------|
| No real labels | Start rule-based overlay + synthetic; freeze “AI” claims in marketing |
| Crime data license | Use OSM proxies (lighting=streetlamp density) until license |
| Bias | Forbidden feature list in CI test |
| Drift | Weekly PSI on features; retrain job |
| GPS noise | Require accuracy; map-match before drift feature |

## 13.9 Pseudocode

```text
function assess(trip, phase):
  x = featurize(trip, phase)  # no demographic fields
  proba, entropy = onnx(x)
  level = argmax(proba)
  if entropy > 0.45: level = upgrade(level)
  indicators = shap_top(x, k=5)
  protocol = PROTOCOLS[level]
  persist(assessment)
  return {score, level, indicators, protocol, disclaimer=true}
```
