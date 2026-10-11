from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .cli import register_cli
from .extensions import csrf, db, login_manager, socketio
from .schema import ensure_sqlite_schema
from .seed import ensure_seeded
from .utils import format_money




def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config.from_object("app.config.Config")
    if os.environ.get("APP_SETTINGS"):
        app.config.from_object(os.environ["APP_SETTINGS"])
    if not os.environ.get("DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{(Path(app.instance_path) / 'app.db').as_posix()}"

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    socketio.init_app(
        app,
        async_mode="threading",
        cors_allowed_origins=app.config["SOCKETIO_CORS_ALLOWED_ORIGINS"]
    )

    from .web.auth import bp as auth_bp
    from .web.customer import bp as customer_bp
    from .web.restaurant import bp as restaurant_bp
    from .web.delivery import bp as delivery_bp
    from .web.admin import bp as admin_bp
    from .web.api import bp as api_bp
    from .web.sockets import register_socket_handlers

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(restaurant_bp)
    app.register_blueprint(delivery_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    register_socket_handlers(socketio)

    register_cli(app)
    app.jinja_env.filters["money"] = format_money

    with app.app_context():
        db.create_all()
        ensure_sqlite_schema()
        ensure_seeded()

    return app
