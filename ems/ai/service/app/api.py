from __future__ import annotations

from flask import Flask, jsonify
from flask_smorest import Api

from .config import settings
from .controllers.health_controller import blp as health_blp
from .controllers.prediction_controller import blp as prediction_blp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["API_TITLE"] = settings.api_title
    app.config["API_VERSION"] = settings.api_version
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_JSON_PATH"] = "openapi.json"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/docs"
    app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    api = Api(app)
    api.register_blueprint(health_blp)
    api.register_blueprint(prediction_blp)

    @app.errorhandler(ValueError)
    def handle_value_error(error: ValueError):
        return jsonify({"status": "bad_request", "message": str(error)}), 400

    @app.errorhandler(FileNotFoundError)
    def handle_file_not_found(error: FileNotFoundError):
        return jsonify({"status": "not_found", "message": str(error)}), 404

    @app.errorhandler(PermissionError)
    def handle_permission_error(error: PermissionError):
        return jsonify({"status": "unauthorized", "message": str(error)}), 401

    return app
