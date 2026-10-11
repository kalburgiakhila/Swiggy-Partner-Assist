from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user

from ..models import Role
from ..utils import role_required
from ..extensions import db, socketio
from ..models import DeliveryLeg, LocationPing, Order, OrderEvent, OrderFinance, OrderStatus, RiderEarning, RiderState
from ..services.dispatch import find_best_rider_near, haversine_km


bp = Blueprint("delivery", __name__, url_prefix="/delivery")


@bp.get("/dashboard")
@role_required(Role.DELIVERY_PARTNER.value)
def dashboard():
    rider_state = db.session.get(RiderState, current_user.id)
    available = (
        Order.query.filter(
            Order.status == OrderStatus.READY_FOR_PICKUP.value,
            Order.delivery_partner_id.is_(None),
        )
        .order_by(Order.created_at.asc())
        .limit(30)
        .all()
    )
    my_active = (
        Order.query.filter(
            Order.delivery_partner_id == current_user.id,
            Order.status.in_([OrderStatus.READY_FOR_PICKUP.value, OrderStatus.PICKED_UP.value]),
        )
        .order_by(Order.created_at.desc())
        .all()
    )
    return render_template("delivery/dashboard.html", available=available, my_active=my_active, rider_state=rider_state)


@bp.post("/toggle-online")
@role_required(Role.DELIVERY_PARTNER.value)
def toggle_online():
    rs = db.session.get(RiderState, current_user.id)
    if not rs:
        rs = RiderState(user_id=current_user.id, is_online=True)
        db.session.add(rs)
    else:
        rs.is_online = not rs.is_online
    db.session.commit()
    flash("You're now online." if rs.is_online else "You're now offline.", "info")
    return redirect(url_for("delivery.dashboard"))


@bp.post("/orders/<int:order_id>/accept")
@role_required(Role.DELIVERY_PARTNER.value)
def accept(order_id: int):
    order = Order.query.get_or_404(order_id)
    if order.status != OrderStatus.READY_FOR_PICKUP.value or order.delivery_partner_id is not None:
        flash("Order is not available to accept.", "warning")
        return redirect(url_for("delivery.dashboard"))
    order.delivery_partner_id = current_user.id
    db.session.commit()
    if not DeliveryLeg.query.filter_by(order_id=order.id, status="active").first():
        seq = (db.session.query(db.func.max(DeliveryLeg.seq)).filter_by(order_id=order.id).scalar() or 0) + 1
        db.session.add(DeliveryLeg(order_id=order.id, rider_id=current_user.id, seq=seq, status="active"))
        db.session.commit()
    try:
        db.session.add(OrderEvent(order_id=order.id, kind="assigned_rider", message="A rider has been assigned to your order."))
        db.session.commit()
    except Exception:
        db.session.rollback()
    socketio.emit("status", {"order_id": order.id, "status": order.status, "delivery_partner_id": order.delivery_partner_id}, namespace="/track", to=f"order:{order.id}")
    socketio.emit(
        "notify",
        {"order_id": order.id, "kind": "assigned_rider", "message": "Rider assigned. Your order will be picked up soon."},
        namespace="/track",
        to=f"order:{order.id}",
    )
    flash(f"Accepted order #{order.id}.", "success")
    return redirect(url_for("delivery.order", order_id=order.id))


@bp.get("/orders/<int:order_id>")
@role_required(Role.DELIVERY_PARTNER.value)
def order(order_id: int):
    order = Order.query.get_or_404(order_id)
    if order.delivery_partner_id != current_user.id:
        return ("Forbidden", 403)
    finance = db.session.get(OrderFinance, order.id)
    return render_template("delivery/order.html", order=order, finance=finance)


@bp.get("/earnings")
@role_required(Role.DELIVERY_PARTNER.value)
def earnings():
    rows = (
        RiderEarning.query.filter_by(rider_id=current_user.id)
        .order_by(RiderEarning.created_at.desc())
        .limit(300)
        .all()
    )
    total = sum(r.amount_cents for r in rows if r.status == "earned")
    return render_template("delivery/earnings.html", rows=rows, total=total)


