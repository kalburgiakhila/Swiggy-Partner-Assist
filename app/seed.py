from __future__ import annotations

from flask import current_app

from .extensions import db
from .models import LocationPing, MenuItem, Order, OrderItem, Restaurant, Role, User


def ensure_seeded() -> None:
    if User.query.first():
        migrate_demo_assets()
        return
    seed_demo_data()
    migrate_demo_assets()


def migrate_demo_assets() -> None:
    demo_emails = {"owner@demo.com", "owner2@demo.com", "owner3@demo.com"}
    demo_owners = User.query.filter(User.email.in_(list(demo_emails))).all()
    if not demo_owners:
        return
    owner_ids = [u.id for u in demo_owners]
    restaurants = Restaurant.query.filter(Restaurant.owner_id.in_(owner_ids)).all()
    for r in restaurants:
        if r.name == "Spice Route Kitchen" and (not r.hero_image_url or r.hero_image_url.startswith("http")):
            r.hero_image_url = "/static/img/item_dosa.jpg"
        if r.name == "Burger Bay" and (not r.hero_image_url or r.hero_image_url.startswith("http")):
            r.hero_image_url = "/static/img/item_burger.jpg"
        if r.name == "Green Bowl Co." and (not r.hero_image_url or r.hero_image_url.startswith("http")):
            r.hero_image_url = "/static/img/item_salad.jpg"
    items = MenuItem.query.join(Restaurant, MenuItem.restaurant_id == Restaurant.id).filter(Restaurant.owner_id.in_(owner_ids)).all()
    for it in items:
        if not it.image_url or it.image_url.startswith("http"):
            # map by item name for demo
            name = (it.name or "").lower()
            if "biryani" in name:
                it.image_url = "/static/img/item_biryani.jpg"
            elif "dosa" in name:
                it.image_url = "/static/img/item_dosa.jpg"
            elif "coffee" in name:
                it.image_url = "/static/img/item_coffee.jpg"
            elif "burger" in name:
                it.image_url = "/static/img/item_burger.jpg"
            elif "fries" in name:
                it.image_url = "/static/img/item_fries.jpg"
            elif "smoothie" in name or "shake" in name:
                it.image_url = "/static/img/item_smoothie.jpg"
            elif "salad" in name or "bowl" in name:
                it.image_url = "/static/img/item_salad.jpg"
            else:
                it.image_url = "/static/img/hero.jpg"
    db.session.commit()


