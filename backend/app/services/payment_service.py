"""
Payment Service with Wallet Operations

This module implements:
- Wallet balance management
- Credit/debit transactions
- Transaction history
- Payment processing for rides

Author: OptimalRide Backend Team
Date: 2026-09-27
"""

from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from datetime import datetime
from enum import Enum
import logging

from backend.app.db.models import Wallet, Transaction, User, Ride
from backend.app.api.core.config import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


class TransactionType(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentService:
    """
    Payment service with wallet operations.
    
    Provides:
    - Wallet balance management
    - Credit/debit transactions
    - Transaction history
    - Ride payment processing
    """
    
    def __init__(self):
        """Initialize payment service."""
        self.default_currency = settings.default_currency or "INR"
    
    async def get_or_create_wallet(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Wallet:
        """
        Get existing wallet or create new one for user.
        
        Args:
            session: Async database session
            user_id: User ID
            
        Returns:
            Wallet instance
        """
        # Try to get existing wallet
        wallet = await session.execute(
            select(Wallet).where(Wallet.user_id == user_id)
        )
        wallet = wallet.scalar_one_or_none()
        
        # Create new wallet if not exists
        if not wallet:
            wallet = Wallet(
                user_id=user_id,
                balance=0.0,
                currency=self.default_currency,
                is_active=True
            )
            session.add(wallet)
            await session.commit()
            await session.refresh(wallet)
            logger.info(f"Created new wallet for user {user_id}")
        
        return wallet
    
    async def get_wallet_balance(
        self,
        session: AsyncSession,
        user_id: int
    ) -> Dict:
        """
        Get wallet balance for user.
        
        Args:
            session: Async database session
            user_id: User ID
            
        Returns:
            Dictionary with balance information
        """
        wallet = await self.get_or_create_wallet(session, user_id)
        
        return {
            "user_id": user_id,
            "balance": wallet.balance,
            "currency": wallet.currency,
            "is_active": wallet.is_active
        }
    
    async def credit_wallet(
        self,
        session: AsyncSession,
        user_id: int,
        amount: float,
        description: str,
        reference_id: Optional[str] = None
    ) -> Dict:
        """
        Credit amount to user's wallet.
        
        Args:
            session: Async database session
            user_id: User ID
            amount: Amount to credit
            description: Transaction description
            reference_id: Optional reference ID
            
        Returns:
            Transaction result
        """
        try:
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            wallet = await self.get_or_create_wallet(session, user_id)
            
            # Create transaction record
            transaction = Transaction(
                wallet_id=wallet.id,
                transaction_type=TransactionType.CREDIT.value,
                amount=amount,
                description=description,
                reference_id=reference_id,
                status=TransactionStatus.COMPLETED.value
            )
            session.add(transaction)
            
            # Update wallet balance
            await session.execute(
                update(Wallet)
                .where(Wallet.id == wallet.id)
                .values(
                    balance=wallet.balance + amount,
                    updated_at=datetime.utcnow()
                )
            )
            
            await session.commit()
            await session.refresh(transaction)
            
            logger.info(f"Credited {amount} to wallet {wallet.id} for user {user_id}")
            
            return {
                "success": True,
                "transaction_id": transaction.id,
                "wallet_id": wallet.id,
                "user_id": user_id,
                "amount": amount,
                "new_balance": wallet.balance + amount,
                "currency": wallet.currency
            }
            
        except Exception as e:
            logger.error(f"Error crediting wallet: {str(e)}")
            await session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def debit_wallet(
        self,
        session: AsyncSession,
        user_id: int,
        amount: float,
        description: str,
        reference_id: Optional[str] = None
    ) -> Dict:
        """
        Debit amount from user's wallet.
        
        Args:
            session: Async database session
            user_id: User ID
            amount: Amount to debit
            description: Transaction description
            reference_id: Optional reference ID
            
        Returns:
            Transaction result
        """
        try:
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            wallet = await self.get_or_create_wallet(session, user_id)
            
            # Check sufficient balance
            if wallet.balance < amount:
                return {
                    "success": False,
                    "error": "Insufficient balance",
                    "current_balance": wallet.balance,
                    "required_amount": amount
                }
            
            # Create transaction record
            transaction = Transaction(
                wallet_id=wallet.id,
                transaction_type=TransactionType.DEBIT.value,
                amount=amount,
                description=description,
                reference_id=reference_id,
                status=TransactionStatus.COMPLETED.value
            )
            session.add(transaction)
            
            # Update wallet balance
            await session.execute(
                update(Wallet)
                .where(Wallet.id == wallet.id)
                .values(
                    balance=wallet.balance - amount,
                    updated_at=datetime.utcnow()
                )
            )
            
            await session.commit()
            await session.refresh(transaction)
            
            logger.info(f"Debited {amount} from wallet {wallet.id} for user {user_id}")
            
            return {
                "success": True,
                "transaction_id": transaction.id,
                "wallet_id": wallet.id,
                "user_id": user_id,
                "amount": amount,
                "new_balance": wallet.balance - amount,
                "currency": wallet.currency
            }
            
        except Exception as e:
            logger.error(f"Error debiting wallet: {str(e)}")
            await session.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def process_ride_payment(
        self,
        session: AsyncSession,
        ride_id: int,
        passenger_id: int,
        amount: float
    ) -> Dict:
        """
        Process payment for a completed ride.
        
        Args:
            session: Async database session
            ride_id: Ride ID
            passenger_id: Passenger user ID
            amount: Fare amount
            
        Returns:
            Payment result
        """
        try:
            # Debit from passenger wallet
            debit_result = await self.debit_wallet(
                session,
                passenger_id,
                amount,
                f"Ride payment for ride {ride_id}",
                reference_id=str(ride_id)
            )
            
            if not debit_result.get('success'):
                return debit_result
            
            # Credit to driver wallet (if driver exists)
            ride = await session.execute(
                select(Ride).where(Ride.id == ride_id)
            )
            ride = ride.scalar_one_or_none()
            
            if ride and ride.driver_id:
                # Calculate driver earnings (minus platform fee)
                platform_fee_percent = settings.platform_fee_percent or 5.0
                driver_earnings = amount * (1 - platform_fee_percent / 100)
                
                credit_result = await self.credit_wallet(
                    session,
                    ride.driver_id,
                    driver_earnings,
                    f"Earnings from ride {ride_id}",
                    reference_id=str(ride_id)
                )
                
                if not credit_result.get('success'):
                    logger.warning(f"Failed to credit driver: {credit_result.get('error')}")
            
            return {
                "success": True,
                "ride_id": ride_id,
                "passenger_id": passenger_id,
                "amount": amount,
                "transaction_id": debit_result.get('transaction_id')
            }
            
        except Exception as e:
            logger.error(f"Error processing ride payment: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_transaction_history(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get transaction history for user.
        
        Args:
            session: Async database session
            user_id: User ID
            limit: Maximum number of transactions
            offset: Offset for pagination
            
        Returns:
            List of transactions
        """
        wallet = await self.get_or_create_wallet(session, user_id)
        
        transactions = await session.execute(
            select(Transaction)
            .where(Transaction.wallet_id == wallet.id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        transactions = transactions.scalars().all()
        
        return [
            {
                "transaction_id": tx.id,
                "type": tx.transaction_type,
                "amount": tx.amount,
                "description": tx.description,
                "reference_id": tx.reference_id,
                "status": tx.status,
                "created_at": tx.created_at.isoformat()
            }
            for tx in transactions
        ]


# Global payment service instance
payment_service = PaymentService()


if __name__ == "__main__":
    import asyncio
    
    async def test_payment_service():
        """Test payment service."""
        print("Testing Payment Service...")
        
        service = PaymentService()
        print("Payment service initialized successfully")
        print(f"Default currency: {service.default_currency}")
        
        print("\nPayment service test completed!")
    
    asyncio.run(test_payment_service())