@bp.post("/orders/<int:order_id>/pickup")
@role_required(Role.DELIVERY_PARTNER.value)
def pickup(order_id: int):
    order = Order.query.get_or_404(order_id)
    if order.delivery_partner_id != current_user.id:
        return ("Forbidden", 403)
    if order.status != OrderStatus.READY_FOR_PICKUP.value:
        flash("Order can't be picked up in current state.", "warning")
        return redirect(url_for("delivery.order", order_id=order.id))
    # Anti-scam: require rider near restaurant
    if current_app.config.get("ANTI_SCAM_GEO_CHECKS", True) and order.restaurant and order.restaurant.lat is not None and order.restaurant.lng is not None:
        last = (
            LocationPing.query.filter_by(order_id=order.id, delivery_partner_id=current_user.id)
            .order_by(LocationPing.created_at.desc())
            .first()
        )
        rs = db.session.get(RiderState, current_user.id)
        lat = last.lat if last else (rs.lat if rs else None)
        lng = last.lng if last else (rs.lng if rs else None)
        if lat is None or lng is None:
            flash("Share live location before pickup.", "warning")
            return redirect(url_for("delivery.order", order_id=order.id))
        if haversine_km(order.restaurant.lat, order.restaurant.lng, float(lat), float(lng)) > 0.35:
            flash("You must be near the restaurant to mark pickup.", "danger")
            return redirect(url_for("delivery.order", order_id=order.id))
    order.status = OrderStatus.PICKED_UP.value
    db.session.commit()

    # Create pending earning for this rider if not split flow
    fin = db.session.get(OrderFinance, order.id)
    if fin and not RiderEarning.query.filter_by(order_id=order.id, rider_id=current_user.id).first():
        db.session.add(
            RiderEarning(order_id=order.id, rider_id=current_user.id, amount_cents=fin.rider_earning_cents, status="pending", reason="delivery")
        )
        db.session.commit()
    try:
        db.session.add(OrderEvent(order_id=order.id, kind="picked_up", message="Your order has been picked up."))
        db.session.commit()
    except Exception:
        db.session.rollback()
    socketio.emit("status", {"order_id": order.id, "status": order.status}, namespace="/track", to=f"order:{order.id}")
    socketio.emit(
        "notify",
        {"order_id": order.id, "kind": "picked_up", "message": "Picked up! Your order is on the way."},
        namespace="/track",
        to=f"order:{order.id}",
    )
    flash("Marked as picked up.", "success")
    return redirect(url_for("delivery.order", order_id=order.id))


@bp.post("/orders/<int:order_id>/deliver")
@role_required(Role.DELIVERY_PARTNER.value)
def deliver(order_id: int):
    order = Order.query.get_or_404(order_id)
    if order.delivery_partner_id != current_user.id:
        return ("Forbidden", 403)
    if order.status != OrderStatus.PICKED_UP.value:
        flash("Order can't be delivered in current state.", "warning")
        return redirect(url_for("delivery.order", order_id=order.id))
    # Anti-scam: require rider near destination
    if current_app.config.get("ANTI_SCAM_GEO_CHECKS", True) and order.delivery_lat is not None and order.delivery_lng is not None:
        last = (
            LocationPing.query.filter_by(order_id=order.id, delivery_partner_id=current_user.id)
            .order_by(LocationPing.created_at.desc())
            .first()
        )
        rs = db.session.get(RiderState, current_user.id)
        lat = last.lat if last else (rs.lat if rs else None)
        lng = last.lng if last else (rs.lng if rs else None)
        if lat is None or lng is None:
            flash("Share live location before delivery.", "warning")
            return redirect(url_for("delivery.order", order_id=order.id))
        if haversine_km(order.delivery_lat, order.delivery_lng, float(lat), float(lng)) > 0.45:
            flash("You must be near the destination to mark delivered.", "danger")
            return redirect(url_for("delivery.order", order_id=order.id))
    order.status = OrderStatus.DELIVERED.value
    db.session.commit()
    fin = db.session.get(OrderFinance, order.id)
    if fin:
        # COD is considered collected at delivery time in this demo
        if fin.payment_method == "cod" and fin.payment_status != "paid":
            fin.payment_status = "paid"
        fin.rider_settlement_status = "earned"
        fin.restaurant_settlement_status = "earned"
        db.session.commit()

    # Close active leg (if any)
    leg = DeliveryLeg.query.filter_by(order_id=order.id, rider_id=current_user.id, status="active").first()
    if leg:
        leg.status = "completed"
        leg.ended_at = datetime.now(timezone.utc)
        db.session.commit()

    # Settle rider earnings for this rider (handles normal and split flows)
    for e in RiderEarning.query.filter_by(order_id=order.id, rider_id=current_user.id).all():
        e.status = "earned"
    db.session.commit()
    try:
        db.session.add(OrderEvent(order_id=order.id, kind="delivered", message="Your order was delivered."))
        db.session.commit()
    except Exception:
        db.session.rollback()
    socketio.emit("status", {"order_id": order.id, "status": order.status}, namespace="/track", to=f"order:{order.id}")
    socketio.emit(
        "notify",
        {"order_id": order.id, "kind": "delivered", "message": "Delivered! Enjoy your meal."},
        namespace="/track",
        to=f"order:{order.id}",
    )
    flash("Delivered successfully.", "success")
    return redirect(url_for("delivery.dashboard"))


