"""
Payment API Endpoints

Endpoints:
- Get wallet balance
- Credit wallet
- Debit wallet
- Process ride payment
- Get transaction history
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List

from ..core.security import get_current_user
from ..db.database import get_db
from ..services.payment_service import payment_service

router = APIRouter(prefix="/payment", tags=["Payment"])


class CreditRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[str] = None


class DebitRequest(BaseModel):
    amount: float = Field(..., gt=0)
    description: str = Field(..., min_length=1, max_length=500)
    reference_id: Optional[str] = None


class RidePaymentRequest(BaseModel):
    ride_id: int = Field(..., gt=0)
    amount: float = Field(..., gt=0)


@router.get("/wallet/balance")
async def get_wallet_balance(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get wallet balance for the current user.
    """
    user_id = current_user.get('id')
    
    balance_info = await payment_service.get_wallet_balance(db, user_id)
    
    return {
        "success": True,
        **balance_info
    }


@router.post("/wallet/credit")
async def credit_wallet(
    request: CreditRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Credit amount to user's wallet.
    
    Requires admin authentication for crediting other users' wallets.
    """
    user_id = current_user.get('id')
    
    result = await payment_service.credit_wallet(
        db,
        user_id,
        request.amount,
        request.description,
        request.reference_id
    )
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error')
        )
    
    return result


@router.post("/wallet/debit")
async def debit_wallet(
    request: DebitRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Debit amount from user's wallet.
    """
    user_id = current_user.get('id')
    
    result = await payment_service.debit_wallet(
        db,
        user_id,
        request.amount,
        request.description,
        request.reference_id
    )
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error')
        )
    
    return result


@router.post("/ride")
async def process_ride_payment(
    request: RidePaymentRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Process payment for a completed ride.
    
    Requires admin or system-level authentication.
    """
    if current_user.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can process ride payments"
        )
    
    passenger_id = current_user.get('id')
    
    result = await payment_service.process_ride_payment(
        db,
        request.ride_id,
        passenger_id,
        request.amount
    )
    
    if not result.get('success'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get('error')
        )
    
    return result


@router.get("/transactions")
async def get_transaction_history(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get transaction history for the current user.
    """
    user_id = current_user.get('id')
    
    transactions = await payment_service.get_transaction_history(
        db,
        user_id,
        limit,
        offset
    )
    
    return {
        "success": True,
        "user_id": user_id,
        "transactions": transactions,
        "count": len(transactions)
    }
