from __future__ import annotations

from flask.views import MethodView
from flask_smorest import Blueprint

from ..schemas.prediction_schema import (
    CapacityFactorPredictionRequestSchema,
    ForecastAccuracyQuerySchema,
    ForecastAccuracyResponseSchema,
    ForecastActualUpsertRequestSchema,
    ForecastActualUpsertResponseSchema,
    ForecastRequestSchema,
    ForecastResponseSchema,
    LiveSatelliteCapacityFactorPredictionRequestSchema,
    LiveSatellitePredictionResponseSchema,
    LoadPredictionRequestSchema,
    LoadPredictionResponseSchema,
    ModelListResponseSchema,
    PredictionResponseSchema,
    SiteProfileRequestSchema,
    SiteProfileResponseSchema,
    SatelliteCapacityFactorPredictionRequestSchema,
    SolarPredictionRequestSchema,
)
from ..services.forecast_service import ForecastService
from ..services.live_satellite_service import LiveSatellitePredictionService
from ..services.load_service import LoadService
from ..services.model_service import ModelService
from ..services.prediction_service import PredictionService
from ..services.site_profile_service import SiteProfileService


blp = Blueprint("ai", "ai", url_prefix="/api/ai")
model_service = ModelService()
prediction_service = PredictionService()
site_profile_service = SiteProfileService()
load_service = LoadService()
forecast_service = ForecastService(prediction_service=prediction_service, load_service=load_service)
live_satellite_service = LiveSatellitePredictionService(prediction_service=prediction_service)


@blp.route("/models")
class ModelListResource(MethodView):
    @blp.response(200, ModelListResponseSchema)
    def get(self):
        return {"models": model_service.model_status()}


@blp.route("/predict-solar")
class SolarPredictionResource(MethodView):
    @blp.arguments(SolarPredictionRequestSchema)
    @blp.response(200, PredictionResponseSchema)
    def post(self, payload):
        return prediction_service.predict_solar(payload)


@blp.route("/predict-capacity-factor")
class CapacityFactorPredictionResource(MethodView):
    @blp.arguments(CapacityFactorPredictionRequestSchema)
    @blp.response(200, PredictionResponseSchema)
    def post(self, payload):
        return prediction_service.predict_capacity_factor(payload)


@blp.route("/predict-satellite-capacity-factor")
class SatelliteCapacityFactorPredictionResource(MethodView):
    @blp.arguments(SatelliteCapacityFactorPredictionRequestSchema)
    @blp.response(200, PredictionResponseSchema)
    def post(self, payload):
        return prediction_service.predict_satellite_capacity_factor(payload)


@blp.route("/predict-live-satellite-capacity-factor")
class LiveSatelliteCapacityFactorPredictionResource(MethodView):
    @blp.arguments(LiveSatelliteCapacityFactorPredictionRequestSchema)
    @blp.response(200, LiveSatellitePredictionResponseSchema)
    def post(self, payload):
        return live_satellite_service.predict(payload)


@blp.route("/forecast")
class ForecastResource(MethodView):
    @blp.arguments(ForecastRequestSchema)
    @blp.response(200, ForecastResponseSchema)
    def post(self, payload):
        return forecast_service.forecast(payload)


@blp.route("/forecast/actuals")
class ForecastActualsResource(MethodView):
    @blp.arguments(ForecastActualUpsertRequestSchema)
    @blp.response(200, ForecastActualUpsertResponseSchema)
    def post(self, payload):
        return forecast_service.save_actuals(payload)


@blp.route("/forecast/accuracy")
class ForecastAccuracyResource(MethodView):
    @blp.arguments(ForecastAccuracyQuerySchema, location="query")
    @blp.response(200, ForecastAccuracyResponseSchema)
    def get(self, payload):
        return forecast_service.accuracy(payload)


@blp.route("/site-profile/structure")
class SiteProfileStructureResource(MethodView):
    @blp.arguments(SiteProfileRequestSchema)
    @blp.response(200, SiteProfileResponseSchema)
    def post(self, payload):
        return site_profile_service.structure(payload)


@blp.route("/predict-load")
class LoadPredictionResource(MethodView):
    @blp.arguments(LoadPredictionRequestSchema)
    @blp.response(200, LoadPredictionResponseSchema)
    def post(self, payload):
        return load_service.predict_load(payload)
