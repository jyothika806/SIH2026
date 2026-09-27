import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/api_config.dart';
import '../providers/auth_provider.dart';

class ApiService {
  final String _baseUrl = ApiConfig.baseUrl;
  
  Future<Map<String, dynamic>> _post(
    String endpoint,
    Map<String, dynamic> body,
    String? token,
  ) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };

    final response = await http.post(
      url,
      headers: headers,
      body: jsonEncode(body),
    );

    return _handleResponse(response);
  }

  Future<Map<String, dynamic>> _get(
    String endpoint,
    String? token,
  ) async {
    final url = Uri.parse('$_baseUrl$endpoint');
    final headers = {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };

    final response = await http.get(url, headers: headers);
    return _handleResponse(response);
  }

  Map<String, dynamic> _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      final body = jsonDecode(response.body) as Map<String, dynamic>?;
      throw Exception(body?['detail'] ?? 'Request failed');
    }
  }

  // Auth endpoints
  Future<Map<String, dynamic>> sendOtp(String phone) async {
    return _post(
      ApiConfig.sendOtp,
      {'phone': phone},
      null,
    );
  }

  Future<Map<String, dynamic>> verifyOtp(String phone, String otp) async {
    return _post(
      ApiConfig.verifyOtp,
      {'phone': phone, 'otp': otp},
      null,
    );
  }

  Future<Map<String, dynamic>> refreshToken(String refreshToken) async {
    return _post(
      ApiConfig.refreshToken,
      {'refresh_token': refreshToken},
      null,
    );
  }

  Future<Map<String, dynamic>> logout(String token) async {
    return _post(ApiConfig.logout, {}, token);
  }

  // Ride endpoints
  Future<Map<String, dynamic>> bookRide({
    required double pickupLat,
    required double pickupLon,
    required double dropoffLat,
    required double dropoffLon,
    required String vehicleType,
    int seatsRequired = 1,
    bool isMidRoute = false,
    int? targetRideId,
  }) async {
    return _post(
      ApiConfig.bookRide,
      {
        'pickup_lat': pickupLat,
        'pickup_lon': pickupLon,
        'dropoff_lat': dropoffLat,
        'dropoff_lon': dropoffLon,
        'vehicle_type': vehicleType,
        'seats_required': seatsRequired,
        'is_mid_route': isMidRoute,
        if (targetRideId != null) 'target_ride_id': targetRideId,
      },
      null, // Will add token from provider
    );
  }

  Future<Map<String, dynamic>> getRide(int rideId, [String? token]) async {
    return _get('${ApiConfig.getRide}/$rideId', token);
  }

  Future<Map<String, dynamic>> submitMidRouteConsent({
    required int midRouteRequestId,
    required String consent,
    required int passengerId,
  }) async {
    return _post(
      ApiConfig.submitMidRouteConsent,
      {
        'mid_route_request_id': midRouteRequestId,
        'consent': consent,
        'passenger_id': passengerId,
      },
      null,
    );
  }

  // Consensus endpoints
  Future<Map<String, dynamic>> createConsensusVote({
    required int rideId,
    required String proposalType,
    required Map<String, dynamic> proposalData,
    required List<int> eligibleVoters,
    int? timeoutSeconds,
  }) async {
    return _post(
      ApiConfig.createVote,
      {
        'ride_id': rideId,
        'proposal_type': proposalType,
        'proposal_data': proposalData,
        'eligible_voters': eligibleVoters,
        if (timeoutSeconds != null) 'timeout_seconds': timeoutSeconds,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> castConsensusVote({
    required String voteId,
    required int passengerId,
    required String vote,
  }) async {
    return _post(
      ApiConfig.castVote,
      {
        'vote_id': voteId,
        'passenger_id': passengerId,
        'vote': vote,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> getVoteStatus(String voteId) async {
    return _get('${ApiConfig.voteStatus}/$voteId', null);
  }

  Future<Map<String, dynamic>> cancelVote(String voteId) async {
    return _post('${ApiConfig.cancelVote}/$voteId', {}, null);
  }

  // Fare endpoints
  Future<Map<String, dynamic>> calculateFare({
    required String vehicleType,
    required double distanceKm,
    required double durationMinutes,
    String surgeLevel = 'none',
    double detourMinutes = 0.0,
    bool applySurgeCap = true,
  }) async {
    return _post(
      ApiConfig.calculateFare,
      {
        'vehicle_type': vehicleType,
        'distance_km': distanceKm,
        'duration_minutes': durationMinutes,
        'surge_level': surgeLevel,
        'detour_minutes': detourMinutes,
        'apply_surge_cap': applySurgeCap,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> estimateFare({
    required String vehicleType,
    required double pickupLat,
    required double pickupLon,
    required double dropoffLat,
    required double dropoffLon,
    double? estimatedDistanceKm,
    double? estimatedDurationMinutes,
  }) async {
    return _post(
      ApiConfig.estimateFare,
      {
        'vehicle_type': vehicleType,
        'pickup_lat': pickupLat,
        'pickup_lon': pickupLon,
        'dropoff_lat': dropoffLat,
        'dropoff_lon': dropoffLon,
        if (estimatedDistanceKm != null) 'estimated_distance_km': estimatedDistanceKm,
        if (estimatedDurationMinutes != null) 'estimated_duration_minutes': estimatedDurationMinutes,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> splitFare({
    required double totalFare,
    required List<Map<String, dynamic>> passengers,
    required String splitMethod,
  }) async {
    return _post(
      ApiConfig.splitFare,
      {
        'total_fare': totalFare,
        'passengers': passengers,
        'split_method': splitMethod,
      },
      null,
    );
  }

  // Emergency endpoints
  Future<Map<String, dynamic>> triggerSos({
    required int rideId,
    required double locationLat,
    required double locationLon,
    String description = 'SOS button pressed',
    Map<String, dynamic>? metadata,
  }) async {
    return _post(
      ApiConfig.triggerSos,
      {
        'ride_id': rideId,
        'location_lat': locationLat,
        'location_lon': locationLon,
        'description': description,
        if (metadata != null) 'metadata': metadata,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> startGuardianMode({
    required int rideId,
    required List<Map<String, String>> emergencyContacts,
    int? pingIntervalSeconds,
  }) async {
    return _post(
      ApiConfig.startGuardian,
      {
        'ride_id': rideId,
        'emergency_contacts': emergencyContacts,
        if (pingIntervalSeconds != null) 'ping_interval_seconds': pingIntervalSeconds,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> updateGuardianLocation({
    required String sessionId,
    required double locationLat,
    required double locationLon,
    double? speed,
    int? batteryLevel,
  }) async {
    return _post(
      ApiConfig.updateGuardian,
      {
        'session_id': sessionId,
        'location_lat': locationLat,
        'location_lon': locationLon,
        if (speed != null) 'speed': speed,
        if (batteryLevel != null) 'battery_level': batteryLevel,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> stopGuardianMode(String sessionId) async {
    return _post('${ApiConfig.stopGuardian}/$sessionId', {}, null);
  }

  Future<Map<String, dynamic>> resolveIncident(String incidentId) async {
    return _post('${ApiConfig.resolveIncident}/$incidentId', {}, null);
  }

  // Gemini endpoints
  Future<Map<String, dynamic>> triageIncident({
    String? textDescription,
    String? audioTranscript,
    String? imageBase64,
    String imageMimeType = 'image/jpeg',
    Map<String, dynamic>? rideContext,
  }) async {
    return _post(
      ApiConfig.geminiTriage,
      {
        if (textDescription != null) 'text_description': textDescription,
        if (audioTranscript != null) 'audio_transcript': audioTranscript,
        if (imageBase64 != null) 'image_base64': imageBase64,
        'image_mime_type': imageMimeType,
        if (rideContext != null) 'ride_context': rideContext,
      },
      null,
    );
  }

  Future<Map<String, dynamic>> askSafetyCopilot({
    required String userMessage,
    List<Map<String, String>>? conversationHistory,
    Map<String, dynamic>? rideContext,
  }) async {
    return _post(
      ApiConfig.safetyCopilot,
      {
        'user_message': userMessage,
        if (conversationHistory != null) 'conversation_history': conversationHistory,
        if (rideContext != null) 'ride_context': rideContext,
      },
      null,
    );
  }
}
