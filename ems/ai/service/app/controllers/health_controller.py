from __future__ import annotations

from flask.views import MethodView
from flask_smorest import Blueprint

from ..schemas.health_schema import HealthResponseSchema
from ..services.model_service import ModelService


blp = Blueprint("health", "health", url_prefix="")
model_service = ModelService()


@blp.route("/health")
class HealthResource(MethodView):
    @blp.response(200, HealthResponseSchema)
    def get(self):
        return {
            "status": "ok",
            "service": "ai-service",
            "models": model_service.model_status(),
        }

