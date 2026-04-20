# ESS Simulator 문서 안내

## 목적

이 디렉터리는 ESS 시뮬레이터의 현재 구현 상태와 작업 기준 문서를 정리한다.
코드는 `simulator/ess-simulator/` 기준이며, 외부 설계 문서 원본을 그대로 복사하지 않고
현재 레포에 반영된 결과를 요약한다.

## 현재 상태

- 1장 기본 실행 구조: 완료
- 2장 MQTT 통신 규격 적용: 완료
- 3장 MQTT payload 모델 구현: 완료

현재 코드에는 아래 항목이 반영되어 있다.

- MQTT 일반 토픽: `{plant_id}/{resource_type}/{device_id}/{message_type}`
- heartbeat 토픽: `{plant_id}/heartbeat`
- ESS command payload 검증
- ESS telemetry payload 직렬화
- ACK payload 직렬화
- heartbeat payload 직렬화 및 주기 발행
- subscriber / publisher / command handler 분리
- `unit / integration / functional` 테스트 구성

## 문서 목록

- `basic-runtime-structure.md`
  - 1장 기본 실행 구조 정리
- `jira-basic-runtime-structure.md`
  - 1장 지라 정리 문서
- `project-structure.md`
  - 현재 디렉터리 구조와 책임 분리
- `mqtt-contract-application.md`
  - 2장, 3장 기준의 MQTT 계약 반영 결과와 테스트 범위

## 실행 및 검증

프로젝트 루트 `simulator/ess-simulator` 에서 실행한다.

```bash
python -m tests
```

## 다음 작업

3장까지는 문서 기준으로 닫혀 있다.
다음 중심 작업은 아래 순서로 본다.

1. 상태 모델 및 상태 전이
2. 충방전 및 SOC 계산 고도화
3. 명령 처리기 확장
4. 안전 제약 및 차단 로직 고도화
5. TUI 정리
