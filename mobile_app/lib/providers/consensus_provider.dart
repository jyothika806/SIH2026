import 'package:flutter/foundation.dart';
import '../models/consensus_vote.dart';
import '../services/api_service.dart';

class ConsensusProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();

  ConsensusVote? _currentVote;
  bool _isLoading = false;
  String? _errorMessage;

  ConsensusVote? get currentVote => _currentVote;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  bool get hasActiveVote => _currentVote != null && _currentVote!.isPending;

  Future<bool> createVote({
    required int rideId,
    required String proposalType,
    required Map<String, dynamic> proposalData,
    required List<int> eligibleVoters,
    int? timeoutSeconds,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.createConsensusVote(
        rideId: rideId,
        proposalType: proposalType,
        proposalData: proposalData,
        eligibleVoters: eligibleVoters,
        timeoutSeconds: timeoutSeconds,
      );

      if (response['success'] == true) {
        _currentVote = ConsensusVote.fromJson(response['vote']);
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to create vote';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to create vote: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> castVote({
    required String voteId,
    required int passengerId,
    required String vote,
  }) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.castConsensusVote(
        voteId: voteId,
        passengerId: passengerId,
        vote: vote,
      );

      if (response['success'] == true) {
        _currentVote = ConsensusVote.fromJson(response['summary']);
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to cast vote';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to cast vote: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> getVoteStatus(String voteId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.getVoteStatus(voteId);

      if (response['success'] == true) {
        _currentVote = ConsensusVote.fromJson(response['vote_status']);
      } else {
        _errorMessage = response['message'] ?? 'Failed to get vote status';
      }
    } catch (e) {
      _errorMessage = 'Failed to get vote status: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> cancelVote(String voteId) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final response = await _apiService.cancelVote(voteId);

      if (response['success'] == true) {
        _currentVote = null;
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _errorMessage = response['message'] ?? 'Failed to cancel vote';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _errorMessage = 'Failed to cancel vote: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  void updateVoteFromWebSocket(Map<String, dynamic> data) {
    if (data.containsKey('vote')) {
      _currentVote = ConsensusVote.fromJson(data['vote']);
      notifyListeners();
    }
  }

  void clearCurrentVote() {
    _currentVote = null;
    notifyListeners();
  }

  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }
}
