# ================================================================
# 기본 4개 Edge + Device + Topology 등록 스크립트 (Windows)
#
# 사용법:
#   1. EMS 부팅:        cd S14P31S305 && docker compose up -d
#   2. Simulator 부팅:  cd simulator/simulator && docker compose up -d
#   3. 이 스크립트 실행: ./setup-default-edges.ps1
#
# 멱등(idempotent): 이미 등록된 항목은 skip
# ================================================================

$ErrorActionPreference = "Continue"
$MANAGER = "http://localhost:8080"
$TOPOLOGY = "http://localhost:8081"

function Invoke-Idempotent {
    param([string]$Method, [string]$Url, [object]$Body)
    try {
        $params = @{ Uri = $Url; Method = $Method; ContentType = "application/json" }
        if ($Body) { $params.Body = ($Body | ConvertTo-Json -Compress) }
        $r = Invoke-RestMethod @params
        Write-Host "  OK: $Method $Url" -ForegroundColor Green
        return $r
    } catch {
        $msg = $_.Exception.Message
        if ($msg -match "already exists|exists") {
            Write-Host "  SKIP (already exists): $Method $Url" -ForegroundColor Yellow
        } else {
            Write-Host "  FAIL: $Method $Url -> $msg" -ForegroundColor Red
        }
        return $null
    }
}

Write-Host "=== 1. Edge 등록 (각 edge_type 기본 device 1개 자동 생성) ===" -ForegroundColor Cyan
$edges = @(
    @{edge_id="solar-edge-01";  edge_type="solar";  plant_id="PLANT-ALPHA"},
    @{edge_id="diesel-edge-01"; edge_type="diesel"; plant_id="PLANT-ALPHA"},
    @{edge_id="ess-edge-01";    edge_type="ess";    plant_id="PLANT-ALPHA"},
    @{edge_id="load-edge-01";   edge_type="load";   plant_id="PLANT-ALPHA"}
)
foreach ($e in $edges) {
    Invoke-Idempotent -Method "POST" -Url "$MANAGER/api/edges" -Body $e
}

Start-Sleep -Seconds 3

Write-Host ""
Write-Host "=== 2. Topology Lines 등록 ===" -ForegroundColor Cyan
# Edge 등록 시 simulator-manager가 자동으로 노드를 만들었음 (node-{edge_id})
# 여기서는 노드 사이 선로(스위치 포함)만 추가
$lines = @(
    @{line_id="line-solar01-ess01";  from_node_id="node-solar-edge-01";  to_node_id="node-ess-edge-01";  switch_id="sw-solar01-ess01"},
    @{line_id="line-diesel01-ess01"; from_node_id="node-diesel-edge-01"; to_node_id="node-ess-edge-01";  switch_id="sw-diesel01-ess01"},
    @{line_id="line-ess01-load01";   from_node_id="node-ess-edge-01";    to_node_id="node-load-edge-01"; switch_id="sw-ess01-load01"}
)
foreach ($l in $lines) {
    Invoke-Idempotent -Method "POST" -Url "$TOPOLOGY/api/lines" -Body $l
}

Write-Host ""
Write-Host "=== 완료 ===" -ForegroundColor Green
Write-Host "확인:"
Write-Host "  Edges:    $MANAGER/api/edges"
Write-Host "  Topology: $TOPOLOGY/api/topology"
