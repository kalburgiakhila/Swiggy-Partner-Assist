from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, session, url_for
from flask_login import current_user

from ..extensions import db, socketio
from ..models import CartItem, MenuItem, Order, OrderFinance, OrderItem, OrderStatus, Restaurant, Role
from ..services.dispatch import haversine_km
from ..services.routing import LatLng, best_route
from ..utils import role_required, safe_int
from .forms import CheckoutForm, PaymentForm

bp = Blueprint("customer", __name__)


@bp.get("/")
def home():
    restaurants = Restaurant.query.order_by(Restaurant.is_open.desc(), Restaurant.created_at.desc()).all()
    return render_template("customer/home.html", restaurants=restaurants)


def _get_session_cart() -> dict[str, int]:
    cart = session.get("cart") or {}
    if not isinstance(cart, dict):
        cart = {}
    return {str(k): safe_int(v, 0) for k, v in cart.items() if safe_int(v, 0) > 0}


def _set_session_cart(cart: dict[str, int]) -> None:
    session["cart"] = cart
    session.modified = True


def _is_customer_user() -> bool:
    return current_user.is_authenticated and current_user.role == Role.CUSTOMER.value


def _cart_quantities() -> dict[str, int]:
    if _is_customer_user():
        items = CartItem.query.filter_by(user_id=current_user.id).all()
        return {str(i.menu_item_id): i.quantity for i in items if i.quantity > 0}
    return _get_session_cart()


def _enforce_single_restaurant(existing_ids: list[int], new_item: MenuItem) -> bool:
    if not existing_ids:
        return True
    existing = MenuItem.query.filter(MenuItem.id.in_(existing_ids)).first()
    if not existing:
        return True
    return existing.restaurant_id == new_item.restaurant_id


def _clear_cart() -> None:
    if _is_customer_user():
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return
    session.pop("cart", None)


@bp.get("/r/<int:restaurant_id>")
def restaurant_detail(restaurant_id: int):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    items = MenuItem.query.filter_by(restaurant_id=restaurant.id).order_by(MenuItem.is_available.desc(), MenuItem.created_at.desc()).all()
    cart = _cart_quantities()
    return render_template("customer/restaurant_detail.html", restaurant=restaurant, items=items, cart=cart)


@bp.post("/cart/add/<int:item_id>")
def cart_add(item_id: int):
    item = MenuItem.query.get_or_404(item_id)
    if _is_customer_user():
        existing_ids = [c.menu_item_id for c in CartItem.query.filter_by(user_id=current_user.id).all()]
        if not _enforce_single_restaurant(existing_ids, item):
            flash("Cart can contain items from only one restaurant. Clear cart to add from another restaurant.", "warning")
            return redirect(url_for("customer.cart"))
        ci = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=item.id).first()
        if not ci:
            ci = CartItem(user_id=current_user.id, menu_item_id=item.id, quantity=0)
            db.session.add(ci)
        ci.quantity += 1
        db.session.commit()
    else:
        cart = _get_session_cart()
        cart[str(item.id)] = cart.get(str(item.id), 0) + 1
        _set_session_cart(cart)
    flash(f"Added {item.name} to cart.", "success")
    return redirect(url_for("customer.restaurant_detail", restaurant_id=item.restaurant_id))


@bp.post("/cart/dec/<int:item_id>")
def cart_dec(item_id: int):
    item = MenuItem.query.get_or_404(item_id)
    if _is_customer_user():
        ci = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=item.id).first()
        if ci:
            ci.quantity = max(0, ci.quantity - 1)
            if ci.quantity <= 0:
                db.session.delete(ci)
            db.session.commit()
    else:
        cart = _get_session_cart()
        key = str(item.id)
        if key in cart:
            cart[key] = max(0, cart[key] - 1)
            if cart[key] <= 0:
                cart.pop(key, None)
            _set_session_cart(cart)
    return redirect(url_for("customer.restaurant_detail", restaurant_id=item.restaurant_id))


@bp.post("/cart/remove/<int:item_id>")
def cart_remove(item_id: int):
    if _is_customer_user():
        ci = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=item_id).first()
        if ci:
            db.session.delete(ci)
            db.session.commit()
    else:
        cart = _get_session_cart()
        cart.pop(str(item_id), None)
        _set_session_cart(cart)
    flash("Item removed from cart.", "info")
    return redirect(url_for("customer.cart"))


