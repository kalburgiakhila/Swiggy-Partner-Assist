from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask_login import current_user

from ..models import LocationPing, Order, Role
from ..utils import role_required
from ..services.routing import LatLng, best_route

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify({"ok": True})


def _can_view_order(order: Order) -> bool:
    if not current_user.is_authenticated:
        return False
    if current_user.role == Role.ADMIN.value:
        return True
    if current_user.role == Role.CUSTOMER.value and order.customer_id == current_user.id:
        return True
    if current_user.role == Role.DELIVERY_PARTNER.value and order.delivery_partner_id == current_user.id:
        return True
    if current_user.role == Role.RESTAURANT_OWNER.value and order.restaurant and order.restaurant.owner_id == current_user.id:
        return True
    return False


@bp.get("/orders/<int:order_id>/route")
@role_required(Role.CUSTOMER.value, Role.DELIVERY_PARTNER.value, Role.RESTAURANT_OWNER.value, Role.ADMIN.value)
def order_route(order_id: int):
    order = Order.query.get_or_404(order_id)
    if not _can_view_order(order):
        return ("Forbidden", 403)
    if order.restaurant.lat is None or order.restaurant.lng is None or order.delivery_lat is None or order.delivery_lng is None:
        return jsonify({"points": [], "source": None})
    source, pts, meta = best_route(
        LatLng(lat=order.restaurant.lat, lng=order.restaurant.lng),
        LatLng(lat=order.delivery_lat, lng=order.delivery_lng),
        grid_size=int(current_app.config.get("ASTAR_GRID_SIZE", 80)),
        osrm_base_url=current_app.config.get("OSRM_BASE_URL"),
    )
    return jsonify(
        {
            "source": source,
            "distance_m": meta.get("distance_m"),
            "duration_s": meta.get("duration_s"),
            "points": [{"lat": p.lat, "lng": p.lng} for p in pts],
        }
    )


@bp.get("/orders/<int:order_id>/latest_ping")
@role_required(Role.CUSTOMER.value, Role.DELIVERY_PARTNER.value, Role.RESTAURANT_OWNER.value, Role.ADMIN.value)
def latest_ping(order_id: int):
    order = Order.query.get_or_404(order_id)
    if not _can_view_order(order):
        return ("Forbidden", 403)
    ping = (
        LocationPing.query.filter_by(order_id=order.id)
        .order_by(LocationPing.created_at.desc())
        .first()
    )
    if not ping:
        return jsonify({"ping": None})
    return jsonify(
        {
            "ping": {
                "lat": ping.lat,
                "lng": ping.lng,
                "accuracy_m": ping.accuracy_m,
                "created_at": ping.created_at.isoformat(),
                "delivery_partner_id": ping.delivery_partner_id,
            }
        }
    )
