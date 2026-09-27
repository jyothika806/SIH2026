# Pre-Ride Driver Liveness & Auth Engine

A state-of-the-art liveness detection system for driver authentication before ride dispatch, implementing passive 3D facial analysis and biometric fallback mechanisms.

## Architecture Overview

```
ai_engine/liveness_detection/
├── face_landmarker.py        # MediaPipe 3D landmark extractor & mesh processing
├── passive_liveness.py       # 3D passive liveness checks (EAR & Head Pose)
├── low_light_fallback.py     # Low-light detection, CLAHE & biometric fallback
└── README.md                 # This file

backend/app/api/v1/
└── liveness.py               # FastAPI endpoints for Pre-OTP verification state machine
```

## Novel Features

### 1. 3D Face Landmark Extraction (`face_landmarker.py`)

**MediaPipe Face Mesh Integration:**
- 468 3D facial landmarks extraction
- Specialized landmark extraction for key features:
  - Left/Right Eye coordinates (6 points each) for EAR calculation
  - Nose tip, chin, eye corners, mouth corners for head pose
- Face bounding box calculation
- Multi-face detection and filtering
- Confidence-based quality assessment

**Robust Error Handling:**
- Missing face detection
- Multiple face detection (security feature)
- Low confidence detection
- Image decoding errors

### 2. Passive Liveness Detection (`passive_liveness.py`)

**Eye Blink Detection (EAR):**
- Eye Aspect Ratio calculation using formula:
  $$EAR = \frac{\vert{}\vert{}p_2 - p_6\vert{}\vert{} + \vert{}\vert{}p_3 - p_5\vert{}\vert{}}{2 \vert{}\vert{}p_1 - p_4\vert{}\vert{}}$$
- Consecutive frame thresholding
- Left and right eye independent analysis
- Dynamic threshold adjustment

**3D Head Pose Estimation:**
- OpenCV `cv2.solvePnP` implementation
- Yaw, Pitch, Roll angle calculation
- Real-time head rotation detection
- Movement validation thresholds

**Spoof Detection:**
- Texture variance analysis (photo detection)
- Depth variance analysis (flat surface detection)
- Motion score calculation
- Multi-factor spoof confidence scoring

### 3. Low-Light Fallback System (`low_light_fallback.py`)

**Ambient Light Detection:**
- Mean pixel intensity calculation
- Light condition classification (6 levels)
- Brightness thresholding (40/255 default)

**CLAHE Enhancement:**
- Contrast Limited Adaptive Histogram Equalization
- LAB color space processing
- Quality score calculation
- Brightness/contrast improvement metrics

**Biometric Fallback:**
- Device-native authentication support:
  - Fingerprint authentication
  - Device FaceID
  - Infrared sensor integration
- Secure token generation
- Method selection based on device capabilities
- Automatic fallback triggering

### 4. State Machine API (`backend/app/api/v1/liveness.py`)

**Verification State Machine:**
- PENDING → REQUESTED → IN_PROGRESS → SUCCESS/FAILED
- Low-light branch: IN_PROGRESS → LOW_LIGHT_DETECTED → FALLBACK_REQUIRED → FALLBACK_AUTHENTICATED
- Expiration handling
- Session management

**REST Endpoints:**
- `POST /api/v1/liveness/request-verification` - Initiate verification
- `POST /api/v1/liveness/verify-driver-scan` - Process driver frame
- `POST /api/v1/liveness/biometric-fallback` - Fallback authentication
- `GET /api/v1/liveness/otp-status/{ride_id}` - OTP status check
- `DELETE /api/v1/liveness/sessions/{verification_id}` - Cancel verification

**WebSocket Support:**
- `WS /api/v1/liveness/ws/verification/{verification_id}` - Real-time updates
- State change notifications
- Ping/pong keep-alive

**OTP Locking Mechanism:**
- OTP locked until verification == SUCCESS
- Automatic release on successful verification
- 5-minute OTP validity after release
- Expiration handling

## Installation

### AI Engine Dependencies

```bash
cd ai_engine
pip install -r requirements.txt
```

Key dependencies:
- `opencv-python>=4.8.0` - Computer vision operations
- `mediapipe>=0.10.0` - Face mesh and landmark detection
- `numpy>=1.24.0` - Numerical operations

### Backend Dependencies

```bash
cd backend
pip install -r requirements.text
```

Additional dependencies for API:
- `fastapi>=0.104.0` - Web framework
- `pydantic>=2.0.0` - Data validation
- `opencv-python>=4.8.0` - Image processing
- `mediapipe>=0.10.0` - Face detection

## Usage

### 1. Test Face Landmarker

```bash
cd ai_engine/liveness_detection
python face_landmarker.py
```

### 2. Test Passive Liveness Detector

```bash
cd ai_engine/liveness_detection
python passive_liveness.py
```

### 3. Test Low-Light Fallback Handler

```bash
cd ai_engine/liveness_detection
python low_light_fallback.py
```

### 4. Start Backend API

```bash
cd backend
python -m app.main
```

The API will be available at `http://localhost:8000`

## API Usage Examples

### Request Verification

```bash
curl -X POST "http://localhost:8000/api/v1/liveness/request-verification" \
  -H "Content-Type: application/json" \
  -d '{
    "ride_id": "ride_12345",
    "driver_id": "driver_67890",
    "passenger_id": "passenger_11111",
    "device_capabilities": {
      "fingerprint": true,
      "faceid": true,
      "infrared": false
    },
    "infrared_available": false,
    "verification_timeout_seconds": 300
  }'
```

