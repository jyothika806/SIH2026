# OptimalRide AI Risk Engine

A state-of-the-art spatial-temporal risk prediction system for ride-hailing safety that currently DOES NOT exist in commercial platforms.

## Architecture Overview

```
ai_engine/risk_engine/
├── datasets/                      # Training and test data
│   └── README.md                 # Data format documentation
├── feature_engineering.py        # Multi-modal spatial-temporal feature pipeline
├── train_risk_model.py           # XGBoost + Conformal Risk Bounds + ONNX Exporter
├── predict.py                    # High-speed ONNX Runtime Inference Engine (<5ms)
└── README.md                     # This file

backend/app/api/v1/
└── risk.py                       # FastAPI High-Concurrency Async Endpoint
```

## Novel Features

### 1. Advanced Feature Engineering (`feature_engineering.py`)

**Temporal Dynamics:**
- `time_of_day`, `day_of_week`, `is_late_night_window` (10 PM - 5 AM)
- Cyclical encoding for temporal features
- Peak hour detection (morning/evening)

**Spatial Road Segment Embedding:**
- `road_segment_crime_index` - Normalized crime statistics
- `lighting_density_score` - Street lighting infrastructure
- `route_isolation_factor` - Distance from main arterial roads
- Derived spatial risk composites

**Driver Behavioral Anomaly:**
- `driver_recent_rating_drift` - 30-day vs 7-day rating delta
- `completion_rate` - Ride completion statistics
- `telemetry_anomaly_score` - Harsh braking/speeding frequency
- Driver reliability composite score

**Co-Passenger Safety Index:**
- Combined verification level and trust score
- Multi-passenger verification aggregation
- Passenger safety index calculation

**Spatial-Temporal Interaction Terms:**
- `isolation_factor * is_late_night_window`
- `crime_index * late_night`
- `poor_lighting * late_night`
- Composite risk interaction scores

### 2. Model Training (`train_risk_model.py`)

**XGBoost Multi-Class Classifier:**
- `objective="multi:softprob"`, `num_class=3`
- Optimized hyperparameters for risk prediction
- Early stopping with validation data

**Conformal Uncertainty Estimation:**
- Prediction confidence scores via Shannon entropy
- Uncertainty threshold: entropy > 0.45 triggers escalation
- Calibration error calculation (ECE)

**ONNX Export with Quantization:**
- FP16/INT8 quantization for sub-5ms latency
- ONNX Runtime optimization
- Model verification and benchmarking

**Comprehensive Metrics:**
- Log-Loss, F1-Score per class
- Uncertainty Calibration Error
- Inference Latency Benchmarks (P95, P99)

### 3. Ultra-Fast Inference (`predict.py`)

**UltraFastRiskPredictor Class:**
- ONNX Runtime with optimized execution providers
- Preallocated tensors for zero-copy inference
- Sub-5ms latency target

**Structured JSON Response:**
```json
{
  "risk_level": "Green" | "Yellow" | "Red",
  "risk_code": 0 | 1 | 2,
  "confidence_score": 0.0 - 1.0,
  "uncertainty_flag": true | false,
  "inference_time_ms": <5.0,
  "action_protocol": {
    "dispatch_mode": "...",
    "otp_level": "...",
    "tracking": "...",
    "verification": "...",
    "emergency_alert": "..."
  }
}
```

**Action Protocols:**
- **Green**: Standard Dispatch + Normal OTP
- **Yellow**: Active Route Tracking + Mid-route Driver Face Verification
- **Red**: Block Auto-Dispatch + Mandatory Biometric Scan + Emergency Alert Ready

### 4. FastAPI Endpoint (`backend/app/api/v1/risk.py`)

**High-Concurrency Async Endpoint:**
- POST `/api/v1/risk/evaluate-advanced`
- Pydantic V2 schemas with custom validation
- Response caching headers
- Batch processing support (`/evaluate-batch`)

**Additional Endpoints:**
- GET `/health` - Service health check
- GET `/action-protocols` - Available action protocols
- GET `/features` - Feature descriptions

## Installation

### AI Engine Dependencies

```bash
cd ai_engine
pip install -r requirements.txt
```

### Backend Dependencies

```bash
cd backend
pip install -r requirements.text
```

## Usage

### 1. Train the Model

