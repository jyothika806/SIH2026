class FareSplit {
  final int passengerId;
  final String passengerName;
  final double sharePercentage;
  final double shareAmount;
  final bool isPrimary;

  FareSplit({
    required this.passengerId,
    required this.passengerName,
    required this.sharePercentage,
    required this.shareAmount,
    required this.isPrimary,
  });

  factory FareSplit.fromJson(Map<String, dynamic> json) {
    return FareSplit(
      passengerId: json['passenger_id'] as int,
      passengerName: json['passenger_name'] as String,
      sharePercentage: (json['share_percentage'] as num).toDouble(),
      shareAmount: (json['share_amount'] as num).toDouble(),
      isPrimary: json['is_primary'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'passenger_id': passengerId,
      'passenger_name': passengerName,
      'share_percentage': sharePercentage,
      'share_amount': shareAmount,
      'is_primary': isPrimary,
    };
  }
}

class FareBreakdown {
  final double baseFare;
  final double distanceFare;
  final double timeFare;
  final double surgeMultiplier;
  final double surgeAmount;
  final double detourSurcharge;
  final double platformFee;
  final double subtotal;
  final double totalFare;
  final String currency;

  FareBreakdown({
    required this.baseFare,
    required this.distanceFare,
    required this.timeFare,
    required this.surgeMultiplier,
    required this.surgeAmount,
    required this.detourSurcharge,
    required this.platformFee,
    required this.subtotal,
    required this.totalFare,
    required this.currency,
  });

  factory FareBreakdown.fromJson(Map<String, dynamic> json) {
    return FareBreakdown(
      baseFare: (json['base_fare'] as num).toDouble(),
      distanceFare: (json['distance_fare'] as num).toDouble(),
      timeFare: (json['time_fare'] as num).toDouble(),
      surgeMultiplier: (json['surge_multiplier'] as num).toDouble(),
      surgeAmount: (json['surge_amount'] as num).toDouble(),
      detourSurcharge: (json['detour_surcharge'] as num).toDouble(),
      platformFee: (json['platform_fee'] as num).toDouble(),
      subtotal: (json['subtotal'] as num).toDouble(),
      totalFare: (json['total_fare'] as num).toDouble(),
      currency: json['currency'] as String? ?? 'INR',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'base_fare': baseFare,
      'distance_fare': distanceFare,
      'time_fare': timeFare,
      'surge_multiplier': surgeMultiplier,
      'surge_amount': surgeAmount,
      'detour_surcharge': detourSurcharge,
      'platform_fee': platformFee,
      'subtotal': subtotal,
      'total_fare': totalFare,
      'currency': currency,
    };
  }
}
