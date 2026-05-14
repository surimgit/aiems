import os

from .api import app
from .extensions import socketio

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5002))
    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
