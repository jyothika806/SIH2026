import 'dart:async';
import 'package:flutter/material.dart';
import '../../config/app_config.dart';

class ConsensusTimer extends StatefulWidget {
  final int totalSeconds;
  final VoidCallback? onTimeout;
  final VoidCallback? onTick;

  const ConsensusTimer({
    super.key,
    required this.totalSeconds,
    this.onTimeout,
    this.onTick,
  });

  @override
  State<ConsensusTimer> createState() => _ConsensusTimerState();
}

class _ConsensusTimerState extends State<ConsensusTimer> {
  late Timer _timer;
  late int _remainingSeconds;

  @override
  void initState() {
    super.initState();
    _remainingSeconds = widget.totalSeconds;
    _startTimer();
  }

  @override
  void dispose() {
    _timer.cancel();
    super.dispose();
  }

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_remainingSeconds > 0) {
        setState(() {
          _remainingSeconds--;
        });
        widget.onTick?.call();
      } else {
        timer.cancel();
        widget.onTimeout?.call();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final progress = _remainingSeconds / widget.totalSeconds;
    final isUrgent = _remainingSeconds <= 5;
    final color = isUrgent ? AppConfig.dangerColor : AppConfig.primaryColor;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color, width: 2),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.timer,
                color: color,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                '$_remainingSeconds',
                style: TextStyle(
                  color: color,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(width: 4),
              Text(
                'sec',
                style: TextStyle(
                  color: color,
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          SizedBox(
            width: 100,
            child: LinearProgressIndicator(
              value: progress,
              backgroundColor: Colors.grey[300],
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
          ),
        ],
      ),
    );
  }
}
