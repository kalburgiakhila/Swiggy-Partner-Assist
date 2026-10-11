from __future__ import annotations

from flask import Blueprint, render_template

from ..models import Role
from ..utils import role_required
from ..models import Order, OrderFinance, RiderEarning, Restaurant, User

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("/")
@role_required(Role.ADMIN.value)
def dashboard():
    user_count = User.query.count()
    restaurant_count = Restaurant.query.count()
    order_count = Order.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(20).all()
    return render_template(
        "admin/dashboard.html",
        user_count=user_count,
        restaurant_count=restaurant_count,
        order_count=order_count,
        recent_orders=recent_orders,
    )


@bp.get("/users")
@role_required(Role.ADMIN.value)
def users():
    users = User.query.order_by(User.created_at.desc()).limit(200).all()
    return render_template("admin/users.html", users=users)


@bp.get("/restaurants")
@role_required(Role.ADMIN.value)
def restaurants():
    restaurants = Restaurant.query.order_by(Restaurant.created_at.desc()).limit(200).all()
    return render_template("admin/restaurants.html", restaurants=restaurants)


@bp.get("/orders")
@role_required(Role.ADMIN.value)
def orders():
    orders = Order.query.order_by(Order.created_at.desc()).limit(200).all()
    return render_template("admin/orders.html", orders=orders)


@bp.get("/finance")
@role_required(Role.ADMIN.value)
def finance():
    rows = (
        OrderFinance.query.join(Order, OrderFinance.order_id == Order.id)
        .order_by(OrderFinance.created_at.desc())
        .limit(200)
        .all()
    )
    rider_total = sum(e.amount_cents for e in RiderEarning.query.filter_by(status="earned").all())
    totals = {
        "commission": sum(r.platform_commission_cents for r in rows),
        "rider": rider_total,
        "payout": sum(r.restaurant_payout_cents for r in rows if r.restaurant_settlement_status == "earned"),
    }
    return render_template("admin/finance.html", rows=rows, totals=totals)
