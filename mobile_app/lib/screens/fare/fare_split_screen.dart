import 'package:flutter/material.dart';
import '../../config/app_config.dart';
import '../../models/fare_split.dart';

class FareSplitScreen extends StatelessWidget {
  final double totalFare;
  final List<FareSplit> allocations;
  final String splitMethod;

  const FareSplitScreen({
    super.key,
    required this.totalFare,
    required this.allocations,
    required this.splitMethod,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fare Split'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildTotalFareCard(),
            const SizedBox(height: 16),
            _buildSplitMethodCard(),
            const SizedBox(height: 16),
            _buildAllocationsList(),
            const SizedBox(height: 24),
            _buildPayButton(),
          ],
        ),
      ),
    );
  }

  Widget _buildTotalFareCard() {
    return Card(
      color: AppConfig.primaryColor,
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          children: [
            Text(
              'Total Fare',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Colors.white70,
                  ),
            ),
            const SizedBox(height: 8),
            Text(
              '₹${totalFare.toStringAsFixed(2)}',
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSplitMethodCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Row(
          children: [
            const Icon(
              Icons.call_split,
              color: AppConfig.primaryColor,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Split Method',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppConfig.textSecondaryColor,
                        ),
                  ),
                  Text(
                    splitMethod.toUpperCase(),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }

  Widget _buildAllocationsList() {
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Text(
              'Passengers',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
            ),
          ),
          const Divider(height: 1),
          ...allocations.map((allocation) => _buildAllocationTile(allocation)),
        ],
      ),
    );
  }

  Widget _buildAllocationTile(FareSplit allocation) {
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: allocation.isPrimary
            ? AppConfig.primaryColor
            : Colors.grey[300],
        child: Text(
          allocation.passengerName[0].toUpperCase(),
          style: TextStyle(
            color: allocation.isPrimary ? Colors.white : Colors.black,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
      title: Row(
        children: [
          Text(
            allocation.passengerName,
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          if (allocation.isPrimary)
            Container(
              margin: const EdgeInsets.only(left: 8),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: AppConfig.primaryColor.withOpacity(0.1),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                'YOU',
                style: TextStyle(
                  fontSize: 10,
                  color: AppConfig.primaryColor,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
        ],
      ),
      subtitle: Text('${allocation.sharePercentage.toStringAsFixed(0)}% share'),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            '₹${allocation.shareAmount.toStringAsFixed(2)}',
            style: const TextStyle(
              fontWeight: FontWeight.bold,
              fontSize: 16,
            ),
          ),
          Text(
            allocation.isPrimary ? 'To pay' : 'Paid',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: allocation.isPrimary ? AppConfig.dangerColor : AppConfig.successColor,
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildPayButton() {
    final myAllocation = allocations.firstWhere(
      (a) => a.isPrimary,
      orElse: () => allocations.first,
    );

    return SizedBox(
      width: double.infinity,
      child: ElevatedButton(
        onPressed: () {
          // Process payment
        },
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 16),
        ),
        child: Text(
          'Pay ₹${myAllocation.shareAmount.toStringAsFixed(2)}',
          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
        ),
      ),
    );
  }
}
