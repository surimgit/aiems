# Flask 진입점 — `flask run` 으로 실행됨 (FLASK_APP=app.main:app).
from .api import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, use_reloader=False)
