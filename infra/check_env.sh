#!/usr/bin/env bash
# ============================================================================
# infra/check_env.sh
# ----------------------------------------------------------------------------
# .env 필수 변수 검증:
#   1) 공란 여부
#   2) 최소 길이
#   3) 형식 (hex / apikey 등)
# 검증 실패 시 exit 1 → Jenkinsfile / 로컬 기동 스크립트에서 사전 차단
#
# 사용법:
#   ./infra/check_env.sh          # 현재 디렉터리 .env
#   ./infra/check_env.sh /path/to/.env
# ============================================================================

set -u

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "[check_env] ❌ $ENV_FILE 파일이 없습니다." >&2
    exit 1
fi

# .env 값 추출 (export 없이, 주석/inline-comment 제거)
_get_env_value() {
    grep -E "^${1}=" "$ENV_FILE" | head -n1 | cut -d= -f2- | sed 's/#.*$//' | xargs || true
}

# ---------------------------------------------------------------------------
# 검증 규칙 : "VAR_NAME|MIN_LEN|TYPE"
#   TYPE :
#     password : 길이만 체크 (영숫자/특수문자 허용)
#     hex      : 소문자 hex (a-f, 0-9) 만 허용
#     apikey   : 'sk-' 로 시작해야 함 (OpenAI)
#     plain    : 비공란만 체크
# ---------------------------------------------------------------------------
# 필수 변수 (공란이면 파이프라인 중단)
RULES=(
    "TIMESCALE_PASSWORD|24|password"
    "TIMESCALE_ROOT_PASSWORD|24|password"
    "POSTGRES_ROOT_PASSWORD|24|password"
    "STATE_PASSWORD|24|password"
    "AI_PASSWORD|24|password"
    "CONTROL_PASSWORD|24|password"
    "REDIS_PASSWORD|24|password"
    "MQTT_USER|1|plain"
    "MQTT_PASSWORD|24|password"
    "API_SECRET_KEY|32|hex"
    "JWT_SECRET|32|hex"
)

# 선택 변수 (값이 있을 때만 형식 검증, 공란이면 경고만)
#   - OPENAI_API_KEY: 현재 ai-service 는 외부 서버리스 GPU 추론 결과 중계 역할이라
#                     OpenAI SDK 직접 호출 없음. 추후 OpenAI 직접 호출로 전환되면
#                     RULES 로 이동
OPTIONAL_RULES=(
    "OPENAI_API_KEY|1|apikey"
)

FAIL_COUNT=0
PASS_COUNT=0

for rule in "${RULES[@]}"; do
    IFS='|' read -r VAR_NAME MIN_LEN CHECK_TYPE <<< "$rule"
    VALUE=$(_get_env_value "$VAR_NAME")

    # 1) 공란
    if [ -z "$VALUE" ]; then
        echo "  ❌ $VAR_NAME : 공란"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    fi

    # 2) 길이
    LEN=${#VALUE}
    if [ "$LEN" -lt "$MIN_LEN" ]; then
        echo "  ❌ $VAR_NAME : 길이 ${LEN}자 (최소 ${MIN_LEN}자 필요)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        continue
    fi

    # 3) 형식
    case "$CHECK_TYPE" in
        hex)
            if ! [[ "$VALUE" =~ ^[a-f0-9]+$ ]]; then
                echo "  ❌ $VAR_NAME : hex(a-f, 0-9) 만 허용 — 'openssl rand -hex ${MIN_LEN}' 로 생성"
                FAIL_COUNT=$((FAIL_COUNT + 1))
                continue
            fi
            ;;
        apikey)
            if ! [[ "$VALUE" =~ ^sk- ]]; then
                echo "  ❌ $VAR_NAME : 'sk-' 로 시작해야 함 (OpenAI API key 형식)"
                FAIL_COUNT=$((FAIL_COUNT + 1))
                continue
            fi
            ;;
    esac

    echo "  ✅ $VAR_NAME : OK (${LEN}자)"
    PASS_COUNT=$((PASS_COUNT + 1))
done

# ---------------------------------------------------------------------------
# 선택 변수 검증 (공란은 경고만, 값 있으면 형식 체크)
# ---------------------------------------------------------------------------
for rule in "${OPTIONAL_RULES[@]}"; do
    IFS='|' read -r VAR_NAME MIN_LEN CHECK_TYPE <<< "$rule"
    VALUE=$(_get_env_value "$VAR_NAME")

    if [ -z "$VALUE" ]; then
        echo "  ⚠️  $VAR_NAME : 공란 (선택 변수, skip)"
        continue
    fi

    LEN=${#VALUE}
    case "$CHECK_TYPE" in
        apikey)
            if ! [[ "$VALUE" =~ ^sk- ]]; then
                echo "  ❌ $VAR_NAME : 'sk-' 로 시작해야 함 (값이 있으면 반드시 OpenAI 형식)"
                FAIL_COUNT=$((FAIL_COUNT + 1))
                continue
            fi
            ;;
        hex)
            if ! [[ "$VALUE" =~ ^[a-f0-9]+$ ]]; then
                echo "  ❌ $VAR_NAME : hex(a-f, 0-9) 만 허용"
                FAIL_COUNT=$((FAIL_COUNT + 1))
                continue
            fi
            ;;
    esac

    echo "  ✅ $VAR_NAME : OK (${LEN}자, 선택)"
    PASS_COUNT=$((PASS_COUNT + 1))
done

echo ""
echo "[check_env] ============================================"

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "[check_env] ❌ 검증 실패: $FAIL_COUNT 개 / 통과: $PASS_COUNT 개"
    echo "[check_env] ============================================"
    echo "[check_env] 생성 명령어 예시:"
    echo "  tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24   # 24자 영숫자"
    echo "  openssl rand -hex 32                              # 32자 hex"
    echo "  python -c 'import secrets; print(secrets.token_urlsafe(24))'"
    exit 1
fi

echo "[check_env] ✅ 모든 필수 환경변수 검증 통과 ($PASS_COUNT 개)"
echo "[check_env] ============================================"
exit 0
