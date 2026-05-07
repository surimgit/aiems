"""AI 서비스 API — Flask 앱 팩토리 및 라우트 정의.

미구현 AI 엔드포인트는 503 FEATURE_UNAVAILABLE 로 응답한다.
nginx 가 /api/ai/ prefix 를 벗겨내므로 라우트는 prefix 없이 등록한다.
"""

import uuid

from flask import Flask, jsonify


def create_app() -> Flask:
    """Flask 앱 팩토리."""
    application = Flask(__name__)
    _register_routes(application)
    return application


# ── 공통 헬퍼 ─────────────────────────────────────────────────────────────────

def _unavailable():
    """AI 기능 미구현 표준 응답 (S305 에러 형식)."""
    return jsonify({
        "error_code": "FEATURE_UNAVAILABLE",
        "message": "AI 서비스가 아직 활성화되지 않았습니다.",
        "trace_id": str(uuid.uuid4()),
        "details": {},
    }), 503


def _register_routes(application: Flask) -> None:
    # ── 헬스체크 ──────────────────────────────────────────────────────────────

    @application.route("/health")
    def health():
        """헬스체크 엔드포인트 (Docker HEALTHCHECK 용)."""
        return jsonify(status="ok", service="ai"), 200

    @application.route("/")
    def index():
        """루트 엔드포인트."""
        return jsonify(
            service="ai",
            version="0.1.0",
            description="EMS AI Service",
        ), 200

    # ── AI 추론 요청 (미구현 → 503) ───────────────────────────────────────────

    @application.route("/inference-requests", methods=["POST"])
    def create_inference_request():
        """AI 추론 요청 생성 — 미구현.

        프론트엔드: POST /api/ai/inference-requests
        nginx 가 /api/ai/ 를 벗겨 /inference-requests 로 전달.
        """
        return _unavailable()

    @application.route("/inference-results/<string:inference_id>", methods=["GET"])
    def get_inference_result(inference_id: str):
        """AI 추론 결과 조회 — 미구현.

        프론트엔드: GET /api/ai/inference-results/{inferenceId}
        """
        return _unavailable()

    # ── 예측/권고 조회 (미구현 → 503) ─────────────────────────────────────────

    @application.route("/forecasts/<string:forecast_id>", methods=["GET"])
    def get_forecast(forecast_id: str):
        """예측 결과 조회 — 미구현.

        프론트엔드: GET /api/ai/forecasts/{forecastId}
        """
        return _unavailable()

    @application.route("/recommendations/<string:recommendation_id>", methods=["GET"])
    def get_recommendation(recommendation_id: str):
        """권고 조회 — 미구현.

        프론트엔드: GET /api/ai/recommendations/{recommendationId}
        """
        return _unavailable()


# ── 하위 호환: main.py 가 `from .api import app` 으로 import 하는 경우 대비 ──
app = create_app()
