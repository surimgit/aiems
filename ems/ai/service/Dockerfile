FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/ems/ai

COPY ems/ai/service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY ems/ai/service /app/ems/ai/service
COPY ems/ai/models /app/ems/ai/models
COPY ems/ai/train /app/ems/ai/train

WORKDIR /app/ems/ai/service

EXPOSE 5004

CMD ["gunicorn", "-b", "0.0.0.0:5004", "app.main:app"]

