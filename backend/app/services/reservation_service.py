"""Atomic seat holds and booking-search expiry handling."""

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.core.config import get_settings
from backend.app.db.models import DriverProfile, Ride, RideStatus, SeatReservation
from backend.app.services.verification_service import driver_eligibility
from backend.app.services.utc_time import as_utc, utc_now


def _active_search(ride: Ride, now: datetime) -> bool:
    return ride.search_expires_at is None or as_utc(ride.search_expires_at) > as_utc(now)


async def assign_driver_with_hold(
    db: AsyncSession,
    ride_id: int,
    driver_id: int,
    now: datetime | None = None,
) -> tuple[bool, str]:
    now = as_utc(now) if now is not None else utc_now()
    await sweep_expired_lifecycle(db, now)
    eligible, _, profile = await driver_eligibility(
        db, driver_id, require_online=True
    )
    if not eligible or profile is None:
        return False, "Driver is not eligible for dispatch"

    ride = await db.scalar(
        select(Ride).where(Ride.id == ride_id).with_for_update()
    )
    if ride is None:
        return False, "Ride not found"
    if ride.status not in {RideStatus.REQUESTED, RideStatus.SEARCHING}:
        return False, "Ride is not available for dispatch"
    if not _active_search(ride, now):
        ride.status = RideStatus.NO_DRIVER_FOUND
        await db.flush()
        return False, "Booking search has expired"
    if profile.vehicle_type != ride.vehicle_type.value:
        return False, "Driver vehicle type does not match the booking"

    settings = get_settings()
    if ride.seats_required > settings.vehicle_capacities.get(profile.vehicle_type, 0):
        return False, "Vehicle does not have enough seats"
    reservation = SeatReservation(
        ride_id=ride.id,
        driver_profile_id=profile.id,
        seats_held=ride.seats_required,
        status="held",
        expires_at=now + timedelta(seconds=settings.seat_hold_ttl_seconds),
    )
    ride.driver_id = driver_id
    ride.status = RideStatus.DRIVER_ASSIGNED
    ride.updated_at = now
    db.add(reservation)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False, "Driver already has an active seat hold"
    return True, "Driver assigned with a temporary seat hold"


async def accept_driver_hold(
    db: AsyncSession,
    ride_id: int,
    driver_id: int,
    now: datetime | None = None,
) -> tuple[bool, str]:
    now = as_utc(now) if now is not None else utc_now()
    ride = await db.scalar(
        select(Ride).where(Ride.id == ride_id).with_for_update()
    )
    if (
        ride is None
        or ride.driver_id != driver_id
        or ride.status != RideStatus.DRIVER_ASSIGNED
        or not _active_search(ride, now)
    ):
        return False, "Ride assignment is no longer active"
    profile_id = await db.scalar(
        select(SeatReservation.driver_profile_id)
        .join(
            DriverProfile,
            SeatReservation.driver_profile_id == DriverProfile.id,
        )
        .where(
            SeatReservation.ride_id == ride_id,
            DriverProfile.user_id == driver_id,
            SeatReservation.status == "held",
            SeatReservation.expires_at > now,
        )
        .with_for_update()
    )
    if profile_id is None:
        return False, "Seat hold has expired"
    result = await db.execute(
        update(SeatReservation)
        .where(
            SeatReservation.ride_id == ride_id,
            SeatReservation.driver_profile_id == profile_id,
            SeatReservation.status == "held",
            SeatReservation.expires_at > now,
        )
        .values(status="confirmed", updated_at=now)
    )
    if result.rowcount != 1:
        return False, "Seat hold has expired"
    ride.status = RideStatus.ARRIVED
    ride.updated_at = now
    await db.flush()
    return True, "Ride accepted"


async def sweep_expired_lifecycle(
    db: AsyncSession,
    now: datetime | None = None,
) -> dict[str, int]:
    now = as_utc(now) if now is not None else utc_now()
    expired_ids = await db.scalars(
        select(SeatReservation.id)
        .where(
            SeatReservation.status == "held",
            SeatReservation.expires_at <= now,
        )
    )
    released_holds = 0
    for reservation_id in expired_ids:
        ride_id = await db.scalar(
            select(SeatReservation.ride_id).where(
                SeatReservation.id == reservation_id
            )
        )
        if ride_id is None:
            continue
        ride = await db.scalar(
            select(Ride).where(Ride.id == ride_id).with_for_update()
        )
        reservation = await db.scalar(
            select(SeatReservation)
            .where(SeatReservation.id == reservation_id)
            .with_for_update()
        )
        if (
            reservation is None
            or reservation.status != "held"
            or reservation.expires_at > now
        ):
            continue
        reservation.status = "expired"
        reservation.reason = "hold_expired"
        reservation.updated_at = now
        released_holds += 1
        if (
            ride is not None
            and ride.status == RideStatus.DRIVER_ASSIGNED
            and ride.driver_id is not None
        ):
            ride.driver_id = None
            ride.status = (
                RideStatus.SEARCHING
                if _active_search(ride, now)
                else RideStatus.NO_DRIVER_FOUND
            )
            ride.updated_at = now

    searches = await db.scalars(
        select(Ride)
        .where(
            Ride.status.in_(
                [
                    RideStatus.REQUESTED,
                    RideStatus.SEARCHING,
                    RideStatus.DRIVER_ASSIGNED,
                ]
            ),
            Ride.search_expires_at.is_not(None),
            Ride.search_expires_at <= now,
        )
        .with_for_update(skip_locked=True)
    )
    expired_search_count = 0
    for ride in searches:
        if ride.status == RideStatus.DRIVER_ASSIGNED:
            await db.execute(
                update(SeatReservation)
                .where(
                    SeatReservation.ride_id == ride.id,
                    SeatReservation.status == "held",
                )
                .values(
                    status="expired",
                    reason="booking_search_expired",
                    updated_at=now,
                )
            )
            ride.driver_id = None
        ride.status = RideStatus.NO_DRIVER_FOUND
        ride.updated_at = now
        expired_search_count += 1
    await db.flush()
    return {
        "holds_released": released_holds,
        "searches_expired": expired_search_count,
    }
