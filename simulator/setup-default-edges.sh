#!/bin/bash
# ================================================================
# 기본 4개 Edge + Device + Topology 등록 스크립트 (Linux/Mac/Git Bash)
#
# 사용법:
#   1. EMS 부팅:        cd S14P31S305 && docker compose up -d
#   2. Simulator 부팅:  cd simulator/simulator && docker compose up -d
#   3. 이 스크립트 실행: bash setup-default-edges.sh
#
# 멱등(idempotent): 이미 등록된 항목은 skip
# ================================================================

set +e
MANAGER="http://localhost:8080"
TOPOLOGY="http://localhost:8081"

call() {
    local method="$1" url="$2" body="$3"
    local result
    if [ -n "$body" ]; then
        result=$(curl -s -X "$method" "$url" -H "Content-Type: application/json" -d "$body" -w "\n%{http_code}")
    else
        result=$(curl -s -X "$method" "$url" -w "\n%{http_code}")
    fi
    local code=$(echo "$result" | tail -n1)
    local resp=$(echo "$result" | sed '$d')
    if [ "$code" = "201" ] || [ "$code" = "200" ]; then
        echo "  OK ($code): $method $url"
    elif echo "$resp" | grep -qi "already exists\|exists"; then
        echo "  SKIP (already exists): $method $url"
    else
        echo "  FAIL ($code): $method $url -> $resp"
    fi
}

echo "=== 1. Edge 등록 (각 edge_type 기본 device 1개 자동 생성) ==="
call POST "$MANAGER/api/edges" '{"edge_id":"solar-edge-01","edge_type":"solar","plant_id":"PLANT-ALPHA"}'
call POST "$MANAGER/api/edges" '{"edge_id":"diesel-edge-01","edge_type":"diesel","plant_id":"PLANT-ALPHA"}'
call POST "$MANAGER/api/edges" '{"edge_id":"ess-edge-01","edge_type":"ess","plant_id":"PLANT-ALPHA"}'
call POST "$MANAGER/api/edges" '{"edge_id":"load-edge-01","edge_type":"load","plant_id":"PLANT-ALPHA"}'

sleep 3

echo ""
echo "=== 2. Topology Lines 등록 ==="
call POST "$TOPOLOGY/api/lines" '{"line_id":"line-solar01-ess01","from_node_id":"node-solar-edge-01","to_node_id":"node-ess-edge-01","switch_id":"sw-solar01-ess01"}'
call POST "$TOPOLOGY/api/lines" '{"line_id":"line-diesel01-ess01","from_node_id":"node-diesel-edge-01","to_node_id":"node-ess-edge-01","switch_id":"sw-diesel01-ess01"}'
call POST "$TOPOLOGY/api/lines" '{"line_id":"line-ess01-load01","from_node_id":"node-ess-edge-01","to_node_id":"node-load-edge-01","switch_id":"sw-ess01-load01"}'

echo ""
echo "=== 완료 ==="
echo "확인:"
echo "  Edges:    $MANAGER/api/edges"
echo "  Topology: $TOPOLOGY/api/topology"
