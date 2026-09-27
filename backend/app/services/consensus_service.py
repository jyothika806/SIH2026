"""
Co-Passenger WebSocket Consensus Voting Protocol Service

This module implements:
- 15-second timed consensus voting for mid-route decisions
- WebSocket-based real-time vote coordination
- Automatic vote resolution with configurable approval ratio
- Vote timeout handling and automatic rejection

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

import asyncio
import logging
from typing import Dict, List, Optional, Literal
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from enum import Enum

from app.core.config import get_settings
from app.db.models import Ride, MidRouteRequest, User
from app.api.v1.rides import manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class VoteStatus(str, Enum):
    """Vote status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class ConsensusVote:
    """
    Represents a consensus voting session.
    
    Attributes:
        vote_id: Unique vote identifier
        ride_id: Associated ride ID
        proposal_type: Type of proposal (mid_route_pickup, route_change, etc.)
        proposal_data: JSON data about the proposal
        eligible_voters: List of passenger IDs eligible to vote
        votes: Dict of passenger_id -> vote (approve/reject)
        status: Current vote status
        created_at: Vote creation timestamp
        expires_at: Vote expiration timestamp
        timeout_seconds: Timeout duration in seconds
    """
    
    def __init__(
        self,
        vote_id: str,
        ride_id: int,
        proposal_type: str,
        proposal_data: Dict,
        eligible_voters: List[int],
        timeout_seconds: int = None
    ):
        self.vote_id = vote_id
        self.ride_id = ride_id
        self.proposal_type = proposal_type
        self.proposal_data = proposal_data
        self.eligible_voters = eligible_voters
        self.votes: Dict[int, Literal["approve", "reject"]] = {}
        self.status = VoteStatus.PENDING
        self.created_at = datetime.utcnow()
        self.timeout_seconds = timeout_seconds or settings.consensus_vote_timeout_seconds
        self.expires_at = self.created_at + timedelta(seconds=self.timeout_seconds)
        self._task: Optional[asyncio.Task] = None
    
    def cast_vote(self, passenger_id: int, vote: Literal["approve", "reject"]) -> bool:
        """
        Cast a vote for a passenger.
        
        Args:
            passenger_id: Passenger ID
            vote: Vote value (approve/reject)
            
        Returns:
            True if vote was cast, False if passenger already voted or not eligible
        """
        if passenger_id not in self.eligible_voters:
            logger.warning(f"Passenger {passenger_id} not eligible to vote")
            return False
        
        if passenger_id in self.votes:
            logger.warning(f"Passenger {passenger_id} already voted")
            return False
        
        self.votes[passenger_id] = vote
        logger.info(f"Vote cast: passenger {passenger_id} voted {vote}")
        return True
    
    def calculate_result(self) -> VoteStatus:
        """
        Calculate vote result based on current votes.
        
        Returns:
            VoteStatus indicating the result
        """
        if not self.votes:
            return VoteStatus.PENDING
        
        total_eligible = len(self.eligible_voters)
        total_votes = len(self.votes)
        approve_count = sum(1 for v in self.votes.values() if v == "approve")
        reject_count = sum(1 for v in self.votes.values() if v == "reject")
        
        # Check if all votes are in
        if total_votes >= total_eligible:
            if approve_count > reject_count:
                return VoteStatus.APPROVED
            else:
                return VoteStatus.REJECTED
        
        # Check if we can decide early based on approval ratio
        if total_votes > 0:
            approval_ratio = approve_count / total_votes
            if approval_ratio >= settings.consensus_min_approval_ratio:
                return VoteStatus.APPROVED
            elif reject_count > (total_eligible - approve_count):
                # Cannot reach approval threshold
                return VoteStatus.REJECTED
        
        return VoteStatus.PENDING
    
    def get_vote_summary(self) -> Dict:
        """
        Get vote summary for broadcasting.
        
        Returns:
            Dict with vote summary
        """
        total_eligible = len(self.eligible_voters)
        total_votes = len(self.votes)
        approve_count = sum(1 for v in self.votes.values() if v == "approve")
        reject_count = sum(1 for v in self.votes.values() if v == "reject")
        remaining = total_eligible - total_votes
        
        return {
            "vote_id": self.vote_id,
            "ride_id": self.ride_id,
            "proposal_type": self.proposal_type,
            "status": self.status.value,
            "total_eligible": total_eligible,
            "total_votes": total_votes,
            "approve_count": approve_count,
            "reject_count": reject_count,
            "remaining_votes": remaining,
            "expires_at": self.expires_at.isoformat(),
            "time_remaining_seconds": max(0, (self.expires_at - datetime.utcnow()).total_seconds())
        }