def seed_demo_data() -> None:
    db.session.query(LocationPing).delete()
    db.session.query(OrderItem).delete()
    db.session.query(Order).delete()
    db.session.query(MenuItem).delete()
    db.session.query(Restaurant).delete()
    db.session.query(User).delete()
    db.session.commit()

    def make_user(email: str, name: str, role: str, password: str, phone: str, **kwargs) -> User:
        u = User(email=email, full_name=name, role=role, phone=phone, **kwargs)
        u.set_password(password)
        return u

    admin = make_user("admin@demo.com", "Demo Admin", Role.ADMIN.value, "Admin@1234", "9999999999")

    base_lat = current_app.config["MAP_DEFAULT_CENTER_LAT"]
    base_lng = current_app.config["MAP_DEFAULT_CENTER_LNG"]

    customer = make_user(
        "customer@demo.com",
        "Demo Customer",
        Role.CUSTOMER.value,
        "Customer@1234",
        "8888888888",
        address="Indiranagar, Bengaluru",
        lat=base_lat + 0.02,
        lng=base_lng + 0.02,
    )
    customer2 = make_user(
        "customer2@demo.com",
        "Aarav Mehta",
        Role.CUSTOMER.value,
        "Customer@1234",
        "8888800000",
        address="HSR Layout, Bengaluru",
        lat=base_lat + 0.01,
        lng=base_lng + 0.03,
    )

    owner = make_user("owner@demo.com", "Demo Restaurant Owner", Role.RESTAURANT_OWNER.value, "Owner@1234", "7777777777")
    owner2 = make_user("owner2@demo.com", "Ananya Rao", Role.RESTAURANT_OWNER.value, "Owner@1234", "7777700000")
    owner3 = make_user("owner3@demo.com", "Karan Singh", Role.RESTAURANT_OWNER.value, "Owner@1234", "7777711111")

    rider = make_user(
        "rider@demo.com",
        "Demo Delivery Partner",
        Role.DELIVERY_PARTNER.value,
        "Rider@1234",
        "6666666666",
        lat=base_lat + 0.01,
        lng=base_lng - 0.01,
    )
    rider2 = make_user(
        "rider2@demo.com",
        "Riya Patel",
        Role.DELIVERY_PARTNER.value,
        "Rider@1234",
        "6666600000",
        lat=base_lat - 0.02,
        lng=base_lng + 0.02,
    )

    rest = Restaurant(
        owner=owner,
        name="Spice Route Kitchen",
        description="South Indian • Biryani • Fast Delivery",
        address="Koramangala, Bengaluru",
        lat=base_lat - 0.015,
        lng=base_lng + 0.01,
        hero_image_url="/static/img/item_dosa.jpg",
        is_open=True,
    )

    rest2 = Restaurant(
        owner=owner2,
        name="Burger Bay",
        description="Burgers • Fries • Shakes",
        address="MG Road, Bengaluru",
        lat=base_lat + 0.005,
        lng=base_lng - 0.005,
        hero_image_url="/static/img/item_burger.jpg",
        is_open=True,
    )
    rest3 = Restaurant(
        owner=owner3,
        name="Green Bowl Co.",
        description="Healthy • Salads • Smoothies",
        address="JP Nagar, Bengaluru",
        lat=base_lat - 0.03,
        lng=base_lng - 0.01,
        hero_image_url="/static/img/item_salad.jpg",
        is_open=True,
    )

    items = [
        MenuItem(
            restaurant=rest,
            name="Chicken Biryani",
            description="Aromatic basmati rice, tender chicken, classic spices.",
            price_cents=25900,
            image_url="/static/img/item_biryani.jpg",
        ),
        MenuItem(
            restaurant=rest,
            name="Masala Dosa",
            description="Crispy dosa with potato masala and coconut chutney.",
            price_cents=11900,
            image_url="/static/img/item_dosa.jpg",
        ),
        MenuItem(
            restaurant=rest,
            name="Filter Coffee",
            description="Strong, smooth, and perfectly sweet.",
            price_cents=6900,
            image_url="/static/img/item_coffee.jpg",
        ),
        MenuItem(
            restaurant=rest,
            name="Gobi Manchurian",
            description="Crispy cauliflower tossed in spicy sauce.",
            price_cents=14900,
            image_url="/static/img/item_dosa.jpg",
        ),
        MenuItem(
            restaurant=rest2,
            name="Classic Cheeseburger",
            description="Juicy patty, cheddar, pickles, and house sauce.",
            price_cents=22900,
            image_url="/static/img/item_burger.jpg",
        ),
        MenuItem(
            restaurant=rest2,
            name="Crispy Fries",
            description="Golden, salted, and crunchy.",
            price_cents=9900,
            image_url="/static/img/item_fries.jpg",
        ),
        MenuItem(
            restaurant=rest2,
            name="Chocolate Shake",
            description="Thick shake with cocoa and vanilla ice cream.",
            price_cents=12900,
            image_url="/static/img/item_smoothie.jpg",
        ),
        MenuItem(
            restaurant=rest3,
            name="Avocado Salad",
            description="Fresh greens, avocado, seeds, and citrus dressing.",
            price_cents=19900,
            image_url="/static/img/item_salad.jpg",
        ),
        MenuItem(
            restaurant=rest3,
            name="Protein Bowl",
            description="Quinoa, roasted veggies, and grilled paneer.",
            price_cents=23900,
            image_url="/static/img/item_salad.jpg",
        ),
        MenuItem(
            restaurant=rest3,
            name="Berry Smoothie",
            description="Mixed berries blended with yogurt.",
            price_cents=14900,
            image_url="/static/img/item_smoothie.jpg",
        ),
    ]

    db.session.add_all([admin, customer, customer2, owner, owner2, owner3, rider, rider2, rest, rest2, rest3, *items])
    db.session.commit()
