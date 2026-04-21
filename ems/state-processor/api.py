import json

import psycopg2.pool
import redis
from flask import Flask, jsonify, request
from flask.views import MethodView
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields

from config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    REDIS_HOST, REDIS_PORT, SITE_ID,
)

app = Flask(__name__)
app.config["API_TITLE"] = "State API"
app.config["API_VERSION"] = "1.0"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/"
app.config["OPENAPI_JSON_PATH"] = "openapi.json"
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

api = Api(app)

_db_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_redis: redis.Redis | None = None


def get_db_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _db_pool
    if _db_pool is None:
        _db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=5,
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        )
    return _db_pool


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis


blp = Blueprint("state", "state", url_prefix="/api")


# ── Schemas ───────────────────────────────────────────────────────────────────

class SensorDataSchema(Schema):
    time = fields.DateTime()
    site_id = fields.String()
    device_id = fields.String()
    resource_type = fields.String()
    p_avg = fields.Float(allow_none=True)
    p_max = fields.Float(allow_none=True)
    p_min = fields.Float(allow_none=True)
    q_avg = fields.Float(allow_none=True)
    v_avg = fields.Float(allow_none=True)
    f_avg = fields.Float(allow_none=True)
    pf_avg = fields.Float(allow_none=True)
    soc = fields.Float(allow_none=True)
    sample_count = fields.Integer()


class DeviceStateSchema(Schema):
    device_id = fields.String()
    site_id = fields.String()
    resource_type = fields.String()
    timestamp = fields.String()
    reported_state = fields.Dict()


class EventLogSchema(Schema):
    time = fields.DateTime()
    site_id = fields.String()
    device_id = fields.String()
    resource_type = fields.String()
    event_type = fields.String()
    severity = fields.String()
    message = fields.String()
    payload = fields.Dict()


# ── Routes ────────────────────────────────────────────────────────────────────

@blp.route("/sensor/recent")
class SensorRecentResource(MethodView):
    @blp.response(200, SensorDataSchema(many=True))
    def get(self):
        device_id = request.args.get("device_id")
        resource_type = request.args.get("resource_type")
        limit = min(int(request.args.get("limit", 100)), 1000)

        filters = []
        params = []
        if device_id:
            filters.append("device_id = %s")
            params.append(device_id)
        if resource_type:
            filters.append("resource_type = %s")
            params.append(resource_type.upper())

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)

        pool = get_db_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT time, site_id, device_id, resource_type,
                           p_avg, p_max, p_min, q_avg, v_avg, f_avg, pf_avg, soc, sample_count
                    FROM sensor_data
                    {where}
                    ORDER BY time DESC LIMIT %s
                    """,
                    params,
                )
                rows = cur.fetchall()
        finally:
            pool.putconn(conn)

        return [
            {
                "time": r[0], "site_id": r[1], "device_id": r[2], "resource_type": r[3],
                "p_avg": r[4], "p_max": r[5], "p_min": r[6],
                "q_avg": r[7], "v_avg": r[8], "f_avg": r[9], "pf_avg": r[10],
                "soc": r[11], "sample_count": r[12],
            }
            for r in rows
        ]


@blp.route("/devices")
class DeviceListResource(MethodView):
    @blp.response(200, DeviceStateSchema(many=True))
    def get(self):
        r = get_redis()
        keys = r.keys(f"state:{SITE_ID}:*")
        if not keys:
            return []

        values = r.mget(*keys)
        result = []
        for value in values:
            if value:
                state = json.loads(value)
                result.append(state)
        return result


@blp.route("/events")
class EventListResource(MethodView):
    @blp.response(200, EventLogSchema(many=True))
    def get(self):
        device_id = request.args.get("device_id")
        severity = request.args.get("severity")
        limit = min(int(request.args.get("limit", 100)), 1000)

        filters = []
        params = []
        if device_id:
            filters.append("device_id = %s")
            params.append(device_id)
        if severity:
            filters.append("severity = %s")
            params.append(severity.upper())

        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        params.append(limit)

        pool = get_db_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT time, site_id, device_id, resource_type,
                           event_type, severity, message, payload
                    FROM event_log
                    {where}
                    ORDER BY time DESC LIMIT %s
                    """,
                    params,
                )
                rows = cur.fetchall()
        finally:
            pool.putconn(conn)

        return [
            {
                "time": r[0], "site_id": r[1], "device_id": r[2], "resource_type": r[3],
                "event_type": r[4], "severity": r[5], "message": r[6],
                "payload": r[7] if isinstance(r[7], dict) else json.loads(r[7] or "{}"),
            }
            for r in rows
        ]


api.register_blueprint(blp)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def run_api(port: int = 5002):
    app.run(host="0.0.0.0", port=port, use_reloader=False)
