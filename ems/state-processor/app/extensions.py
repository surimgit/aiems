from flask_socketio import SocketIO

from .config import SOCKETIO_CORS_ALLOWED_ORIGINS


socketio = SocketIO(
    async_mode="gevent",
    cors_allowed_origins=SOCKETIO_CORS_ALLOWED_ORIGINS,
)
