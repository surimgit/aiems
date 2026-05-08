from __future__ import annotations

from marshmallow import Schema, fields, validate


class SolarPredictionRequestSchema(Schema):
    model_path = fields.String(load_default=None, allow_none=True)
    model_version = fields.String(load_default=None, allow_none=True)
    site_id = fields.String(load_default=None, allow_none=True)
    installed_capacity_kw = fields.Float(load_default=None, allow_none=True)
    irradiance_threshold = fields.Float(load_default=None, allow_none=True)
    structured_profile = fields.Raw(load_default=None, allow_none=True)
    context_features = fields.Raw(load_default=None, allow_none=True)
    features = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()), required=True, validate=validate.Length(min=1))


class CapacityFactorPredictionRequestSchema(Schema):
    model_path = fields.String(load_default=None, allow_none=True)
    model_version = fields.String(load_default=None, allow_none=True)
    site_id = fields.String(load_default=None, allow_none=True)
    region = fields.String(load_default=None, allow_none=True)
    installed_capacity_kw = fields.Float(load_default=None, allow_none=True)
    estimated_capacity_wh = fields.Float(load_default=None, allow_none=True)
    max_capacity_factor = fields.Float(load_default=None, allow_none=True)
    structured_profile = fields.Raw(load_default=None, allow_none=True)
    context_features = fields.Raw(load_default=None, allow_none=True)
    features = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()), required=True, validate=validate.Length(min=1))


class SatelliteCapacityFactorPredictionRequestSchema(CapacityFactorPredictionRequestSchema):
    device = fields.String(load_default=None, allow_none=True)
    image_normalization = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["binary", "legacy_percent"]),
    )


class LiveSatelliteCapacityFactorPredictionRequestSchema(Schema):
    site_id = fields.String(load_default=None, allow_none=True)
    region = fields.String(load_default="대전시")
    latitude = fields.Float(load_default=None, allow_none=True)
    longitude = fields.Float(load_default=None, allow_none=True)
    dong_code = fields.String(load_default=None, allow_none=True)
    installed_capacity_kw = fields.Float(load_default=100.0)
    estimated_capacity_kw = fields.Float(load_default=None, allow_none=True)
    model_capacity_kw = fields.Float(load_default=None, allow_none=True)
    horizon_hours = fields.Integer(load_default=1, validate=validate.Range(min=1, max=24))
    target_time = fields.String(load_default=None, allow_none=True)
    weather_search_hours = fields.Integer(load_default=6)
    satellite_search_hours = fields.Integer(load_default=12)
    model_path = fields.String(load_default=None, allow_none=True)
    model_version = fields.String(load_default=None, allow_none=True)
    device = fields.String(load_default=None, allow_none=True)
    image_normalization = fields.String(
        load_default=None,
        allow_none=True,
        validate=validate.OneOf(["binary", "legacy_percent"]),
    )
    max_capacity_factor = fields.Float(load_default=None, allow_none=True)


class PredictionResponseSchema(Schema):
    ok = fields.Boolean(required=True)
    task = fields.String(required=True)
    model_path = fields.String(required=True)
    rows = fields.Integer(required=True)
    predictions = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()), required=True)
    structured_profile = fields.Raw(allow_none=True)
    context_features = fields.Raw(allow_none=True)
    metadata = fields.Raw(allow_none=True)


class LiveSatellitePredictionResponseSchema(Schema):
    ok = fields.Boolean(required=True)
    task = fields.String(required=True)
    input_mode = fields.String(required=True)
    warnings = fields.List(fields.String(), required=True)
    site = fields.Raw(required=True)
    target = fields.Raw(required=True)
    weather = fields.Raw(required=True)
    satellite = fields.Raw(required=True)
    model_input = fields.Raw(required=True)
    prediction = fields.Raw(required=True)
    prediction_result = fields.Raw(required=True)


class SiteProfileRequestSchema(Schema):
    site_id = fields.String(load_default=None, allow_none=True)
    site = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict)
    text = fields.String(required=True)
    profile = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=None, allow_none=True)
    use_openai = fields.Boolean(load_default=None, allow_none=True)
    auth_env = fields.String(load_default=None, allow_none=True)
    model = fields.String(load_default=None, allow_none=True)
    reasoning_effort = fields.String(load_default=None, allow_none=True)
    max_output_tokens = fields.Integer(load_default=1600)


class SiteProfileResponseSchema(Schema):
    ok = fields.Boolean(required=True)
    source = fields.String(required=True)
    profile = fields.Dict(keys=fields.String(), values=fields.Raw(), required=True)


class LoadPredictionRequestSchema(Schema):
    site_id = fields.String(load_default=None, allow_none=True)
    site = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict)
    site_profile = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=None, allow_none=True)
    timezone = fields.String(load_default=None, allow_none=True)
    target_times = fields.List(fields.String(), load_default=None, allow_none=True)
    start_time = fields.String(load_default=None, allow_none=True)
    periods = fields.Integer(load_default=24)
    frequency_hours = fields.Float(load_default=1.0)
    base_load_kw = fields.Float(load_default=None, allow_none=True)
    min_load_kw = fields.Float(load_default=0.0)
    weather_weight = fields.Float(load_default=1.0)
    reserve_ratio = fields.Float(load_default=None, allow_none=True)
    min_reserve_kw = fields.Float(load_default=0.0)
    fallback_flag = fields.Boolean(load_default=True)
    model_version = fields.String(load_default=None, allow_none=True)


class LoadPredictionResponseSchema(Schema):
    ok = fields.Boolean(required=True)
    task = fields.String(required=True)
    rows = fields.Integer(required=True)
    predictions = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()), required=True)


class ForecastRequestSchema(Schema):
    site_id = fields.String(load_default=None, allow_none=True)
    site = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict)
    start_time = fields.String(load_default=None, allow_none=True)
    periods = fields.Integer(load_default=None, allow_none=True)
    frequency_hours = fields.Float(load_default=None, allow_none=True)
    target_times = fields.List(fields.String(), load_default=None, allow_none=True)
    history_defaults = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict)
    base_load_kw = fields.Float(load_default=None, allow_none=True)
    min_load_kw = fields.Float(load_default=0.0)
    reserve_ratio = fields.Float(load_default=None, allow_none=True)
    min_reserve_kw = fields.Float(load_default=0.0)
    weather_weight = fields.Float(load_default=1.0)
    site_profile = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=None, allow_none=True)
    solar = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict)
    load = fields.Dict(keys=fields.String(), values=fields.Raw(), load_default=dict)
    net_load_high_threshold_kw = fields.Float(load_default=0.0)


class ForecastResponseSchema(Schema):
    ok = fields.Boolean(required=True)
    task = fields.String(required=True)
    rows = fields.Integer(required=True)
    forecasts = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()), required=True)
    recommendations = fields.List(fields.Dict(keys=fields.String(), values=fields.Raw()), required=True)
    solar_result = fields.Raw(allow_none=True)
    load_result = fields.Raw(allow_none=True)


class PredictionModelStatusSchema(Schema):
    name = fields.String(required=True)
    model_path = fields.String(required=True)
    exists = fields.Boolean(required=True)
    loaded = fields.Boolean(required=True)
    feature_columns = fields.List(fields.String(), allow_none=True)


class ModelListResponseSchema(Schema):
    models = fields.List(fields.Nested(PredictionModelStatusSchema), required=True)
