class User {
  final int id;
  final String phone;
  final String role;
  final String? fcmToken;
  final int? age;
  final String? gender;
  final double rating;
  final bool isActive;
  final DateTime? createdAt;

  User({
    required this.id,
    required this.phone,
    required this.role,
    this.fcmToken,
    this.age,
    this.gender,
    required this.rating,
    required this.isActive,
    this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as int,
      phone: json['phone'] as String,
      role: json['role'] as String,
      fcmToken: json['fcm_token'] as String?,
      age: json['age'] as int?,
      gender: json['gender'] as String?,
      rating: (json['rating'] as num?)?.toDouble() ?? 5.0,
      isActive: json['is_active'] as bool? ?? true,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'phone': phone,
      'role': role,
      'fcm_token': fcmToken,
      'age': age,
      'gender': gender,
      'rating': rating,
      'is_active': isActive,
      'created_at': createdAt?.toIso8601String(),
    };
  }

  bool get isDriver => role == 'driver';
  bool get isPassenger => role == 'passenger';
  bool get isAdmin => role == 'admin';
}
