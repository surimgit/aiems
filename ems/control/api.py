import json
import uuid
from datetime import datetime, timezone

import psycopg2.pool
from flask import Flask, abort, jsonify, request
from flask.views import MethodView
from flask_smorest import Api, Blueprint
from marshmallow import Schema, fields, validate

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

app = Flask(__name__)
app.config["API_TITLE"] = "Control API"
app.config["API_VERSION"] = "1.0"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = "/"
app.config["OPENAPI_JSON_PATH"] = "openapi.json"
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/docs"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

api = Api(app)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=5,
            host=DB_HOST, port=DB_PORT,
            dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        )
    return _pool


blp = Blueprint("control", "control", url_prefix="/api/control")


# ── Schemas ───────────────────────────────────────────────────────────────────

class OperatorCommandRequestSchema(Schema):
    site_id = fields.String(required=True)
    device_id = fields.String(required=True)
    resource_type = fields.String(required=True)
    action = fields.String(
        required=True,
        validate=validate.OneOf([
            "START_CHARGE", "STOP_CHARGE",
            "START_DISCHARGE", "STOP_DISCHARGE",
            "START_GENERATOR", "STOP_GENERATOR",
            "OPEN_SWITCH", "CLOSE_SWITCH",
            "SHED_LOAD", "RESTORE_LOAD",
            "SET_POWER_LIMIT", "STANDBY",
        ]),
    )
    requested_by = fields.String(required=True)
    reason = fields.String(load_default="")
    source_recommendation_id = fields.String(load_default=None, allow_none=True)


class CommandAcceptedResponseSchema(Schema):
    command_id = fields.String()
    status = fields.String()
    site_id = fields.String()
    device_id = fields.String()
    action = fields.String()
    created_at = fields.DateTime()


class CommandHistorySchema(Schema):
    command_id = fields.String()
    site_id = fields.String()
    device_id = fields.String()
    resource_type = fields.String()
    command_type = fields.String()
    payload = fields.Dict()
    reason = fields.String()
    issued_by = fields.String()
    ack_status = fields.String()
    time = fields.DateTime()


# ── Routes ────────────────────────────────────────────────────────────────────

@blp.route("/operator-commands")
class OperatorCommandResource(MethodView):
    @blp.arguments(OperatorCommandRequestSchema)
    @blp.response(202, CommandAcceptedResponseSchema)
    def post(self, payload):
        command_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        pool = get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO control_history
                        (time, command_id, site_id, device_id, resource_type,
                         command_type, payload, reason, issued_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        now,
                        command_id,
                        payload["site_id"],
                        payload["device_id"],
                        payload["resource_type"].upper(),
                        payload["action"],
                        json.dumps({"action": payload["action"]}),
                        payload.get("reason", ""),
                        payload["requested_by"],
                    ),
                )
            conn.commit()
        finally:
            pool.putconn(conn)

        return {
            "command_id": command_id,
            "status": "ACCEPTED",
            "site_id": payload["site_id"],
            "device_id": payload["device_id"],
            "action": payload["action"],
            "created_at": now,
        }


@blp.route("/commands")
class CommandListResource(MethodView):
    @blp.response(200, CommandHistorySchema(many=True))
    def get(self):
        device_id = request.args.get("device_id")
        limit = min(int(request.args.get("limit", 100)), 1000)
        pool = get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                if device_id:
                    cur.execute(
                        """
                        SELECT command_id, site_id, device_id, resource_type,
                               command_type, payload, reason, issued_by, ack_status, time
                        FROM control_history
                        WHERE device_id = %s
                        ORDER BY time DESC LIMIT %s
                        """,
                        (device_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT command_id, site_id, device_id, resource_type,
                               command_type, payload, reason, issued_by, ack_status, time
                        FROM control_history
                        ORDER BY time DESC LIMIT %s
                        """,
                        (limit,),
                    )
                rows = cur.fetchall()
        finally:
            pool.putconn(conn)

        return [
            {
                "command_id": str(r[0]),
                "site_id": r[1],
                "device_id": r[2],
                "resource_type": r[3],
                "command_type": r[4],
                "payload": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                "reason": r[6],
                "issued_by": r[7],
                "ack_status": r[8],
                "time": r[9],
            }
            for r in rows
        ]


@blp.route("/commands/<command_id>")
class CommandDetailResource(MethodView):
    @blp.response(200, CommandHistorySchema)
    def get(self, command_id):
        pool = get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT command_id, site_id, device_id, resource_type,
                           command_type, payload, reason, issued_by, ack_status, time
                    FROM control_history
                    WHERE command_id = %s
                    """,
                    (command_id,),
                )
                r = cur.fetchone()
        finally:
            pool.putconn(conn)

        if not r:
            abort(404)

        return {
            "command_id": str(r[0]),
            "site_id": r[1],
            "device_id": r[2],
            "resource_type": r[3],
            "command_type": r[4],
            "payload": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
            "reason": r[6],
            "issued_by": r[7],
            "ack_status": r[8],
            "time": r[9],
        }


api.register_blueprint(blp)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def run_api(port: int = 5001):
    app.run(host="0.0.0.0", port=port, use_reloader=False)
