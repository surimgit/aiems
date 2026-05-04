"""AI 서비스 API — Flask 앱 정의 및 헬스체크."""

from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/health")
def health():
    """헬스체크 엔드포인트 (Docker HEALTHCHECK 용)."""
    return jsonify(status="ok", service="ai"), 200


@app.route("/")
def index():
    """루트 엔드포인트."""
    return jsonify(
        service="ai",
        version="0.1.0",
        description="EMS AI Service",
    ), 200
