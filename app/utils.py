from __future__ import annotations

from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user, login_required

from .models import Role


def role_required(*roles: str):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles and not getattr(current_user, "is_admin", False):
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def redirect_for_user(user):
    if not user or not getattr(user, "role", None):
        return redirect(url_for("customer.home"))
    if user.role == Role.ADMIN.value:
        return redirect(url_for("admin.dashboard"))
    if user.role == Role.RESTAURANT_OWNER.value:
        return redirect(url_for("restaurant.dashboard"))
    if user.role == Role.DELIVERY_PARTNER.value:
        return redirect(url_for("delivery.dashboard"))
    return redirect(url_for("customer.home"))


def format_money(cents: int) -> str:
    return f"₹{(cents or 0) / 100:.2f}"


def safe_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None