### Submit Driver Scan

```bash
curl -X POST "http://localhost:8000/api/v1/liveness/verify-driver-scan" \
  -H "Content-Type: application/json" \
  -d '{
    "verification_id": "uuid-from-request",
    "frame_data": "base64-encoded-image",
    "frame_format": "jpeg",
    "sequence_number": 1
  }'
```

### Check OTP Status

```bash
curl -X GET "http://localhost:8000/api/v1/liveness/otp-status/ride_12345"
```

### Biometric Fallback

```bash
curl -X POST "http://localhost:8000/api/v1/liveness/biometric-fallback" \
  -H "Content-Type: application/json" \
  -d '{
    "verification_id": "uuid-from-request",
    "auth_token": "token-from-fallback-payload",
    "biometric_method": "fingerprint",
    "device_id": "device_12345"
  }'
```

## Technical Specifications

### Eye Aspect Ratio (EAR) Calculation

```
EAR = (||p2 - p6|| + ||p3 - p5||) / (2 * ||p1 - p4||)

Where:
- p1, p4: Horizontal eye extent points
- p2, p6: Vertical eye extent points (left side)
- p3, p5: Vertical eye extent points (right side)
```

### Head Pose Estimation

Uses OpenCV `cv2.solvePnP` with 6 3D model points:
- Nose tip (0, 0, 0)
- Chin (0, -330, -65)
- Left eye corner (-225, 170, -135)
- Right eye corner (225, 170, -135)
- Left mouth corner (-150, -150, -125)
- Right mouth corner (150, -150, -125)

### Light Condition Thresholds

| Condition | Brightness Range (0-255) |
|-----------|-------------------------|
| Insufficient | 0 - 25 |
| Very Low | 25 - 40 |
| Low | 40 - 70 |
| Moderate | 70 - 120 |
| Good | 120 - 180 |
| Excellent | 180 - 255 |

### CLAHE Parameters

- Clip Limit: 2.0
- Tile Grid Size: 8x8
- Color Space: LAB (L channel only)

## Security Features

### Anti-Spoofing Measures

1. **Multiple Face Detection** - Rejects frames with multiple faces
2. **Texture Analysis** - Detects photo/print attacks
3. **Depth Analysis** - Detects flat surface attacks
4. **Motion Analysis** - Requires natural movement
5. **Confidence Thresholding** - Low confidence frames rejected

### Biometric Fallback Security

1. **Secure Token Generation** - Cryptographically secure tokens
2. **Token Expiration** - 15-minute validity
3. **Device Capability Verification** - Method selection based on actual capabilities
4. **Infrared Priority** - Most secure method for low-light conditions

### OTP Security

1. **State-Based Locking** - OTP locked until verification success
2. **Automatic Release** - OTP released only on successful verification
3. **Short Validity** - 5-minute OTP validity after release
4. **One-Time Use** - Single-use OTP codes

## Performance Metrics

Target performance:
- **Landmark Extraction**: <50ms per frame
- **Liveness Verification**: <100ms per frame
- **CLAHE Enhancement**: <30ms per frame
- **API Response Time**: <200ms (excluding network latency)

## Error Handling

### Common Error Scenarios

1. **No Face Detected**
   - Status: `no_face_detected`
   - Action: Request user to reposition

2. **Multiple Faces Detected**
   - Status: `multiple_faces_detected`
   - Action: Request single face in frame

3. **Low Confidence**
   - Status: `low_confidence`
   - Action: Improve lighting or face visibility

4. **Low Light Conditions**
   - Status: `low_light_detected`
   - Action: Apply CLAHE or trigger fallback

5. **Spoof Detected**
   - Status: `spoof_detected`
   - Action: Reject and require manual verification

## Integration Points

### External Systems

- **Camera/Mobile App** - Frame capture and transmission
- **Device Biometric APIs** - Fingerprint/FaceID integration
- **Infrared Sensors** - Low-light biometric verification
- **Dispatch System** - OTP release on verification success
- **Notification System** - Verification status updates

### Internal Systems

- **Risk Engine** - Pre-ride risk assessment
- **Auth System** - Driver authentication
- **Ride Management** - Ride lifecycle management
- **Analytics System** - Liveness success rates and patterns

## Future Enhancements

- Active liveness challenges (blink instructions, head movements)
- Deep learning-based spoof detection
- Voice liveness detection (multi-modal)
- Behavioral biometrics (typing patterns, device usage)
- Continuous authentication during ride
- 3D face reconstruction for depth analysis

## Testing

### Unit Tests

```bash
cd ai_engine/liveness_detection
pytest tests/
```

### Integration Tests

```bash
cd backend
pytest tests/test_liveness_api.py
```

### Manual Testing

Use the provided test scripts in each module to verify functionality:
- `face_landmarker.py` - Landmark extraction
- `passive_liveness.py` - Liveness detection
- `low_light_fallback.py` - Low-light handling

## Troubleshooting

### Common Issues

1. **MediaPipe Initialization Failed**
   - Ensure MediaPipe is properly installed
   - Check Python version compatibility (3.8+)

2. **OpenCV Import Error**
   - Install `opencv-python` and `opencv-contrib-python`
   - Verify correct version (4.8.0+)

3. **Low Detection Rate**
   - Check lighting conditions
   - Verify camera resolution (min 640x480)
   - Adjust confidence thresholds

4. **Memory Issues**
   - Limit frame sequence length
   - Implement frame skipping
   - Use smaller model complexity

## License

Proprietary - OptimalRide Project for SIH 2026

## Authors

OptimalRide AI Research Team
