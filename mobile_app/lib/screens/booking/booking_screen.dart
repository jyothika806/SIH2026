import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/ride_provider.dart';
import '../../providers/emergency_provider.dart';
import '../../providers/auth_provider.dart';
import '../../config/app_config.dart';
import '../emergency/sos_screen.dart';

class BookingScreen extends StatefulWidget {
  const BookingScreen({super.key});

  @override
  State<BookingScreen> createState() => _BookingScreenState();
}

class _BookingScreenState extends State<BookingScreen> {
  String _selectedVehicle = AppConfig.vehicleBike;
  int _seatsRequired = 1;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Book a Ride'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications),
            onPressed: () {
              // Show notifications
            },
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () {
              _showLogoutDialog();
            },
          ),
        ],
      ),
      body: Consumer<RideProvider>(
        builder: (context, rideProvider, child) {
          if (rideProvider.hasActiveRide) {
            return _buildActiveRideView(rideProvider);
          }
          return _buildBookingView();
        },
      ),
      floatingActionButton: Consumer<EmergencyProvider>(
        builder: (context, emergencyProvider, child) {
          return FloatingActionButton.extended(
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => const SOSScreen(),
                ),
              );
            },
            backgroundColor: AppConfig.dangerColor,
            icon: const Icon(Icons.emergency),
            label: const Text('SOS'),
          );
        },
      ),
    );
  }

  Widget _buildBookingView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildLocationInput(),
          const SizedBox(height: 24),
          _buildVehicleSelection(),
          const SizedBox(height: 24),
          _buildSeatSelection(),
          const SizedBox(height: 24),
          _buildFareEstimate(),
          const SizedBox(height: 24),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: _bookRide,
              child: const Text('Book Ride'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationInput() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Location',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 16),
            ListTile(
              leading: const Icon(Icons.circle, color: AppConfig.successColor, size: 12),
              title: const Text('Pickup Location'),
              subtitle: const Text('Current location'),
              trailing: const Icon(Icons.my_location),
            ),
            const Divider(),
            ListTile(
              leading: const Icon(Icons.location_on, color: AppConfig.dangerColor),
              title: const Text('Dropoff Location'),
              subtitle: const Text('Select destination'),
              trailing: const Icon(Icons.search),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVehicleSelection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Select Vehicle',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                _buildVehicleOption(
                  icon: Icons.motorcycle,
                  label: 'Bike',
                  value: AppConfig.vehicleBike,
                ),
                const SizedBox(width: 12),
                _buildVehicleOption(
                  icon: Icons.directions_car,
                  label: 'Auto',
                  value: AppConfig.vehicleAuto,
                ),
                const SizedBox(width: 12),
                _buildVehicleOption(
                  icon: Icons.local_taxi,
                  label: 'Cab',
                  value: AppConfig.vehicleCab,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVehicleOption({
    required IconData icon,
    required String label,
    required String value,
  }) {
    final isSelected = _selectedVehicle == value;
    return Expanded(
      child: InkWell(
        onTap: () {
          setState(() {
            _selectedVehicle = value;
          });
        },
        child: Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            border: Border.all(
              color: isSelected ? AppConfig.primaryColor : Colors.grey,
              width: isSelected ? 2 : 1,
            ),
            borderRadius: BorderRadius.circular(8),
            color: isSelected ? AppConfig.primaryColor.withOpacity(0.1) : null,
          ),
          child: Column(
            children: [
              Icon(
                icon,
                color: isSelected ? AppConfig.primaryColor : Colors.grey,
              ),
              const SizedBox(height: 8),
              Text(
                label,
                style: TextStyle(
                  color: isSelected ? AppConfig.primaryColor : Colors.grey,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSeatSelection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Seats Required',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: List.generate(4, (index) {
                final seats = index + 1;
                final isSelected = _seatsRequired == seats;
                return InkWell(
                  onTap: () {
                    setState(() {
                      _seatsRequired = seats;
                    });
                  },
                  child: Container(
                    width: 50,
                    height: 50,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: isSelected ? AppConfig.primaryColor : Colors.grey[200],
                    ),
                    child: Center(
                      child: Text(
                        seats.toString(),
                        style: TextStyle(
                          color: isSelected ? Colors.white : Colors.black,
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                        ),
                      ),
                    ),
                  ),
                );
              }),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFareEstimate() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Estimated Fare',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '₹15-25',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppConfig.primaryColor,
                      ),
                ),
                Text(
                  'Est. 15-20 min',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: AppConfig.textSecondaryColor,
                      ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActiveRideView(RideProvider rideProvider) {
    final ride = rideProvider.currentRide!;
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.directions_car, color: AppConfig.primaryColor),
                      const SizedBox(width: 8),
                      Text(
                        'Active Ride',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.bold,
                            ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _buildInfoRow('Vehicle Type', ride.vehicleType.toUpperCase()),
                  _buildInfoRow('Status', ride.status.toUpperCase()),
                  _buildInfoRow('Seats', '${ride.seatsOccupied}/${ride.seatsTotal}'),
                  if (ride.fare != null)
                    _buildInfoRow('Fare', '₹${ride.fare!.toStringAsFixed(2)}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: Card(
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(
                      Icons.map,
                      size: 80,
                      color: AppConfig.textSecondaryColor,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Live Tracking',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: AppConfig.textSecondaryColor,
                ),
          ),
          Text(
            value,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
        ],
      ),
    );
  }

  Future<void> _bookRide() async {
    final rideProvider = Provider.of<RideProvider>(context, listen: false);
    
    final success = await rideProvider.bookRide(
      pickupLat: 12.9716,
      pickupLon: 77.5946,
      dropoffLat: 12.9352,
      dropoffLon: 77.6245,
      vehicleType: _selectedVehicle,
      seatsRequired: _seatsRequired,
    );

    if (!success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(rideProvider.errorMessage ?? 'Failed to book ride'),
          backgroundColor: AppConfig.dangerColor,
        ),
      );
    }
  }

  void _showLogoutDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Logout'),
        content: const Text('Are you sure you want to logout?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              context.read<AuthProvider>().logout();
            },
            child: const Text('Logout'),
            style: TextButton.styleFrom(foregroundColor: AppConfig.dangerColor),
          ),
        ],
      ),
    );
  }
}
