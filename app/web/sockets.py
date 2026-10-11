from __future__ import annotations

from flask_login import current_user
from flask_socketio import SocketIO, emit, join_room

from ..extensions import db
from ..models import LocationPing, Order, OrderEvent, RiderState, Role
from ..models import OrderStatus
from ..services.dispatch import haversine_km


def register_socket_handlers(socketio: SocketIO) -> None:
    def can_view_order(order: Order) -> bool:
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

    @socketio.on("join_order", namespace="/track")
    def join_order(data):
        order_id = str((data or {}).get("order_id", "")).strip()
        if not order_id:
            return
        try:
            order_id_int = int(order_id)
        except Exception:
            return
        order = db.session.get(Order, order_id_int)
        if not order or not can_view_order(order):
            emit("error", {"message": "Not authorized for this order."})
            return
        join_room(f"order:{order_id_int}")
        emit("joined", {"order_id": order_id_int, "status": order.status, "delivery_partner_id": order.delivery_partner_id})

    @socketio.on("location_update", namespace="/track")
    def location_update(data):
        if not current_user.is_authenticated:
            return
        if current_user.role != Role.DELIVERY_PARTNER.value:
            return
        order_id = int((data or {}).get("order_id") or 0)
        lat = (data or {}).get("lat")
        lng = (data or {}).get("lng")
        acc = (data or {}).get("accuracy_m")
        if not order_id or lat is None or lng is None:
            return
        order = db.session.get(Order, order_id)
        if not order or order.delivery_partner_id != current_user.id:
            return
        ping = LocationPing(
            order_id=order.id,
            delivery_partner_id=current_user.id,
            lat=float(lat),
            lng=float(lng),
            accuracy_m=float(acc) if acc is not None else None,
        )
        db.session.add(ping)
        # keep rider state fresh
        rs = db.session.get(RiderState, current_user.id)
        if not rs:
            rs = RiderState(user_id=current_user.id, is_online=True)
            db.session.add(rs)
        rs.lat = ping.lat
        rs.lng = ping.lng
        rs.is_online = True
        db.session.commit()

        def emit_once(kind: str, message: str):
            try:
                evt = OrderEvent(order_id=order.id, kind=kind, message=message)
                db.session.add(evt)
                db.session.commit()
            except Exception:
                db.session.rollback()
                return
            emit("notify", {"order_id": order.id, "kind": kind, "message": message}, to=f"order:{order.id}")

        # Proximity notifications (realistic experience)
        if order.restaurant and order.restaurant.lat is not None and order.restaurant.lng is not None:
            d_pickup_km = haversine_km(order.restaurant.lat, order.restaurant.lng, ping.lat, ping.lng)
            if order.status == OrderStatus.READY_FOR_PICKUP.value and d_pickup_km <= 0.20:
                emit_once("arrived_pickup", "Rider is near the restaurant for pickup.")

        if order.delivery_lat is not None and order.delivery_lng is not None:
            d_drop_km = haversine_km(order.delivery_lat, order.delivery_lng, ping.lat, ping.lng)
            if order.status == OrderStatus.PICKED_UP.value and d_drop_km <= 0.30:
                emit_once("nearby_drop", "Rider is nearby. Please be ready to receive your order.")
        emit(
            "location",
            {"order_id": order.id, "lat": ping.lat, "lng": ping.lng, "accuracy_m": ping.accuracy_m, "created_at": ping.created_at.isoformat()},
            to=f"order:{order.id}",
        )

    @socketio.on("rider_heartbeat", namespace="/track")
    def rider_heartbeat(data):
        if not current_user.is_authenticated:
            return
        if current_user.role != Role.DELIVERY_PARTNER.value:
            return
        lat = (data or {}).get("lat")
        lng = (data or {}).get("lng")
        if lat is None or lng is None:
            return
        rs = db.session.get(RiderState, current_user.id)
        if not rs:
            rs = RiderState(user_id=current_user.id, is_online=True)
            db.session.add(rs)
        rs.is_online = True
        rs.lat = float(lat)
        rs.lng = float(lng)
        db.session.commit()

    @socketio.on("ping", namespace="/track")
    def ping(data):
        emit("pong", {"user": getattr(current_user, "id", None), "echo": data})
