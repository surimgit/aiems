from __future__ import annotations

from marshmallow import Schema, fields


class ModelStatusSchema(Schema):
    name = fields.String(required=True)
    model_path = fields.String(required=True)
    exists = fields.Boolean(required=True)
    loaded = fields.Boolean(required=True)
    feature_columns = fields.List(fields.String(), allow_none=True)


class HealthResponseSchema(Schema):
    status = fields.String(required=True)
    service = fields.String(required=True)
    models = fields.List(fields.Nested(ModelStatusSchema), required=True)

