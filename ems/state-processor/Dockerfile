FROM python:3.10-slim
ARG PORT=5002
ENV PORT=${PORT}
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE ${PORT}
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1
CMD ["sh", "-c", "gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 --access-logfile - --error-logfile - --log-level info -b 0.0.0.0:${PORT} app.main:app"]
