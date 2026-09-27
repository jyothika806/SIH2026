import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../providers/ride_provider.dart';
import '../../config/app_config.dart';

class DriverHomeScreen extends StatefulWidget {
  const DriverHomeScreen({super.key});

  @override
  State<DriverHomeScreen> createState() => _DriverHomeScreenState();
}

class _DriverHomeScreenState extends State<DriverHomeScreen> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Driver Console'),
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
      body: _buildBody(),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() {
            _selectedIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.home),
            label: 'Home',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.history),
            label: 'History',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.account_balance_wallet),
            label: 'Earnings',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person),
            label: 'Profile',
          ),
        ],
      ),
    );
  }

  Widget _buildBody() {
    switch (_selectedIndex) {
      case 0:
        return _buildHomeTab();
      case 1:
        return _buildHistoryTab();
      case 2:
        return _buildEarningsTab();
      case 3:
        return _buildProfileTab();
      default:
        return _buildHomeTab();
    }
  }

  Widget _buildHomeTab() {
    return Consumer<RideProvider>(
      builder: (context, rideProvider, child) {
        if (rideProvider.hasActiveRide) {
          return _buildActiveRideView(rideProvider);
        } else {
          return _buildAvailableView();
        }
      },
    );
  }

  Widget _buildAvailableView() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.directions_car,
            size: 100,
            color: AppConfig.primaryColor,
          ),
          const SizedBox(height: 24),
          Text(
            'You\'re Online',
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            'Waiting for ride requests...',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                  color: AppConfig.textSecondaryColor,
                ),
          ),
          const SizedBox(height: 48),
          ElevatedButton.icon(
            onPressed: () {
              // Go offline
            },
            icon: const Icon(Icons.power_settings_new),
            label: const Text('Go Offline'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppConfig.dangerColor,
            ),
          ),
        ],
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
                  Text(
                    'Active Ride',
                    style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
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
                      'Navigation View',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Map integration coming soon',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppConfig.textSecondaryColor,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: () {
              // Complete ride
            },
            icon: const Icon(Icons.check_circle),
            label: const Text('Complete Ride'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppConfig.successColor,
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

  Widget _buildHistoryTab() {
    return const Center(
      child: Text('Ride History'),
    );
  }

  Widget _buildEarningsTab() {
    return const Center(
      child: Text('Earnings'),
    );
  }

  Widget _buildProfileTab() {
    return Consumer<AuthProvider>(
      builder: (context, authProvider, child) {
        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            children: [
              const CircleAvatar(
                radius: 50,
                child: Icon(Icons.person, size: 50),
              ),
              const SizedBox(height: 16),
              Text(
                'Driver',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              Text(
                authProvider.user?.phone ?? '',
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      color: AppConfig.textSecondaryColor,
                    ),
              ),
              const SizedBox(height: 24),
              Card(
                child: ListTile(
                  leading: const Icon(Icons.star),
                  title: const Text('Rating'),
                  trailing: Text(
                    '${authProvider.user?.rating ?? 5.0}',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
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
              Provider.of<AuthProvider>(context, listen: false).logout();
            },
            child: const Text('Logout'),
            style: TextButton.styleFrom(foregroundColor: AppConfig.dangerColor),
          ),
        ],
      ),
    );
  }
}
