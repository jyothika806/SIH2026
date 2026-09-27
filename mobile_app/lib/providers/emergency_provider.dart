import 'package:flutter/foundation.dart';
import '../models/emergency_incident.dart';
import '../services/api_service.dart';

class EmergencyProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();

  EmergencyIncident? _currentIncident;
  GuardianModeSession? _guardianSession;
  bool _isSosActive = false;
  bool _isLoading = false;
  String? _errorMessage;

  EmergencyIncident? get currentIncident => _currentIncident;
  GuardianModeSession? get guardianSession => _guardianSession;
  bool get isSosActive => _isSosActive;
  bool get isGuardianModeActive => _guardianSession?.active ?? false;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  Future<bool> triggerSos({
    required int rideId,
    required double locationLat,
    required double locationLon,
    String description = 'SOS button pressed',
    Map<String, dynamic>? metadata,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.triggerSos(
        rideId: rideId,
        locationLat: locationLat,
        locationLon: locationLon,
        description: description,
        metadata: metadata,
      );

      if (response['success'] == true) {
        _currentIncident = EmergencyIncident.fromJson(response['incident']);
        _isSosActive = true;
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to trigger SOS';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to trigger SOS: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> startGuardianMode({
    required int rideId,
    required List<Map<String, String>> emergencyContacts,
    int? pingIntervalSeconds,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.startGuardianMode(
        rideId: rideId,
        emergencyContacts: emergencyContacts,
        pingIntervalSeconds: pingIntervalSeconds,
      );

      if (response['success'] == true) {
        _guardianSession = GuardianModeSession.fromJson(response['session']);
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to start Guardian Mode';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to start Guardian Mode: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> updateGuardianLocation({
    required String sessionId,
    required double locationLat,
    required double locationLon,
    double? speed,
    int? batteryLevel,
  }) async {
    try {
      final response = await _apiService.updateGuardianLocation(
        sessionId: sessionId,
        locationLat: locationLat,
        locationLon: locationLon,
        speed: speed,
        batteryLevel: batteryLevel,
      );

      return response['success'] == true;
    } catch (e) {
      _errorMessage = 'Failed to update Guardian location: $e';
      notifyListeners();
      return false;
    }
  }

  Future<bool> stopGuardianMode(String sessionId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.stopGuardianMode(sessionId);

      if (response['success'] == true) {
        _guardianSession = null;
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to stop Guardian Mode';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to stop Guardian Mode: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> resolveIncident(String incidentId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.resolveIncident(incidentId);

      if (response['success'] == true) {
        _currentIncident = null;
        _isSosActive = false;
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to resolve incident';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to resolve incident: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  void deactivateSos() {
    _isSosActive = false;
    notifyListeners();
  }

  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }
}
