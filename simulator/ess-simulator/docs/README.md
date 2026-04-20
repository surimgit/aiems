# ESS Simulator 문서 안내

## 목적

이 디렉터리는 ESS 시뮬레이터의 작업 기준, 현재 구조, 지라 단위 결과를 정리한다.

현재 상태는 다음과 같다.

- 1장 기본 실행 구조: 완료
- 2장 ESS MQTT 통신 규격 적용: 완료

## 문서 구성

- `basic-runtime-structure.md`
  - 1장 기본 실행 구조의 범위, 완료 조건, 후속 작업 기준
- `jira-basic-runtime-structure.md`
  - 1장 지라 정리 문서
- `project-structure.md`
  - 현재 프로젝트 디렉터리 구조와 각 영역 책임
- `mqtt-contract-application.md`
  - 2장 MQTT 통신 규격 적용 결과와 테스트 구조

## 현재 코드 기준 핵심 포인트

- MQTT topic 규격이 고정되어 있다.
- command / telemetry / ack payload 형식이 코드로 정리되어 있다.
- MQTT subscriber / publisher와 내부 command handler가 분리되어 있다.
- 테스트는 `unit / integration / functional` 3계층으로 나뉘어 있다.

## 테스트 실행

프로젝트 루트 `simulator/ess-simulator` 에서 아래 명령으로 전체 테스트를 실행한다.

```bash
python -m tests
```

## 다음 작업 권장 순서

1. telemetry 상태 필드 확장
2. command result / reason code 표준화
3. 실제 기기 입력 어댑터 분리
4. SOC 및 상태 전이 로직 고도화
