from __future__ import annotations

import enum
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    CUSTOMER = "customer"
    RESTAURANT_OWNER = "restaurant_owner"
    DELIVERY_PARTNER = "delivery_partner"
    ADMIN = "admin"


class OrderStatus(str, enum.Enum):
    PLACED = "placed"
    ACCEPTED = "accepted"
    READY_FOR_PICKUP = "ready_for_pickup"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELED = "canceled"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    role = db.Column(db.String(40), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    address = db.Column(db.String(255), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    restaurant = db.relationship("Restaurant", back_populates="owner", uselist=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN.value


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    hero_image_url = db.Column(db.String(500), nullable=True)
    is_open = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    owner = db.relationship("User", back_populates="restaurant")
    items = db.relationship("MenuItem", back_populates="restaurant", cascade="all, delete-orphan")
    orders = db.relationship("Order", back_populates="restaurant")


class MenuItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    price_cents = db.Column(db.Integer, nullable=False)
    image_url = db.Column(db.String(500), nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    restaurant = db.relationship("Restaurant", back_populates="items")


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    restaurant_id = db.Column(db.Integer, db.ForeignKey("restaurant.id"), nullable=False, index=True)
    delivery_partner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    status = db.Column(db.String(40), nullable=False, index=True, default=OrderStatus.PLACED.value)
    notes = db.Column(db.String(500), nullable=True)

    delivery_address = db.Column(db.String(255), nullable=True)
    delivery_lat = db.Column(db.Float, nullable=True)
    delivery_lng = db.Column(db.Float, nullable=True)

    subtotal_cents = db.Column(db.Integer, nullable=False, default=0)
    delivery_fee_cents = db.Column(db.Integer, nullable=False, default=2500)
    total_cents = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    restaurant = db.relationship("Restaurant", back_populates="orders")
    customer = db.relationship("User", foreign_keys=[customer_id])
    delivery_partner = db.relationship("User", foreign_keys=[delivery_partner_id])
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    pings = db.relationship("LocationPing", back_populates="order", cascade="all, delete-orphan")

    def recalc_totals(self) -> None:
        self.subtotal_cents = sum(i.price_cents_snapshot * i.quantity for i in self.items)
        self.total_cents = self.subtotal_cents + (self.delivery_fee_cents or 0)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=True, index=True)
    name_snapshot = db.Column(db.String(120), nullable=False)
    price_cents_snapshot = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    order = db.relationship("Order", back_populates="items")


class LocationPing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    delivery_partner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    accuracy_m = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    order = db.relationship("Order", back_populates="pings")


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("user_id", "menu_item_id", name="uq_cart_user_item"),)


class RiderState(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    is_online = db.Column(db.Boolean, default=False, nullable=False, index=True)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False, index=True)

    user = db.relationship("User")


class OrderEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    kind = db.Column(db.String(60), nullable=False, index=True)
    message = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("order_id", "kind", name="uq_order_event_kind"),)


class OrderFinance(db.Model):
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), primary_key=True)
    payment_method = db.Column(db.String(40), nullable=False, default="cod")
    payment_status = db.Column(db.String(40), nullable=False, default="pending")
    restaurant_settlement_status = db.Column(db.String(40), nullable=False, default="pending")
    rider_settlement_status = db.Column(db.String(40), nullable=False, default="pending")
    distance_m = db.Column(db.Float, nullable=True)
    duration_s = db.Column(db.Float, nullable=True)
    platform_commission_cents = db.Column(db.Integer, nullable=False, default=0)
    rider_earning_cents = db.Column(db.Integer, nullable=False, default=0)
    restaurant_payout_cents = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    order = db.relationship("Order")


class DeliveryLeg(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    seq = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(40), nullable=False, default="active", index=True)  # active/handed_off/completed
    handoff_lat = db.Column(db.Float, nullable=True)
    handoff_lng = db.Column(db.Float, nullable=True)
    started_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    ended_at = db.Column(db.DateTime, nullable=True, index=True)

    __table_args__ = (db.UniqueConstraint("order_id", "seq", name="uq_leg_order_seq"),)


class RiderEarning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False, index=True)
    rider_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    amount_cents = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(40), nullable=False, default="pending", index=True)  # pending/earned
    reason = db.Column(db.String(80), nullable=False, default="delivery")
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