class ConsensusService:
    """
    Consensus voting service with WebSocket coordination.
    
    Manages voting sessions, handles timeouts, and broadcasts updates
    via WebSocket to all connected clients.
    """
    
    def __init__(self):
        """Initialize consensus service."""
        self.active_votes: Dict[str, ConsensusVote] = {}
        self._vote_counter = 0
    
    def _generate_vote_id(self) -> str:
        """Generate unique vote ID."""
        self._vote_counter += 1
        return f"vote_{datetime.utcnow().timestamp()}_{self._vote_counter}"
    
    async def create_vote(
        self,
        ride_id: int,
        proposal_type: str,
        proposal_data: Dict,
        eligible_voters: List[int],
        timeout_seconds: int = None
    ) -> ConsensusVote:
        """
        Create a new consensus voting session.
        
        Args:
            ride_id: Associated ride ID
            proposal_type: Type of proposal
            proposal_data: Proposal data
            eligible_voters: List of eligible passenger IDs
            timeout_seconds: Custom timeout (uses default if None)
            
        Returns:
            Created ConsensusVote instance
        """
        vote_id = self._generate_vote_id()
        vote = ConsensusVote(
            vote_id=vote_id,
            ride_id=ride_id,
            proposal_type=proposal_type,
            proposal_data=proposal_data,
            eligible_voters=eligible_voters,
            timeout_seconds=timeout_seconds
        )
        
        self.active_votes[vote_id] = vote
        
        # Start timeout task
        vote._task = asyncio.create_task(self._vote_timeout_handler(vote_id))
        
        # Broadcast vote creation via WebSocket
        await manager.broadcast(
            str(ride_id),
            {
                "type": "consensus_vote_created",
                "vote": vote.get_vote_summary()
            }
        )
        
        logger.info(f"Created consensus vote {vote_id} for ride {ride_id}")
        return vote
    
    async def cast_vote(
        self,
        vote_id: str,
        passenger_id: int,
        vote: Literal["approve", "reject"]
    ) -> Dict:
        """
        Cast a vote in an active voting session.
        
        Args:
            vote_id: Vote ID
            passenger_id: Passenger ID
            vote: Vote value (approve/reject)
            
        Returns:
            Dict with vote result and summary
        """
        if vote_id not in self.active_votes:
            raise ValueError(f"Vote {vote_id}
        
        vote_session = self.active_votes[vote_id]
        
        if vote_session.status != VoteStatus.PENDING:
            raise ValueError(f"Vote {vote_id} is not pending (status: {vote_session.status})")
        
        # Cast the vote
        if not vote_session.cast_vote(passenger_id, vote):
            raise ValueError(f"Passenger {passenger_id} cannot vote in this session")
        
        # Calculate result
        result = vote_session.calculate_result()
        
        # Update status if decided
        if result != VoteStatus.PENDING:
            vote_session.status = result
            if vote_session._task:
                vote_session._task.cancel()
            await self._finalize_vote(vote_id, result)
        
        # Broadcast vote update via WebSocket
        await manager.broadcast(
            str(vote_session.ride_id),
            {
                "type": "consensus_vote_update",
                "vote": vote_session.get_vote_summary()
            }
        )
        
        return {
            "success": True,
            "vote_id": vote_id,
            "result": result.value,
            "summary": vote_session.get_vote_summary()
        }
    
    async def _vote_timeout_handler(self, vote_id: str):
        """
        Handle vote timeout.
        
        Args:
            vote_id: Vote ID
        """
        vote_session = self.active_votes.get(vote_id)
        if not vote_session:
            return
        
        # Wait for timeout
        try:
            await asyncio.sleep(vote_session.timeout_seconds)
        except asyncio.CancelledError:
            # Vote was decided early
            return
        
        # Handle timeout
        if vote_id in self.active_votes and vote_session.status == VoteStatus.PENDING:
            vote_session.status = VoteStatus.TIMEOUT
            await self._finalize_vote(vote_id, VoteStatus.TIMEOUT)
            
            # Broadcast timeout via WebSocket
            await manager.broadcast(
                str(vote_session.ride_id),
                {
                    "type": "consensus_vote_timeout",
                    "vote": vote_session.get_vote_summary()
                }
            )
            
            logger.info(f"Vote {vote_id} timed out")
    
    async def _finalize_vote(self, vote_id: str, result: VoteStatus):
        """
        Finalize a vote and clean up.
        
        Args:
            vote_id: Vote ID
            result: Final vote result
        """
        vote_session = self.active_votes.get(vote_id)
        if not vote_session:
            return
        
        # Broadcast final result
        await manager.broadcast(
            str(vote_session.ride_id),
            {
                "type": "consensus_vote_finalized",
                "vote": vote_session.get_vote_summary(),
                "result": result.value
            }
        )
        
        # Remove from active votes after a delay
        await asyncio.sleep(5)
        if vote_id in self.active_votes:
            del self.active_votes[vote_id]
        
        logger.info(f"Finalized vote {vote_id} with result {result}")
    
    async def get_vote_status(self, vote_id: str) -> Optional[Dict]:
        """
        Get status of an active vote.
        
        Args:
            vote_id: Vote ID
            
        Returns:
            Vote summary or None if not found
        """
        vote_session = self.active_votes.get(vote_id)
        if not vote_session:
            return None
        
        return vote_session.get_vote_summary()
    
    async def cancel_vote(self, vote_id: str) -> bool:
        """
        Cancel an active vote.
        
        Args:
            vote_id: Vote ID
            
        Returns:
            True if cancelled, False if not found
        """
        vote_session = self.active_votes.get(vote_id)
        if not vote_session:
            return False
        
        if vote_session._task:
            vote_session._task.cancel()
        
        del self.active_votes[vote_id]
        
        # Broadcast cancellation
        await manager.broadcast(
            str(vote_session.ride_id),
            {
                "type": "consensus_vote_cancelled",
                "vote_id": vote_id
            }
        )
        
        logger.info(f"Cancelled vote {vote_id}")
        return True


# Global consensus service instance
consensus_service = ConsensusService()


if __name__ == "__main__":
    import asyncio
    
    async def test_consensus_service():
        """Test consensus service."""
        print("Testing Consensus Service...")
        
        service = ConsensusService()
        
        # Create a vote
        vote = await service.create_vote(
            ride_id=123,
            proposal_type="mid_route_pickup",
            proposal_data={"detour_minutes": 3},
            eligible_voters=[1, 2, 3],
            timeout_seconds=10
        )
        
        print(f"Created vote: {vote.vote_id}")
        print(f"Vote summary: {vote.get_vote_summary()}")
        
        # Cast some votes
        await asyncio.sleep(1)
        result1 = await service.cast_vote(vote.vote_id, 1, "approve")
        print(f"Vote 1 result: {result1}")
        
        await asyncio.sleep(1)
        result2 = await service.cast_vote(vote.vote_id, 2, "approve")
        print(f"Vote 2 result: {result2}")
        
        # Wait for timeout or early decision
        await asyncio.sleep(3)
        
        print("\nConsensus service test completed!")
    
    asyncio.run(test_consensus_service())
