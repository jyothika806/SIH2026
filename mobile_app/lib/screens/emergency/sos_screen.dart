import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/emergency_provider.dart';
import '../../providers/ride_provider.dart';
import '../../config/app_config.dart';

class SOSScreen extends StatefulWidget {
  const SOSScreen({super.key});

  @override
  State<SOSScreen> createState() => _SOSScreenState();
}

class _SOSScreenState extends State<SOSScreen> {
  bool _isTriggering = false;

  Future<void> _triggerSos() async {
    setState(() {
      _isTriggering = true;
    });

    final emergencyProvider = Provider.of<EmergencyProvider>(context, listen: false);
    final rideProvider = Provider.of<RideProvider>(context, listen: false);

    final ride = rideProvider.currentRide;
    if (ride == null) {
      setState(() {
        _isTriggering = false;
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('No active ride'),
            backgroundColor: AppConfig.dangerColor,
          ),
        );
      }
      return;
    }

    final success = await emergencyProvider.triggerSos(
      rideId: ride.id,
      locationLat: ride.pickupLat ?? 12.9716,
      locationLon: ride.pickupLon ?? 77.5946,
      description: 'Emergency SOS triggered by passenger',
    );

    setState(() {
      _isTriggering = false;
    });

    if (success && mounted) {
      _showSosActivatedDialog();
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(emergencyProvider.errorMessage ?? 'Failed to trigger SOS'),
          backgroundColor: AppConfig.dangerColor,
        ),
      );
    }
  }

  void _showSosActivatedDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: AppConfig.dangerColor,
        title: Row(
          children: [
            const Icon(Icons.emergency, color: Colors.white),
            const SizedBox(width: 8),
            const Text(
              'SOS ACTIVATED',
              style: TextStyle(color: Colors.white),
            ),
          ],
        ),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.notifications_active,
              size: 80,
              color: Colors.white,
            ),
            SizedBox(height: 16),
            Text(
              'Emergency contacts and safety team have been notified',
              style: TextStyle(color: Colors.white),
              textAlign: TextAlign.center,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              Navigator.pop(context);
            },
            child: const Text(
              'OK',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Emergency SOS'),
        backgroundColor: AppConfig.dangerColor,
        foregroundColor: Colors.white,
      ),
      body: Consumer<EmergencyProvider>(
        builder: (context, emergencyProvider, child) {
          return Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(
                  Icons.emergency,
                  size: 100,
                  color: AppConfig.dangerColor,
                ),
                const SizedBox(height: 24),
                Text(
                  'Emergency SOS',
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppConfig.dangerColor,
                      ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  'Tap the button below to trigger emergency alert',
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: AppConfig.textSecondaryColor,
                      ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 48),
                GestureDetector(
                  onTap: _isTriggering ? null : _triggerSos,
                  child: Container(
                    height: 200,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _isTriggering
                          ? Colors.grey
                          : AppConfig.dangerColor,
                      boxShadow: [
                        BoxShadow(
                          color: AppConfig.dangerColor.withOpacity(0.3),
                          blurRadius: 20,
                          spreadRadius: 10,
                        ),
                      ],
                    ),
                    child: Center(
                      child: _isTriggering
                          ? const CircularProgressIndicator(
                              valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                            )
                          : const Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.emergency,
                                  size: 60,
                                  color: Colors.white,
                                ),
                                SizedBox(height: 8),
                                Text(
                                  'TAP TO ACTIVATE',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.bold,
                                    fontSize: 18,
                                  ),
                                ),
                              ],
                            ),
                    ),
                  ),
                ),
                const SizedBox(height: 48),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            const Icon(Icons.info, color: AppConfig.primaryColor),
                            const SizedBox(width: 8),
                            Text(
                              'What happens when you activate SOS?',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.bold,
                                  ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        _buildInfoItem('Emergency contacts will be notified via SMS'),
                        _buildInfoItem('Safety team will be alerted immediately'),
                        _buildInfoItem('Your live location will be shared'),
                        _buildInfoItem('Emergency siren will be activated'),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildInfoItem(String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        children: [
          const Icon(Icons.check_circle, color: AppConfig.successColor, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}