```bash
cd ai_engine/risk_engine
python train_risk_model.py
```

This will:
- Generate synthetic training data (or use your own)
- Train XGBoost model with conformal uncertainty
- Export to ONNX with FP16 quantization
- Save all artifacts to `ai_engine/models/`

### 2. Test Inference

```bash
cd ai_engine/risk_engine
python predict.py
```

This will:
- Load the ONNX model
- Run sample predictions
- Benchmark inference latency
- Verify sub-5ms target

### 3. Start Backend API

```bash
cd backend
python -m app.main
```

The API will be available at `http://localhost:8000`

### 4. Make API Requests

```bash
curl -X POST "http://localhost:8000/api/v1/risk/evaluate-advanced" \
  -H "Content-Type: application/json" \
  -d '{
    "timestamp": "2026-09-27T10:30:00",
    "road_segment_crime_index": 0.7,
    "lighting_density_score": 0.3,
    "route_isolation_factor": 0.8,
    "distance_from_arterial": 800.0,
    "driver_30day_rating": 4.2,
    "driver_7day_rating": 3.8,
    "completion_rate": 0.88,
    "harsh_braking_frequency": 4.5,
    "speeding_frequency": 3.2,
    "total_rides_last_30days": 45,
    "passenger_verification_level": "basic",
    "passenger_trust_score": 0.6,
    "co_passenger_count": 1,
    "co_passenger_verification_levels": ["none"]
  }'
```

## Performance Benchmarks

Target performance metrics:
- **Inference Latency**: <5ms (P95)
- **Model Accuracy**: >85% F1-Score (macro)
- **Calibration Error**: <0.1 ECE
- **Concurrent Requests**: 1000+ requests/second

## Feature Extraction Pipeline

The system extracts **43 features** across 5 domains:

1. **Temporal** (10 features): Time patterns, cyclical encoding
2. **Spatial** (7 features): Crime, lighting, isolation metrics
3. **Driver Behavior** (11 features): Rating drift, telemetry anomalies
4. **Passenger Safety** (6 features): Verification, trust scores
5. **Interactions** (9 features): Cross-domain feature products

## Risk Level Classification

- **Green (0)**: Low risk - Standard dispatch protocol
- **Yellow (1)**: Medium risk - Enhanced tracking and verification
- **Red (2)**: High risk - Mandatory biometrics and emergency readiness

## Uncertainty Escalation

When model uncertainty exceeds threshold (entropy > 0.45):
- Green → Yellow escalation
- Yellow → Red escalation
- Uncertainty flag set in response
- Action protocol automatically upgraded

## Production Deployment

### Model Artifacts

After training, the following artifacts are saved to `ai_engine/models/`:
- `risk_engine.onnx` - Quantized ONNX model
- `risk_engine.json` - XGBoost model (backup)
- `risk_engine_scaler.joblib` - Feature scaler
- `risk_engine_uncertainty.joblib` - Conformal estimator
- `risk_engine_metrics.json` - Evaluation metrics
- `risk_engine_features.json` - Feature names

### API Configuration

Configure in `backend/app/main.py`:
- CORS settings
- Model loading strategy
- Endpoint routing
- Middleware configuration

### Monitoring

Key metrics to monitor:
- Inference latency (P95, P99)
- Prediction distribution (Green/Yellow/Red)
- Uncertainty flag rate
- API error rates
- Model drift over time

## Integration Points

### External Data Sources

- **Crime Data**: Municipal crime databases
- **Lighting Data**: City infrastructure APIs
- **GPS/Maps**: Isolation factor calculation
- **Driver Telemetry**: Real-time vehicle sensors
- **Passenger Verification**: Identity verification services

### Internal Systems

- **Dispatch System**: Risk-based routing
- **Notification System**: Alert triggers
- **Biometric System**: Verification requests
- **Emergency System**: Alert escalation
- **Analytics System**: Risk pattern analysis

## Future Enhancements

- Deep learning models (transformers for spatial-temporal data)
- Real-time model updating
- Graph neural networks for road network analysis
- Multi-modal fusion (images, audio, text)
- Federated learning for privacy-preserving updates
- Explainable AI (SHAP, LIME) for risk attribution

## License

Proprietary - OptimalRide Project for SIH 2026

## Authors

OptimalRide AI Research Team
