from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user

from ..utils import role_required
from ..extensions import db, socketio
from ..models import DeliveryLeg, MenuItem, Order, OrderEvent, OrderFinance, OrderStatus, Restaurant, Role
from ..services.dispatch import assign_best_rider
from .forms import MenuItemForm, RestaurantProfileForm

bp = Blueprint("restaurant", __name__, url_prefix="/restaurant")


@bp.get("/dashboard")
@role_required(Role.RESTAURANT_OWNER.value)
def dashboard():
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    orders = []
    items = []
    finances = {}
    if restaurant:
        orders = (
            Order.query.filter_by(restaurant_id=restaurant.id)
            .order_by(Order.created_at.desc())
            .limit(20)
            .all()
        )
        items = MenuItem.query.filter_by(restaurant_id=restaurant.id).order_by(MenuItem.created_at.desc()).all()
        if orders:
            order_ids = [o.id for o in orders]
            fin_rows = OrderFinance.query.filter(OrderFinance.order_id.in_(order_ids)).all()
            finances = {f.order_id: f for f in fin_rows}
    return render_template("restaurant/dashboard.html", restaurant=restaurant, orders=orders, items=items, finances=finances)


@bp.route("/profile", methods=["GET", "POST"])
@role_required(Role.RESTAURANT_OWNER.value)
def profile():
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    form = RestaurantProfileForm(obj=restaurant)
    if form.validate_on_submit():
        if not restaurant:
            restaurant = Restaurant(owner_id=current_user.id)
            db.session.add(restaurant)
        restaurant.name = form.name.data.strip()
        restaurant.description = (form.description.data or "").strip() or None
        restaurant.address = (form.address.data or "").strip() or None
        restaurant.lat = form.lat.data
        restaurant.lng = form.lng.data
        restaurant.hero_image_url = (form.hero_image_url.data or "").strip() or None
        db.session.commit()
        flash("Restaurant profile saved.", "success")
        return redirect(url_for("restaurant.dashboard"))
    return render_template("restaurant/profile.html", form=form, restaurant=restaurant)


@bp.get("/menu/new")
@role_required(Role.RESTAURANT_OWNER.value)
def menu_new():
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    if not restaurant:
        flash("Create your restaurant profile first.", "warning")
        return redirect(url_for("restaurant.profile"))
    form = MenuItemForm()
    return render_template("restaurant/menu_form.html", form=form, restaurant=restaurant, item=None)


@bp.post("/menu/new")
@role_required(Role.RESTAURANT_OWNER.value)
def menu_new_post():
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    if not restaurant:
        flash("Create your restaurant profile first.", "warning")
        return redirect(url_for("restaurant.profile"))
    form = MenuItemForm()
    if not form.validate_on_submit():
        return render_template("restaurant/menu_form.html", form=form, restaurant=restaurant, item=None), 400
    item = MenuItem(
        restaurant_id=restaurant.id,
        name=form.name.data.strip(),
        description=(form.description.data or "").strip() or None,
        price_cents=int(form.price_cents.data),
        image_url=(form.image_url.data or "").strip() or None,
        is_available=bool(form.is_available.data),
    )
    db.session.add(item)
    db.session.commit()
    flash("Menu item created.", "success")
    return redirect(url_for("restaurant.dashboard"))


@bp.get("/menu/<int:item_id>/edit")
@role_required(Role.RESTAURANT_OWNER.value)
def menu_edit(item_id: int):
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    item = MenuItem.query.get_or_404(item_id)
    if not restaurant or item.restaurant_id != restaurant.id:
        return ("Forbidden", 403)
    form = MenuItemForm(obj=item)
    return render_template("restaurant/menu_form.html", form=form, restaurant=restaurant, item=item)


