from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/health")
def health_check():
    return jsonify({"status": "ok", "service": "state-processor"})
