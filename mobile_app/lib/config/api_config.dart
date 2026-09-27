class ApiConfig {
  // Base URL - Update with your backend server address
  static const String baseUrl = 'http://localhost:8000';
  
  // API Endpoints
  static const String apiVersion = '/api/v1';
  
  // Auth
  static const String sendOtp = '$apiVersion/auth/send-otp';
  static const String verifyOtp = '$apiVersion/auth/verify-otp';
  static const String refreshToken = '$apiVersion/auth/refresh';
  static const String logout = '$apiVersion/auth/logout';
  
  // Rides
  static const String bookRide = '$apiVersion/rides/book';
  static const String getRide = '$apiVersion/rides';
  static const String submitMidRouteConsent = '$apiVersion/rides/mid-route/consent';
  static const String suggestModalShift = '$apiVersion/rides/modal-shift/suggest';
  static const String updateTelemetry = '$apiVersion/rides/telemetry';
  static const String websocketRideTracking = '/api/v1/rides/ws/rides';
  
  // Liveness
  static const String submitLiveness = '$apiVersion/liveness/submit';
  static const String verifyLiveness = '$apiVersion/liveness/verify';
  
  // Risk
  static const String evaluateRisk = '$apiVersion/risk/evaluate';
  
  // Gemini AI
  static const String geminiTriage = '$apiVersion/gemini/triage';
  static const String safetyCopilot = '$apiVersion/gemini/safety-copilot';
  static const String geminiStatus = '$apiVersion/gemini/status';
  
  // Consensus
  static const String createVote = '$apiVersion/consensus/create';
  static const String castVote = '$apiVersion/consensus/cast';
  static const String voteStatus = '$apiVersion/consensus/status';
  static const String cancelVote = '$apiVersion/consensus/cancel';
  
  // Fare
  static const String calculateFare = '$apiVersion/fare/calculate';
  static const String estimateFare = '$apiVersion/fare/estimate';
  static const String splitFare = '$apiVersion/fare/split';
  static const String detourSurcharge = '$apiVersion/fare/detour-surcharge';
  static const String surgeLevel = '$apiVersion/fare/surge-level';
  
  // Emergency
  static const String triggerSos = '$apiVersion/emergency/sos';
  static const String startGuardian = '$apiVersion/emergency/guardian/start';
  static const String updateGuardian = '$apiVersion/emergency/guardian/update';
  static const String stopGuardian = '$apiVersion/emergency/guardian/stop';
  static const String logIncident = '$apiVersion/emergency/log';
  static const String resolveIncident = '$apiVersion/emergency/resolve';
  static const String emergencyConfig = '$apiVersion/emergency/config';
  static const String checkLowLight = '$apiVersion/emergency/check-low-light';
  
  // WebSocket
  static String getRideWebSocketUrl(int rideId, String token) {
    return 'ws://localhost:8000$websocketRideTracking/$rideId/track?token=$token';
  }
}
