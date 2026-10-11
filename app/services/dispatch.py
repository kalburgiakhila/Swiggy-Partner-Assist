from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from ..extensions import db
from ..models import Order, OrderStatus, RiderState, Role, User


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def assign_best_rider(order: Order, max_age_minutes: int = 5, max_distance_km: float = 8.0) -> tuple[int | None, float | None]:
    """
    Assign nearest online rider based on last known GPS.
    Returns (rider_user_id, distance_km) or (None, None) if no suitable rider.
    """
    if order.delivery_partner_id is not None:
        return order.delivery_partner_id, 0.0
    if not order.restaurant or order.restaurant.lat is None or order.restaurant.lng is None:
        return None, None

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)

    busy_ids = [
        r[0]
        for r in db.session.query(Order.delivery_partner_id)
        .filter(
            Order.delivery_partner_id.is_not(None),
            Order.status.in_([OrderStatus.READY_FOR_PICKUP.value, OrderStatus.PICKED_UP.value]),
        )
        .distinct()
        .all()
    ]

    candidates = (
        db.session.query(RiderState, User)
        .join(User, RiderState.user_id == User.id)
        .filter(
            User.role == Role.DELIVERY_PARTNER.value,
            RiderState.is_online.is_(True),
            RiderState.lat.is_not(None),
            RiderState.lng.is_not(None),
            RiderState.updated_at >= cutoff,
        )
        .all()
    )

    best_id = None
    best_d = None
    for rs, u in candidates:
        if u.id in busy_ids:
            continue
        d = haversine_km(order.restaurant.lat, order.restaurant.lng, float(rs.lat), float(rs.lng))
        if d > max_distance_km:
            continue
        if best_d is None or d < best_d:
            best_d = d
            best_id = u.id

    if best_id is None:
        return None, None

    order.delivery_partner_id = best_id
    db.session.commit()
    return best_id, best_d


def find_best_rider_near(
    lat: float,
    lng: float,
    exclude_ids: set[int] | None = None,
    max_age_minutes: int = 5,
    max_distance_km: float = 5.0,
) -> tuple[int | None, float | None]:
    """
    Find nearest online rider near a point (handoff).
    Returns (rider_user_id, distance_km).
    """
    exclude_ids = exclude_ids or set()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)

    busy_ids = {
        r[0]
        for r in db.session.query(Order.delivery_partner_id)
        .filter(
            Order.delivery_partner_id.is_not(None),
            Order.status.in_([OrderStatus.READY_FOR_PICKUP.value, OrderStatus.PICKED_UP.value]),
        )
        .distinct()
        .all()
        if r[0] is not None
    }

    candidates = (
        db.session.query(RiderState, User)
        .join(User, RiderState.user_id == User.id)
        .filter(
            User.role == Role.DELIVERY_PARTNER.value,
            RiderState.is_online.is_(True),
            RiderState.lat.is_not(None),
            RiderState.lng.is_not(None),
            RiderState.updated_at >= cutoff,
        )
        .all()
    )

    best_id = None
    best_d = None
    for rs, u in candidates:
        if u.id in busy_ids or u.id in exclude_ids:
            continue
        d = haversine_km(lat, lng, float(rs.lat), float(rs.lng))
        if d > max_distance_km:
            continue
        if best_d is None or d < best_d:
            best_d = d
            best_id = u.id
    return best_id, best_d
