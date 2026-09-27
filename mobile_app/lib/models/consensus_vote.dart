class ConsensusVote {
  final String voteId;
  final int rideId;
  final String proposalType;
  final Map<String, dynamic> proposalData;
  final String status;
  final int totalEligible;
  final int totalVotes;
  final int approveCount;
  final int rejectCount;
  final int remainingVotes;
  final String expiresAt;
  final double timeRemainingSeconds;

  ConsensusVote({
    required this.voteId,
    required this.rideId,
    required this.proposalType,
    required this.proposalData,
    required this.status,
    required this.totalEligible,
    required this.totalVotes,
    required this.approveCount,
    required this.rejectCount,
    required this.remainingVotes,
    required this.expiresAt,
    required this.timeRemainingSeconds,
  });

  factory ConsensusVote.fromJson(Map<String, dynamic> json) {
    return ConsensusVote(
      voteId: json['vote_id'] as String,
      rideId: json['ride_id'] as int,
      proposalType: json['proposal_type'] as String,
      proposalData: json['proposal_data'] as Map<String, dynamic>? ?? {},
      status: json['status'] as String,
      totalEligible: json['total_eligible'] as int,
      totalVotes: json['total_votes'] as int,
      approveCount: json['approve_count'] as int,
      rejectCount: json['reject_count'] as int,
      remainingVotes: json['remaining_votes'] as int,
      expiresAt: json['expires_at'] as String,
      timeRemainingSeconds: (json['time_remaining_seconds'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'vote_id': voteId,
      'ride_id': rideId,
      'proposal_type': proposalType,
      'proposal_data': proposalData,
      'status': status,
      'total_eligible': totalEligible,
      'total_votes': totalVotes,
      'approve_count': approveCount,
      'reject_count': rejectCount,
      'remaining_votes': remainingVotes,
      'expires_at': expiresAt,
      'time_remaining_seconds': timeRemainingSeconds,
    };
  }

  bool get isPending => status == 'pending';
  bool get isApproved => status == 'approved';
  bool get isRejected => status == 'rejected';
  bool get isTimeout => status == 'timeout';
  double get approvalPercentage => totalVotes > 0 ? (approveCount / totalVotes) * 100 : 0;
}
