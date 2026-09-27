class Ride {
  final int id;
  final int driverId;
  final int passengerId;
  final String vehicleType;
  final int seatsTotal;
  final int seatsOccupied;
  final String status;
  final bool otpUnlocked;
  final int? estimatedDuration;
  final int? estimatedDistance;
  final double? fare;
  final DriverInfo? driverInfo;
  final String? pickupAddress;
  final String? dropoffAddress;
  final double? pickupLat;
  final double? pickupLon;
  final double? dropoffLat;
  final double? dropoffLon;
  final DateTime? createdAt;
  final DateTime? startedAt;
  final DateTime? completedAt;

  Ride({
    required this.id,
    required this.driverId,
    required this.passengerId,
    required this.vehicleType,
    required this.seatsTotal,
    required this.seatsOccupied,
    required this.status,
    required this.otpUnlocked,
    this.estimatedDuration,
    this.estimatedDistance,
    this.fare,
    this.driverInfo,
    this.pickupAddress,
    this.dropoffAddress,
    this.pickupLat,
    this.pickupLon,
    this.dropoffLat,
    this.dropoffLon,
    this.createdAt,
    this.startedAt,
    this.completedAt,
  });

  factory Ride.fromJson(Map<String, dynamic> json) {
    return Ride(
      id: json['id'] as int,
      driverId: json['driver_id'] as int,
      passengerId: json['passenger_id'] as int,
      vehicleType: json['vehicle_type'] as String,
      seatsTotal: json['seats_total'] as int,
      seatsOccupied: json['seats_occupied'] as int,
      status: json['status'] as String,
      otpUnlocked: json['otp_unlocked'] as bool,
      estimatedDuration: json['estimated_duration'] as int?,
      estimatedDistance: json['estimated_distance'] as int?,
      fare: (json['fare'] as num?)?.toDouble(),
      driverInfo: json['driver_info'] != null
          ? DriverInfo.fromJson(json['driver_info'])
          : null,
      pickupAddress: json['pickup_address'] as String?,
      dropoffAddress: json['dropoff_address'] as String?,
      pickupLat: (json['pickup_lat'] as num?)?.toDouble(),
      pickupLon: (json['pickup_lon'] as num?)?.toDouble(),
      dropoffLat: (json['dropoff_lat'] as num?)?.toDouble(),
      dropoffLon: (json['dropoff_lon'] as num?)?.toDouble(),
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : null,
      startedAt: json['started_at'] != null
          ? DateTime.parse(json['started_at'] as String)
          : null,
      completedAt: json['completed_at'] != null
          ? DateTime.parse(json['completed_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'driver_id': driverId,
      'passenger_id': passengerId,
      'vehicle_type': vehicleType,
      'seats_total': seatsTotal,
      'seats_occupied': seatsOccupied,
      'status': status,
      'otp_unlocked': otpUnlocked,
      'estimated_duration': estimatedDuration,
      'estimated_distance': estimatedDistance,
      'fare': fare,
      'driver_info': driverInfo?.toJson(),
      'pickup_address': pickupAddress,
      'dropoff_address': dropoffAddress,
      'pickup_lat': pickupLat,
      'pickup_lon': pickupLon,
      'dropoff_lat': dropoffLat,
      'dropoff_lon': dropoffLon,
      'created_at': createdAt?.toIso8601String(),
      'started_at': startedAt?.toIso8601String(),
      'completed_at': completedAt?.toIso8601String(),
    };
  }
}

class DriverInfo {
  final int id;
  final int? age;
  final String? gender;
  final double rating;

  DriverInfo({
    required this.id,
    this.age,
    this.gender,
    required this.rating,
  });

  factory DriverInfo.fromJson(Map<String, dynamic> json) {
    return DriverInfo(
      id: json['id'] as int,
      age: json['age'] as int?,
      gender: json['gender'] as String?,
      rating: (json['rating'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'age': age,
      'gender': gender,
      'rating': rating,
    };
  }
}
