import 'package:flutter/foundation.dart';
import '../models/ride.dart';
import '../services/api_service.dart';

class RideProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();

  Ride? _currentRide;
  List<Ride> _rideHistory = [];
  bool _isLoading = false;
  String? _errorMessage;

  Ride? get currentRide => _currentRide;
  List<Ride> get rideHistory => _rideHistory;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get hasActiveRide => _currentRide != null;

  Future<bool> bookRide({
    required double pickupLat,
    required double pickupLon,
    required double dropoffLat,
    required double dropoffLon,
    required String vehicleType,
    int seatsRequired = 1,
    bool isMidRoute = false,
    int? targetRideId,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.bookRide(
        pickupLat: pickupLat,
        pickupLon: pickupLon,
        dropoffLat: dropoffLat,
        dropoffLon: dropoffLon,
        vehicleType: vehicleType,
        seatsRequired: seatsRequired,
        isMidRoute: isMidRoute,
        targetRideId: targetRideId,
      );

      if (response['success'] == true) {
        _currentRide = Ride.fromJson(response['ride']);
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to book ride';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to book ride: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> getRide(int rideId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.getRide(rideId);

      if (response['success'] == true) {
        _currentRide = Ride.fromJson(response['ride']);
      } else {
        _errorMessage = response['message'] ?? 'Failed to get ride';
      }
    } catch (e) {
      _errorMessage = 'Failed to get ride: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> submitMidRouteConsent({
    required int midRouteRequestId,
    required String consent,
    required int passengerId,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.submitMidRouteConsent(
        midRouteRequestId: midRouteRequestId,
        consent: consent,
        passengerId: passengerId,
      );

      if (response['success'] == true) {
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to submit consent';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to submit consent: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  void updateRideStatus(String status) {
    if (_currentRide != null) {
      _currentRide = Ride(
        id: _currentRide!.id,
        driverId: _currentRide!.driverId,
        passengerId: _currentRide!.passengerId,
        vehicleType: _currentRide!.vehicleType,
        seatsTotal: _currentRide!.seatsTotal,
        seatsOccupied: _currentRide!.seatsOccupied,
        status: status,
        otpUnlocked: _currentRide!.otpUnlocked,
        estimatedDuration: _currentRide!.estimatedDuration,
        estimatedDistance: _currentRide!.estimatedDistance,
        fare: _currentRide!.fare,
        driverInfo: _currentRide!.driverInfo,
        pickupAddress: _currentRide!.pickupAddress,
        dropoffAddress: _currentRide!.dropoffAddress,
        pickupLat: _currentRide!.pickupLat,
        pickupLon: _currentRide!.pickupLon,
        dropoffLat: _currentRide!.dropoffLat,
        dropoffLon: _currentRide!.dropoffLon,
        createdAt: _currentRide!.createdAt,
        startedAt: _currentRide!.startedAt,
        completedAt: _currentRide!.completedAt,
      );
      notifyListeners();
    }
  }

  void clearCurrentRide() {
    _currentRide = null;
    notifyListeners();
  }

  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }
}
