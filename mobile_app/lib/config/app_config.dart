class AppConfig {
  static const String appName = 'OptimalRide';
  static const String appVersion = '1.0.0';
  
  // Colors
  static const Color primaryColor = Color(0xFF2563EB);
  static const Color secondaryColor = Color(0xFF10B981);
  static const Color dangerColor = Color(0xFFEF4444);
  static const Color warningColor = Color(0xFFF59E0B);
  static const Color successColor = Color(0xFF10B981);
  static const Color backgroundColor = Color(0xFFF9FAFB);
  static const Color cardColor = Color(0xFFFFFFFF);
  static const Color textColor = Color(0xFF1F2937);
  static const Color textSecondaryColor = Color(0xFF6B7280);
  
  // Vehicle Types
  static const String vehicleBike = 'bike';
  static const String vehicleAuto = 'auto';
  static const String vehicleCab = 'cab';
  
  // User Roles
  static const String rolePassenger = 'passenger';
  static const String roleDriver = 'driver';
  static const String roleAdmin = 'admin';
  
  // Ride Status
  static const String rideRequested = 'requested';
  static const String rideSearching = 'searching';
  static const String rideDriverAssigned = 'driver_assigned';
  static const String rideArrived = 'arrived';
  static const String rideInProgress = 'in_progress';
  static const String rideCompleted = 'completed';
  static const String rideCancelled = 'cancelled';
  
  // Consensus Vote Timeout
  static const int consensusVoteTimeoutSeconds = 15;
  
  // SOS Siren Duration
  static const int sosSirenDurationSeconds = 30;
  
  // Guardian Mode Ping Interval
  static const int guardianPingIntervalSeconds = 10;
}
