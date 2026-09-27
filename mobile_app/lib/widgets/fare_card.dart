import 'package:flutter/material.dart';
import '../../config/app_config.dart';
import '../../models/fare_split.dart';

class FareCard extends StatelessWidget {
  final FareBreakdown fare;
  final VoidCallback? onSplitFare;

  const FareCard({
    super.key,
    required this.fare,
    this.onSplitFare,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Fare Breakdown',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppConfig.primaryColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    fare.currency,
                    style: TextStyle(
                      color: AppConfig.primaryColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildFareRow('Base Fare', fare.baseFare),
            _buildFareRow('Distance Fare', fare.distanceFare),
            _buildFareRow('Time Fare', fare.timeFare),
            if (fare.surgeAmount > 0)
              _buildFareRow(
                'Surge (${fare.surgeMultiplier}x)',
                fare.surgeAmount,
                color: AppConfig.warningColor,
              ),
            if (fare.detourSurcharge > 0)
              _buildFareRow(
                'Detour Surcharge',
                fare.detourSurcharge,
                color: AppConfig.warningColor,
              ),
            const Divider(),
            _buildFareRow('Subtotal', fare.subtotal, isBold: true),
            _buildFareRow('Platform Fee', fare.platformFee),
            const Divider(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Total',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                ),
                Text(
                  '₹${fare.totalFare.toStringAsFixed(2)}',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                        color: AppConfig.primaryColor,
                      ),
                ),
              ],
            ),
            if (onSplitFare != null) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: onSplitFare,
                  icon: const Icon(Icons.call_split),
                  label: const Text('Split Fare'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildFareRow(
    String label,
    double amount, {
    bool isBold = false,
    Color? color,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: color ?? AppConfig.textSecondaryColor,
                  fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
                ),
          ),
          Text(
            '₹${amount.toStringAsFixed(2)}',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: color,
                  fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
                ),
          ),
        ],
      ),
    );
  }
}
