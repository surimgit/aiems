FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/ems/ai

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY ems/ai/service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY ems/ai/service /app/ems/ai/service
COPY ems/ai/inference /app/ems/ai/inference
COPY ems/ai/models /app/ems/ai/models
COPY ems/ai/train /app/ems/ai/train

WORKDIR /app/ems/ai/service

EXPOSE 5004

CMD ["sh", "-c", "gunicorn --timeout ${GUNICORN_TIMEOUT:-1200} --access-logfile - --error-logfile - --log-level info -b 0.0.0.0:5004 app.main:app"]
