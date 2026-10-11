from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models import CartItem, MenuItem, Role, User
from ..utils import redirect_for_user
from .forms import LoginForm, RegisterForm

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect_for_user(current_user)
    form = LoginForm()
    return render_template("auth/login.html", form=form)


@bp.post("/login")
def login_post():
    if current_user.is_authenticated:
        return redirect_for_user(current_user)
    form = LoginForm()
    if not form.validate_on_submit():
        return render_template("auth/login.html", form=form), 400

    user = User.query.filter_by(email=form.email.data.lower().strip()).first()
    if not user or not user.check_password(form.password.data) or not user.is_active:
        flash("Invalid email or password.", "danger")
        return render_template("auth/login.html", form=form), 401

    login_user(user, remember=bool(form.remember.data))
    # Merge guest session cart into DB cart for customers.
    if user.role == Role.CUSTOMER.value:
        from flask import session
        cart = session.get("cart") or {}
        if isinstance(cart, dict) and cart:
            item_ids = []
            for k, v in cart.items():
                try:
                    item_ids.append(int(k))
                except Exception:
                    continue
            if item_ids:
                items = MenuItem.query.filter(MenuItem.id.in_(item_ids)).all()
                items_by_id = {i.id: i for i in items}
                for k, qty in cart.items():
                    try:
                        item_id = int(k)
                        qty_i = int(qty)
                    except Exception:
                        continue
                    if qty_i <= 0 or item_id not in items_by_id:
                        continue
                    ci = CartItem.query.filter_by(user_id=user.id, menu_item_id=item_id).first()
                    if not ci:
                        ci = CartItem(user_id=user.id, menu_item_id=item_id, quantity=0)
                        db.session.add(ci)
                    ci.quantity = max(0, ci.quantity) + qty_i
                db.session.commit()
            session.pop("cart", None)
    else:
        from flask import session

        session.pop("cart", None)
    return redirect_for_user(user)


@bp.get("/register")
def register():
    if current_user.is_authenticated:
        return redirect_for_user(current_user)
    form = RegisterForm()
    role = request.args.get("role")
    if role in {r.value for r in Role}:
        form.role.data = role
    return render_template("auth/register.html", form=form)


@bp.post("/register")
def register_post():
    if current_user.is_authenticated:
        return redirect_for_user(current_user)
    form = RegisterForm()
    if not form.validate_on_submit():
        return render_template("auth/register.html", form=form), 400

    email = form.email.data.lower().strip()
    if User.query.filter_by(email=email).first():
        flash("Email already registered. Please login.", "warning")
        return redirect(url_for("auth.login"))

    user = User(
        email=email,
        full_name=form.full_name.data.strip(),
        phone=(form.phone.data or "").strip() or None,
        role=form.role.data,
    )
    user.set_password(form.password.data)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    flash("Welcome! Your account is created.", "success")
    return redirect_for_user(user)


@bp.get("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("customer.home"))
