from __future__ import annotations

from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
csrf = CSRFProtect()
try:
    import eventlet  # noqa: F401

    _ASYNC_MODE = "eventlet"
except Exception:
    _ASYNC_MODE = "threading"

socketio = SocketIO(async_mode=_ASYNC_MODE)