@bp.post("/menu/<int:item_id>/edit")
@role_required(Role.RESTAURANT_OWNER.value)
def menu_edit_post(item_id: int):
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    item = MenuItem.query.get_or_404(item_id)
    if not restaurant or item.restaurant_id != restaurant.id:
        return ("Forbidden", 403)
    form = MenuItemForm()
    if not form.validate_on_submit():
        return render_template("restaurant/menu_form.html", form=form, restaurant=restaurant, item=item), 400
    item.name = form.name.data.strip()
    item.description = (form.description.data or "").strip() or None
    item.price_cents = int(form.price_cents.data)
    item.image_url = (form.image_url.data or "").strip() or None
    item.is_available = bool(form.is_available.data)
    db.session.commit()
    flash("Menu item updated.", "success")
    return redirect(url_for("restaurant.dashboard"))


@bp.post("/menu/<int:item_id>/delete")
@role_required(Role.RESTAURANT_OWNER.value)
def menu_delete(item_id: int):
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    item = MenuItem.query.get_or_404(item_id)
    if not restaurant or item.restaurant_id != restaurant.id:
        return ("Forbidden", 403)
    db.session.delete(item)
    db.session.commit()
    flash("Menu item deleted.", "info")
    return redirect(url_for("restaurant.dashboard"))


@bp.post("/orders/<int:order_id>/accept")
@role_required(Role.RESTAURANT_OWNER.value)
def order_accept(order_id: int):
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    order = Order.query.get_or_404(order_id)
    if not restaurant or order.restaurant_id != restaurant.id:
        return ("Forbidden", 403)
    if order.status != OrderStatus.PLACED.value:
        flash("Order can't be accepted in current state.", "warning")
        return redirect(url_for("restaurant.dashboard"))
    fin = db.session.get(OrderFinance, order.id)
    if fin and fin.payment_method in {"upi", "card"} and fin.payment_status != "paid":
        flash("Payment not completed yet. Wait for customer to pay.", "warning")
        return redirect(url_for("restaurant.dashboard"))
    order.status = OrderStatus.ACCEPTED.value
    db.session.commit()
    socketio.emit(
        "status",
        {"order_id": order.id, "status": order.status, "delivery_partner_id": order.delivery_partner_id},
        namespace="/track",
        to=f"order:{order.id}",
    )
    flash(f"Order #{order.id} accepted.", "success")
    return redirect(url_for("restaurant.dashboard"))


@bp.post("/orders/<int:order_id>/ready")
@role_required(Role.RESTAURANT_OWNER.value)
def order_ready(order_id: int):
    restaurant = Restaurant.query.filter_by(owner_id=current_user.id).first()
    order = Order.query.get_or_404(order_id)
    if not restaurant or order.restaurant_id != restaurant.id:
        return ("Forbidden", 403)
    if order.status not in {OrderStatus.ACCEPTED.value, OrderStatus.PLACED.value}:
        flash("Order can't be marked ready in current state.", "warning")
        return redirect(url_for("restaurant.dashboard"))
    order.status = OrderStatus.READY_FOR_PICKUP.value
    db.session.commit()
    if order.delivery_partner_id is None:
        rider_id, dist_km = assign_best_rider(order)
        if rider_id:
            flash(f"Auto-assigned rider (#{rider_id}) ~{dist_km:.1f} km away.", "info")
            if not DeliveryLeg.query.filter_by(order_id=order.id, seq=1).first():
                db.session.add(DeliveryLeg(order_id=order.id, rider_id=rider_id, seq=1, status="active"))
                db.session.commit()
            try:
                db.session.add(OrderEvent(order_id=order.id, kind="assigned_rider", message="A rider has been assigned to your order."))
                db.session.commit()
            except Exception:
                db.session.rollback()
            socketio.emit(
                "notify",
                {"order_id": order.id, "kind": "assigned_rider", "message": "Rider assigned. Your order will be picked up soon."},
                namespace="/track",
                to=f"order:{order.id}",
            )
        else:
            flash("No nearby online rider found. Order stays unassigned until a rider accepts.", "warning")
    socketio.emit("status", {"order_id": order.id, "status": order.status}, namespace="/track", to=f"order:{order.id}")
    flash(f"Order #{order.id} marked ready for pickup.", "success")
    return redirect(url_for("restaurant.dashboard"))
