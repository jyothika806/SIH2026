"""
Ride Rating & Review API Endpoints

Endpoints:
- Submit ride rating
- Get ride ratings
- Get user ratings
- Get driver ratings
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from pydantic import BaseModel, Field
from typing import Optional, List

from ..core.security import get_current_user
from ..db.database import get_db
from ..db.models import RideRating, Ride, User

router = APIRouter(prefix="/rating", tags=["Rating"])


class RatingRequest(BaseModel):
    ride_id: int = Field(..., gt=0)
    rated_user_id: int = Field(..., gt=0)
    rating: int = Field(..., ge=1, le=5)
    review: Optional[str] = Field(None, max_length=1000)
    rating_category: str = Field("overall", regex="^(safety|punctuality|behavior|overall)$")


class RatingResponse(BaseModel):
    id: int
    ride_id: int
    rater_id: int
    rated_user_id: int
    rating: int
    review: Optional[str]
    rating_category: str
    created_at: str

    class Config:
        from_attributes = True


@router.post("/submit", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
async def submit_rating(
    request: RatingRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a rating for a ride.
    
    Users can rate drivers and vice versa.
    """
    rater_id = current_user.get('id')
    
    # Check if ride exists and is completed
    ride = await db.execute(
        select(Ride).where(Ride.id == request.ride_id)
    )
    ride = ride.scalar_one_or_none()
    
    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ride not found"
        )
    
    if ride.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only rate completed rides"
        )
    
    # Check if user was part of the ride
    if rater_id not in [ride.driver_id, ride.passenger_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You were not part of this ride"
        )
    
    # Check if rated user was part of the ride
    if request.rated_user_id not in [ride.driver_id, ride.passenger_id]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rated user was not part of this ride"
        )
    
    # Check if already rated
    existing_rating = await db.execute(
        select(RideRating).where(
            and_(
                RideRating.ride_id == request.ride_id,
                RideRating.rater_id == rater_id,
                RideRating.rated_user_id == request.rated_user_id
            )
        )
    )
    if existing_rating.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already rated this user for this ride"
        )
    
    # Create rating
    rating = RideRating(
        ride_id=request.ride_id,
        rater_id=rater_id,
        rated_user_id=request.rated_user_id,
        rating=request.rating,
        review=request.review,
        rating_category=request.rating_category
    )
    
    db.add(rating)
    await db.commit()
    await db.refresh(rating)
    
    # Update user's average rating
    await _update_user_rating(db, request.rated_user_id)
    
    return rating


@router.get("/ride/{ride_id}")
async def get_ride_ratings(
    ride_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all ratings for a specific ride.
    """
    ratings = await db.execute(
        select(RideRating).where(RideRating.ride_id == ride_id)
    )
    ratings = ratings.scalars().all()
    
    return {
        "success": True,
        "ride_id": ride_id,
        "ratings": [
            {
                "id": r.id,
                "rater_id": r.rater_id,
                "rated_user_id": r.rated_user_id,
                "rating": r.rating,
                "review": r.review,
                "rating_category": r.rating_category,
                "created_at": r.created_at.isoformat()
            }
            for r in ratings
        ],
        "count": len(ratings)
    }


@router.get("/user/{user_id}")
async def get_user_ratings(
    user_id: int,
    rating_category: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all ratings for a specific user.
    """
    query = select(RideRating).where(RideRating.rated_user_id == user_id)
    
    if rating_category:
        query = query.where(RideRating.rating_category == rating_category)
    
    ratings = await db.execute(
        query.order_by(RideRating.created_at.desc())
        .limit(limit)
    )
    ratings = ratings.scalars().all()
    
    # Calculate average rating
    avg_rating_query = select(func.avg(RideRating.rating)).where(
        RideRating.rated_user_id == user_id
    )
    if rating_category:
        avg_rating_query = avg_rating_query.where(
            RideRating.rating_category == rating_category
        )
    
    avg_rating = await db.scalar(avg_rating_query)
    
    return {
        "success": True,
        "user_id": user_id,
        "rating_category": rating_category,
        "average_rating": round(float(avg_rating) if avg_rating else 0, 2),
        "total_ratings": len(ratings),
        "ratings": [
            {
                "id": r.id,
                "ride_id": r.ride_id,
                "rater_id": r.rater_id,
                "rating": r.rating,
                "review": r.review,
                "rating_category": r.rating_category,
                "created_at": r.created_at.isoformat()
            }
            for r in ratings
        ]
    }


@router.get("/driver/{driver_id}/summary")
async def get_driver_rating_summary(
    driver_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get rating summary for a driver.
    """
    # Get ratings by category
    categories = ["safety", "punctuality", "behavior", "overall"]
    summary = {}
    
    for category in categories:
        avg_rating = await db.scalar(
            select(func.avg(RideRating.rating)).where(
                and_(
                    RideRating.rated_user_id == driver_id,
                    RideRating.rating_category == category
                )
            )
        )
        count = await db.scalar(
            select(func.count(RideRating.id)).where(
                and_(
                    RideRating.rated_user_id == driver_id,
                    RideRating.rating_category == category
                )
            )
        )
        
        summary[category] = {
            "average": round(float(avg_rating) if avg_rating else 0, 2),
            "count": count or 0
        }
    
    # Overall average
    overall_avg = await db.scalar(
        select(func.avg(RideRating.rating)).where(
            RideRating.rated_user_id == driver_id
        )
    )
    overall_count = await db.scalar(
        select(func.count(RideRating.id)).where(
            RideRating.rated_user_id == driver_id
        )
    )
    
    return {
        "success": True,
        "driver_id": driver_id,
        "overall": {
            "average": round(float(overall_avg) if overall_avg else 0, 2),
            "count": overall_count or 0
        },
        "by_category": summary
    }


async def _update_user_rating(db: AsyncSession, user_id: int):
    """
    Update user's average rating in the users table.
    """
    from ..db.models import User
    
    avg_rating = await db.scalar(
        select(func.avg(RideRating.rating)).where(
            RideRating.rated_user_id == user_id
        )
    )
    
    await db.execute(
        select(User).where(User.id == user_id)
    )
    
    # Update user rating
    await db.execute(
        select(User).where(User.id == user_id)
    )
    
    # Note: This would require updating the User model to have a rating field
    # For now, we calculate on-demand
