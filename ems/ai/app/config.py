"""ai 설정.

master .env 매핑:
  - DB는 PostgreSQL `ai_db` 사용.
    → POSTGRES_*  + AI_*  변수를 우선.
  - REDIS_PASSWORD 추가.
"""

import os

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

# ── DB (PostgreSQL ai_db) ─────────────────────────────────────────────────
DB_HOST = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("AI_DB") or os.getenv("DB_NAME", "ai_db")
DB_USER = os.getenv("AI_USER") or os.getenv("DB_USER", "ai_user")
DB_PASSWORD = os.getenv("AI_PASSWORD") or os.getenv("DB_PASSWORD", "")

# ── OpenAI (선택) ─────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
