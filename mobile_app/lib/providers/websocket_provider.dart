import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/api_config.dart';

class WebSocketProvider with ChangeNotifier {
  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  bool _isConnected = false;
  bool _isConnecting = false;
  String? _currentRideId;
  final Map<String, dynamic> _lastMessage = {};

  bool get isConnected => _isConnected;
  bool get isConnecting => _isConnecting;
  Map<String, dynamic> get lastMessage => _lastMessage;

  Future<void> connect(int rideId, String token) async {
    if (_isConnected && _currentRideId == rideId.toString()) {
      return;
    }

    _isConnecting = true;
    _currentRideId = rideId.toString();
    notifyListeners();

    try {
      final url = ApiConfig.getRideWebSocketUrl(rideId, token);
      _channel = WebSocketChannel.connect(Uri.parse(url));

      _subscription = _channel!.stream.listen(
        (message) {
          _handleMessage(message);
        },
        onError: (error) {
          _isConnected = false;
          _isConnecting = false;
          notifyListeners();
        },
        onDone: () {
          _isConnected = false;
          _isConnecting = false;
          notifyListeners();
        },
      );

      _isConnected = true;
      _isConnecting = false;
      notifyListeners();
    } catch (e) {
      _isConnected = false;
      _isConnecting = false;
      notifyListeners();
      rethrow;
    }
  }

  void _handleMessage(dynamic message) {
    if (message is String) {
      // Parse JSON message
      try {
        final data = message as String;
        // In production, parse JSON and update state
        _lastMessage.clear();
        _lastMessage['raw'] = data;
        notifyListeners();
      } catch (e) {
        debugPrint('Error parsing WebSocket message: $e');
      }
    }
  }

  void sendMessage(Map<String, dynamic> message) {
    if (_channel != null && _isConnected) {
      _channel!.sink.add(message);
    }
  }

  void sendLocationUpdate({
    required double latitude,
    required double longitude,
    double? speed,
    double? heading,
  }) {
    sendMessage({
      'type': 'location_update',
      'latitude': latitude,
      'longitude': longitude,
      'speed': speed,
      'heading': heading,
    });
  }

  void sendPing() {
    sendMessage({'type': 'ping'});
  }

  void disconnect() {
    _subscription?.cancel();
    _channel?.sink.close();
    _channel = null;
    _isConnected = false;
    _isConnecting = false;
    _currentRideId = null;
    notifyListeners();
  }

  @override
  void dispose() {
    disconnect();
    super.dispose();
  }
}
