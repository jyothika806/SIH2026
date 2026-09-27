class EmergencyIncident {
  final String incidentId;
  final int rideId;
  final int userId;
  final String userRole;
  final String emergencyType;
  final String severity;
  final double locationLat;
  final double locationLon;
  final String description;
  final Map<String, dynamic> metadata;
  final bool resolved;
  final String? resolvedAt;
  final String timestamp;

  EmergencyIncident({
    required this.incidentId,
    required this.rideId,
    required this.userId,
    required this.userRole,
    required this.emergencyType,
    required this.severity,
    required this.locationLat,
    required this.locationLon,
    required this.description,
    required this.metadata,
    required this.resolved,
    this.resolvedAt,
    required this.timestamp,
  });

  factory EmergencyIncident.fromJson(Map<String, dynamic> json) {
    return EmergencyIncident(
      incidentId: json['incident_id'] as String,
      rideId: json['ride_id'] as int,
      userId: json['user_id'] as int,
      userRole: json['user_role'] as String,
      emergencyType: json['emergency_type'] as String,
      severity: json['severity'] as String,
      locationLat: (json['location_lat'] as num).toDouble(),
      locationLon: (json['location_lon'] as num).toDouble(),
      description: json['description'] as String,
      metadata: json['metadata'] as Map<String, dynamic>? ?? {},
      resolved: json['resolved'] as bool? ?? false,
      resolvedAt: json['resolved_at'] as String?,
      timestamp: json['timestamp'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'incident_id': incidentId,
      'ride_id': rideId,
      'user_id': userId,
      'user_role': userRole,
      'emergency_type': emergencyType,
      'severity': severity,
      'location_lat': locationLat,
      'location_lon': locationLon,
      'description': description,
      'metadata': metadata,
      'resolved': resolved,
      'resolved_at': resolvedAt,
      'timestamp': timestamp,
    };
  }

  bool get isCritical => severity == 'critical';
  bool get isHigh => severity == 'high';
  bool get isMedium => severity == 'medium';
  bool get isLow => severity == 'low';
  bool get isSos => emergencyType == 'sos_button';
  bool get isGuardianMode => emergencyType == 'guardian_mode';
}

class GuardianModeSession {
  final String sessionId;
  final int rideId;
  final int userId;
  final List<EmergencyContact> emergencyContacts;
  final String startedAt;
  final String lastPing;
  final int pingIntervalSeconds;
  final int locationUpdatesCount;
  final bool active;

  GuardianModeSession({
    required this.sessionId,
    required this.rideId,
    required this.userId,
    required this.emergencyContacts,
    required this.startedAt,
    required this.lastPing,
    required this.pingIntervalSeconds,
    required this.locationUpdatesCount,
    required this.active,
  });

  factory GuardianModeSession.fromJson(Map<String, dynamic> json) {
    final contacts = (json['emergency_contacts'] as List?)
            ?.map((e) => EmergencyContact.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];

    return GuardianModeSession(
      sessionId: json['session_id'] as String,
      rideId: json['ride_id'] as int,
      userId: json['user_id'] as int,
      emergencyContacts: contacts,
      startedAt: json['started_at'] as String,
      lastPing: json['last_ping'] as String,
      pingIntervalSeconds: json['ping_interval_seconds'] as int,
      locationUpdatesCount: json['location_updates_count'] as int,
      active: json['active'] as bool,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'session_id': sessionId,
      'ride_id': rideId,
      'user_id': userId,
      'emergency_contacts': emergencyContacts.map((e) => e.toJson()).toList(),
      'started_at': startedAt,
      'last_ping': lastPing,
      'ping_interval_seconds': pingIntervalSeconds,
      'location_updates_count': locationUpdatesCount,
      'active': active,
    };
  }
}

class EmergencyContact {
  final String phone;
  final String name;

  EmergencyContact({
    required this.phone,
    required this.name,
  });

  factory EmergencyContact.fromJson(Map<String, dynamic> json) {
    return EmergencyContact(
      phone: json['phone'] as String,
      name: json['name'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'phone': phone,
      'name': name,
    };
  }
}