@bp.post("/orders/<int:order_id>/assist")
@role_required(Role.DELIVERY_PARTNER.value)
def assist(order_id: int):
    """
    Partner Assist: if the rider has picked up but can't finish,
    reassign to a nearby online rider using a cost-effective (distance) score.
    """
    order = Order.query.get_or_404(order_id)
    if order.status != OrderStatus.PICKED_UP.value:
        flash("Assist is available only after pickup.", "warning")
        return redirect(url_for("delivery.order", order_id=order.id))
    if order.delivery_partner_id != current_user.id:
        flash("Only the current rider can request assist.", "danger")
        return redirect(url_for("delivery.dashboard"))

    last = (
        LocationPing.query.filter_by(order_id=order.id, delivery_partner_id=current_user.id)
        .order_by(LocationPing.created_at.desc())
        .first()
    )
    rs = db.session.get(RiderState, current_user.id)
    lat = last.lat if last else (rs.lat if rs else None)
    lng = last.lng if last else (rs.lng if rs else None)
    if lat is None or lng is None:
        flash("Share live location before requesting assist.", "warning")
        return redirect(url_for("delivery.order", order_id=order.id))

    new_id, dist_km = find_best_rider_near(float(lat), float(lng), exclude_ids={current_user.id})
    if not new_id:
        flash("No nearby online rider found for assist.", "warning")
        return redirect(url_for("delivery.order", order_id=order.id))

    fin = db.session.get(OrderFinance, order.id)
    total = fin.rider_earning_cents if fin else 0
    first_share = int(round(total * 0.45))
    second_share = max(0, total - first_share)

    active = DeliveryLeg.query.filter_by(order_id=order.id, rider_id=current_user.id, status="active").first()
    if active:
        active.status = "handed_off"
        active.handoff_lat = float(lat)
        active.handoff_lng = float(lng)
        active.ended_at = datetime.now(timezone.utc)
        next_seq = active.seq + 1
    else:
        next_seq = (db.session.query(db.func.max(DeliveryLeg.seq)).filter_by(order_id=order.id).scalar() or 0) + 1
    db.session.add(DeliveryLeg(order_id=order.id, rider_id=new_id, seq=next_seq, status="active", handoff_lat=float(lat), handoff_lng=float(lng)))

    order.delivery_partner_id = new_id

    if fin:
        fin.rider_settlement_status = "split_pending"
    # settle current rider partial immediately, remainder on completion by new rider
    db.session.add(RiderEarning(order_id=order.id, rider_id=current_user.id, amount_cents=first_share, status="earned", reason="handoff_part"))
    db.session.add(RiderEarning(order_id=order.id, rider_id=new_id, amount_cents=second_share, status="pending", reason="handoff_complete"))
    db.session.commit()

    socketio.emit(
        "notify",
        {"order_id": order.id, "kind": "handoff", "message": f"Partner assist: order reassigned to a nearby rider (~{dist_km:.1f} km)."},
        namespace="/track",
        to=f"order:{order.id}",
    )
    flash("Assist requested. Order reassigned to a nearby rider.", "info")
    return redirect(url_for("delivery.dashboard"))