@bp.get("/cart")
def cart():
    cart = _cart_quantities()
    item_ids = [int(k) for k in cart.keys()] if cart else []
    items = MenuItem.query.filter(MenuItem.id.in_(item_ids)).all() if item_ids else []
    items_by_id = {str(i.id): i for i in items}
    lines = []
    subtotal = 0
    restaurant_id = None
    for item_id, qty in cart.items():
        item = items_by_id.get(item_id)
        if not item:
            continue
        restaurant_id = restaurant_id or item.restaurant_id
        if restaurant_id != item.restaurant_id:
            flash("Cart can contain items from only one restaurant. Clear cart to add from another restaurant.", "warning")
            continue
        line_total = item.price_cents * qty
        subtotal += line_total
        lines.append({"item": item, "qty": qty, "line_total": line_total})
    return render_template("customer/cart.html", lines=lines, subtotal=subtotal)


@bp.post("/cart/inc/<int:item_id>")
def cart_inc(item_id: int):
    item = MenuItem.query.get_or_404(item_id)
    if _is_customer_user():
        ci = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=item.id).first()
        if not ci:
            ci = CartItem(user_id=current_user.id, menu_item_id=item.id, quantity=0)
            db.session.add(ci)
        ci.quantity += 1
        db.session.commit()
    else:
        cart = _get_session_cart()
        cart[str(item.id)] = cart.get(str(item.id), 0) + 1
        _set_session_cart(cart)
    return redirect(url_for("customer.cart"))


@bp.post("/cart/dec_from_cart/<int:item_id>")
def cart_dec_from_cart(item_id: int):
    item = MenuItem.query.get_or_404(item_id)
    if _is_customer_user():
        ci = CartItem.query.filter_by(user_id=current_user.id, menu_item_id=item.id).first()
        if ci:
            ci.quantity = max(0, ci.quantity - 1)
            if ci.quantity <= 0:
                db.session.delete(ci)
            db.session.commit()
    else:
        cart = _get_session_cart()
        key = str(item.id)
        if key in cart:
            cart[key] = max(0, cart[key] - 1)
            if cart[key] <= 0:
                cart.pop(key, None)
            _set_session_cart(cart)
    return redirect(url_for("customer.cart"))


@bp.get("/checkout")
@role_required(Role.CUSTOMER.value)
def checkout():
    form = CheckoutForm()
    if current_user.address:
        form.delivery_address.data = current_user.address
    if current_user.lat is not None:
        form.delivery_lat.data = current_user.lat
    if current_user.lng is not None:
        form.delivery_lng.data = current_user.lng
    return render_template("customer/checkout.html", form=form)


