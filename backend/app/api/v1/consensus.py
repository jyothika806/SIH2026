"""
Co-Passenger Consensus Voting API Endpoints

This module implements:
- Consensus vote creation endpoint
- Vote casting endpoint
- Vote status retrieval endpoint
- Vote cancellation endpoint

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional
from datetime import datetime

from app.api.v1.auth import get_current_user
from app.services.consensus_service import consensus_service, VoteStatus

router = APIRouter(prefix="/consensus", tags=["Consensus Voting"])


# Pydantic Schemas
class CreateVoteRequest(BaseModel):
    """Create vote request schema."""
    
    ride_id: int = Field(..., description="Associated ride ID")
    proposal_type: str = Field(..., description="Type of proposal (mid_route_pickup, route_change, etc.)")
    proposal_data: Dict = Field(..., description="Proposal data")
    eligible_voters: List[int] = Field(..., description="List of eligible passenger IDs")
    timeout_seconds: Optional[int] = Field(None, description="Custom timeout in seconds")


class CreateVoteResponse(BaseModel):
    """Create vote response schema."""
    
    vote_id: str = Field(..., description="Vote ID")
    ride_id: int = Field(..., description="Ride ID")
    proposal_type: str = Field(..., description="Proposal type")
    status: str = Field(..., description="Vote status")
    expires_at: str = Field(..., description="Expiration timestamp")
    timeout_seconds: int = Field(..., description="Timeout duration")


class CastVoteRequest(BaseModel):
    """Cast vote request schema."""
    
    vote_id: str = Field(..., description="Vote ID")
    passenger_id: int = Field(..., description="Passenger ID")
    vote: Literal["approve", "reject"] = Field(..., description="Vote value")


class CastVoteResponse(BaseModel):
    """Cast vote response schema."""
    
    success: bool = Field(..., description="Whether vote was cast")
    vote_id: str = Field(..., description="Vote ID")
    result: str = Field(..., description="Vote result")
    summary: Dict = Field(..., description="Vote summary")


# API Endpoints
@router.post("/create", response_model=CreateVoteResponse)
async def create_consensus_vote(
    request: CreateVoteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new consensus voting session.
    
    Initiates a 15-second (configurable) timed voting session for
    co-passenger decision making.
    
    Args:
        request: Vote creation data
        current_user: Current user from JWT token
        
    Returns:
        CreateVoteResponse with vote details
    """
    try:
        # Create vote
        vote = await consensus_service.create_vote(
            ride_id=request.ride_id,
            proposal_type=request.proposal_type,
            proposal_data=request.proposal_data,
            eligible_voters=request.eligible_voters,
            timeout_seconds=request.timeout_seconds
        )
        
        return CreateVoteResponse(
            vote_id=vote.vote_id,
            ride_id=vote.ride_id,
            proposal_type=vote.proposal_type,
            status=vote.status.value,
            expires_at=vote.expires_at.isoformat(),
            timeout_seconds=vote.timeout_seconds
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create consensus vote: {str(e)}"
        )


@router.post("/cast", response_model=CastVoteResponse)
async def cast_consensus_vote(
    request: CastVoteRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Cast a vote in an active consensus session.
    
    Passengers can approve or reject proposals. Votes are tallied
    and results are determined based on approval ratio or timeout.
    
    Args:
        request: Vote casting data
        current_user: Current user from JWT token
        
    Returns:
        CastVoteResponse with vote result
    """
    try:
        # Cast vote
        result = await consensus_service.cast_vote(
            vote_id=request.vote_id,
            passenger_id=request.passenger_id,
            vote=request.vote
        )
        
        return CastVoteResponse(
            success=result["success"],
            vote_id=result["vote_id"],
            result=result["result"],
            summary=result["summary"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cast vote: {str(e)}"
        )


@router.get("/status/{vote_id}")
async def get_vote_status(
    vote_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get status of an active consensus vote.
    
    Args:
        vote_id: Vote ID
        current_user: Current user from JWT token
        
    Returns:
        Vote status information
    """
    try:
        status = await consensus_service.get_vote_status(vote_id)
        
        if not status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vote not found"
            )
        
        return {
            "success": True,
            "vote_status": status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vote status: {str(e)}"
        )


@router.post("/cancel/{vote_id}")
async def cancel_vote(
    vote_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel an active consensus vote.
    
    Args:
        vote_id: Vote ID
        current_user: Current user from JWT token
        
    Returns:
        Cancellation status
    """
    try:
        success = await consensus_service.cancel_vote(vote_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vote not found"
            )
        
        return {
            "success": True,
            "message": f"Vote {vote_id} cancelled successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel vote: {str(e)}"
        )
