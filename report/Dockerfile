FROM python:3.11-slim

# 서비스별로 빌드 시 PORT 주입
# docker build --build-arg PORT=8001 -t ingestion .
ARG PORT=8003
ENV PORT=${PORT}

WORKDIR /app

# 시스템 패키지 (curl: healthcheck용)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE ${PORT}

# HEALTHCHECK - FastAPI 측에 GET /health 엔드포인트가 반드시 있어야 함
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:${PORT}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