@bp.post("/checkout")
@role_required(Role.CUSTOMER.value)
def checkout_post():
    form = CheckoutForm()
    if not form.validate_on_submit():
        return render_template("customer/checkout.html", form=form), 400

    cart = _cart_quantities()
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("customer.home"))

    item_ids = [int(k) for k in cart.keys()]
    items = MenuItem.query.filter(MenuItem.id.in_(item_ids), MenuItem.is_available.is_(True)).all()
    items_by_id = {str(i.id): i for i in items}
    restaurant_id = None

    order = Order(
        customer_id=current_user.id,
        delivery_address=form.delivery_address.data.strip(),
        delivery_lat=form.delivery_lat.data,
        delivery_lng=form.delivery_lng.data,
        notes=(form.notes.data or "").strip() or None,
        status=OrderStatus.PLACED.value,
    )
    for item_id, qty in cart.items():
        item = items_by_id.get(item_id)
        if not item:
            continue
        restaurant_id = restaurant_id or item.restaurant_id
        if item.restaurant_id != restaurant_id:
            flash("Cart must contain items from one restaurant only.", "danger")
            return redirect(url_for("customer.cart"))
        order.items.append(
            OrderItem(
                menu_item_id=item.id,
                name_snapshot=item.name,
                price_cents_snapshot=item.price_cents,
                quantity=qty,
            )
        )
    if not restaurant_id or not order.items:
        flash("Cart items are unavailable.", "warning")
        return redirect(url_for("customer.cart"))

    order.restaurant_id = restaurant_id
    order.recalc_totals()

    # Commission + earnings + payment simulation (demo)
    distance_m = None
    duration_s = None
    restaurant = Restaurant.query.get(restaurant_id)
    if restaurant and restaurant.lat is not None and restaurant.lng is not None and order.delivery_lat is not None and order.delivery_lng is not None:
        _source, _pts, meta = best_route(
            LatLng(lat=restaurant.lat, lng=restaurant.lng),
            LatLng(lat=order.delivery_lat, lng=order.delivery_lng),
            grid_size=int(current_app.config.get("ASTAR_GRID_SIZE", 80)),
            osrm_base_url=current_app.config.get("OSRM_BASE_URL"),
        )
        distance_m = meta.get("distance_m")
        duration_s = meta.get("duration_s")
        if distance_m is None:
            distance_m = haversine_km(restaurant.lat, restaurant.lng, order.delivery_lat, order.delivery_lng) * 1000

    commission = int(round(order.subtotal_cents * 0.15))
    payout = max(0, order.subtotal_cents - commission)
    distance_km = (float(distance_m) / 1000.0) if distance_m else 0.0
    rider_earning = int(round(2500 + (distance_km * 1200)))  # ₹25 base + ₹12/km (demo)
    payment_method = (form.payment_method.data or "cod").strip().lower()
    payment_status = "cod_pending" if payment_method == "cod" else "pending"

    db.session.add(order)
    db.session.flush()
    db.session.add(
        OrderFinance(
            order_id=order.id,
            payment_method=payment_method,
            payment_status=payment_status,
            distance_m=distance_m,
            duration_s=duration_s,
            platform_commission_cents=commission,
            rider_earning_cents=rider_earning,
            restaurant_payout_cents=payout,
        )
    )
    db.session.commit()

    _clear_cart()
    if payment_status == "pending":
        flash(f"Order #{order.id} created. Complete payment to start processing.", "warning")
        return redirect(url_for("customer.pay_order", order_id=order.id))
    flash(f"Order #{order.id} placed!", "success")
    return redirect(url_for("customer.order_detail", order_id=order.id))


@bp.get("/orders")
@role_required(Role.CUSTOMER.value)
def orders():
    orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template("customer/orders.html", orders=orders)


@bp.get("/orders/<int:order_id>")
@role_required(Role.CUSTOMER.value)
def order_detail(order_id: int):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        return ("Forbidden", 403)
    finance = db.session.get(OrderFinance, order.id)
    return render_template("customer/order_detail.html", order=order, finance=finance)


@bp.route("/orders/<int:order_id>/pay", methods=["GET", "POST"])
@role_required(Role.CUSTOMER.value)
def pay_order(order_id: int):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        return ("Forbidden", 403)
    finance = db.session.get(OrderFinance, order.id)
    if not finance:
        return ("Finance not found", 404)
    if finance.payment_method == "cod":
        flash("This order is Cash on Delivery.", "info")
        return redirect(url_for("customer.order_detail", order_id=order.id))
    if finance.payment_status == "paid":
        flash("Payment already completed.", "success")
        return redirect(url_for("customer.order_detail", order_id=order.id))

    form = PaymentForm()
    if form.validate_on_submit():
        finance.payment_status = "paid"
        db.session.commit()
        socketio.emit(
            "notify",
            {"order_id": order.id, "kind": "payment", "message": "Payment received. Restaurant will start preparing your order."},
            namespace="/track",
            to=f"order:{order.id}",
        )
        flash("Payment successful (simulated).", "success")
        return redirect(url_for("customer.order_detail", order_id=order.id))
    return render_template("customer/pay.html", order=order, finance=finance, form=form)


@bp.post("/orders/<int:order_id>/cancel")
@role_required(Role.CUSTOMER.value)
def cancel_order(order_id: int):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        return ("Forbidden", 403)
    if order.status != OrderStatus.PLACED.value:
        flash("Only newly placed orders can be canceled.", "warning")
        return redirect(url_for("customer.order_detail", order_id=order.id))
    order.status = OrderStatus.CANCELED.value
    db.session.commit()
    socketio.emit("status", {"order_id": order.id, "status": order.status}, namespace="/track", to=f"order:{order.id}")
    flash("Order canceled.", "info")
    return redirect(url_for("customer.orders"))
