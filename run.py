import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))

try:
    import eventlet

    eventlet.monkey_patch()
except Exception:
    eventlet = None

from app import create_app, socketio  # noqa: E402


def main() -> None:
    app = create_app()
    ssl_cert = os.environ.get("SSL_CERT_FILE")
    ssl_key = os.environ.get("SSL_KEY_FILE")
    ssl_context = (ssl_cert, ssl_key) if ssl_cert and ssl_key else None
    socketio.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        ssl_context=ssl_context,
    )


if __name__ == "__main__":
    main()
