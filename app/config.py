from __future__ import annotations

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///instance/app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None

    SOCKETIO_CORS_ALLOWED_ORIGINS = os.environ.get("SOCKETIO_CORS_ALLOWED_ORIGINS", "*")

    MAP_DEFAULT_CENTER_LAT = float(os.environ.get("MAP_DEFAULT_CENTER_LAT", "12.9716"))
    MAP_DEFAULT_CENTER_LNG = float(os.environ.get("MAP_DEFAULT_CENTER_LNG", "77.5946"))
    MAP_DEFAULT_ZOOM = int(os.environ.get("MAP_DEFAULT_ZOOM", "12"))

    ASTAR_GRID_SIZE = int(os.environ.get("ASTAR_GRID_SIZE", "80"))
    OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
    ANTI_SCAM_GEO_CHECKS = os.environ.get("ANTI_SCAM_GEO_CHECKS", "1") == "1"
