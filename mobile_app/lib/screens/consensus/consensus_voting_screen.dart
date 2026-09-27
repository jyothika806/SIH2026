import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/consensus_provider.dart';
import '../../config/app_config.dart';

class ConsensusVotingScreen extends StatefulWidget {
  final String voteId;
  final int passengerId;

  const ConsensusVotingScreen({
    super.key,
    required this.voteId,
    required this.passengerId,
  });

  @override
  State<ConsensusVotingScreen> createState() => _ConsensusVotingScreenState();
}

class _ConsensusVotingScreenState extends State<ConsensusVotingScreen> {
  Timer? _timer;
  int _remainingSeconds = AppConfig.consensusVoteTimeoutSeconds;

  @override
  void initState() {
    super.initState();
    _startTimer();
    _loadVoteStatus();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startTimer() {
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_remainingSeconds > 0) {
        setState(() {
          _remainingSeconds--;
        });
      } else {
        timer.cancel();
        _handleTimeout();
      }
    });
  }

  Future<void> _loadVoteStatus() async {
    final consensusProvider = Provider.of<ConsensusProvider>(context, listen: false);
    await consensusProvider.getVoteStatus(widget.voteId);
  }

  void _handleTimeout() {
    Navigator.pop(context);
  }

  Future<void> _castVote(String vote) async {
    final consensusProvider = Provider.of<ConsensusProvider>(context, listen: false);
    
    final success = await consensusProvider.castVote(
      voteId: widget.voteId,
      passengerId: widget.passengerId,
      vote: vote,
    );

    if (success && mounted) {
      Navigator.pop(context, true);
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(consensusProvider.errorMessage ?? 'Failed to cast vote'),
          backgroundColor: AppConfig.dangerColor,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<ConsensusProvider>(
      builder: (context, consensusProvider, child) {
        final vote = consensusProvider.currentVote;
        
        return Dialog(
          insetPadding: const EdgeInsets.all(16),
          child: Container(
            padding: const EdgeInsets.all(24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Icon(
                      Icons.how_to_vote,
                      color: AppConfig.primaryColor,
                    ),
                    _buildTimer(),
                  ],
                ),
                const SizedBox(height: 16),
                Text(
                  'Consensus Vote',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                if (vote != null)
                  Text(
                    'Mid-route pickup request',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: AppConfig.textSecondaryColor,
                        ),
                    textAlign: TextAlign.center,
                  ),
                const SizedBox(height: 24),
                if (vote != null) _buildVoteSummary(vote),
                const SizedBox(height: 24),
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () => _castVote('reject'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppConfig.dangerColor,
                        ),
                        child: const Text('Reject'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () => _castVote('approve'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppConfig.successColor,
                        ),
                        child: const Text('Approve'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildTimer() {
    final color = _remainingSeconds <= 5 ? AppConfig.dangerColor : AppConfig.primaryColor;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.timer,
            size: 16,
            color: color,
          ),
          const SizedBox(width: 4),
          Text(
            '$_remainingSeconds',
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildVoteSummary(dynamic vote) {
    return Card(
      color: AppConfig.backgroundColor,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            _buildStatRow('Total Voters', vote.totalEligible.toString()),
            _buildStatRow('Votes Cast', vote.totalVotes.toString()),
            _buildStatRow('Approve', vote.approveCount.toString(), color: AppConfig.successColor),
            _buildStatRow('Reject', vote.rejectCount.toString(), color: AppConfig.dangerColor),
            _buildStatRow('Remaining', vote.remainingVotes.toString()),
            const SizedBox(height: 8),
            LinearProgressIndicator(
              value: vote.approvalPercentage / 100,
              backgroundColor: Colors.grey[300],
              valueColor: AlwaysStoppedAnimation<Color>(
                vote.approvalPercentage >= 50 ? AppConfig.successColor : AppConfig.warningColor,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '${vote.approvalPercentage.toStringAsFixed(0)}% Approval',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatRow(String label, String value, {Color? color}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppConfig.textSecondaryColor,
                ),
          ),
          Text(
            value,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
          ),
        ],
      ),
    );
  }
}
