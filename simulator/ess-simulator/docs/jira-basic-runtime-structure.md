# Jira 정리 - ESS 시뮬레이터 기본 실행 구조 구성

## 제목

ESS 시뮬레이터 기본 실행 구조 구성

## 설명

ESS 시뮬레이터의 기본 프로젝트 실행 구조를 구성한다.

`main.py`, 설정 로더, 실행 루프, 기본 디렉터리 구조를 정리하고 로컬에서 프로세스가 정상 기동되도록 만든다.
Python 3.10 기준 환경을 고정하고, 이후 MQTT/CLI command를 연결할 수 있는 실행 뼈대를 마련한다.

## 스토리 포인트

2

## 상태

완료

## 작업 목표

- ESS 시뮬레이터의 시작 지점을 명확히 한다.
- 설정 파일을 읽는 구조를 만든다.
- 이후 MQTT, payload, ESS 로직을 붙일 수 있는 실행 뼈대를 만든다.
- Python 3.10 기준 실행 환경을 명확히 한다.

## 세부 작업

- `main.py` 진입점 정리
- `config/devices.yaml` 로딩 구조 정의
- `asyncio` 메인 루프 자리 마련
- PyYAML + pydantic 기반 설정 로딩 및 검증
- 기본 로그 출력 또는 상태 확인 메시지 추가
- `Dockerfile`, `requirements.txt` 기본 실행 기준 정리

## 완료 기준

- 로컬에서 실행 가능
- 설정 파일 로딩 가능
- 실행 루프 진입 가능
- Python 3.10 Docker 기준 정리 완료
- 다음 지라 작업으로 자연스럽게 이어질 수 있음

## 완료 결과

- [main.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/main.py): 부트스트랩 전용으로 정리
- [runtime_config.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/runtime_config.py): 설정 로딩/검증 분리
- [simulator_app.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/simulator_app.py): 앱 조립 및 실행 루프 분리
- [devices.yaml](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/config/devices.yaml): 실행 가능한 기본 설정 작성
- [validators.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/core/validators.py): 값 검증 함수 분리
- [calculations.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/core/calculations.py): 계산 함수 분리
- [policies.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/core/policies.py): 정책 판단 함수 분리

현재 구조는 지라 2번 작업인 MQTT 통신 규격 구체화 및 payload 정합성 작업으로 넘길 수 있는 상태다.

## 선행/후속 관계

선행 작업:

- 없음

후속 작업:

- ESS MQTT 통신 규격 적용
- ESS MQTT Payload 모델 구현
- ESS 충방전 및 SOC 계산 로직 구현

다음 진행 대상:

- `2장 브랜치`: ESS MQTT 통신 규격 적용

## 비고

현재 단계에서는 기능 구현보다 구조 고정이 우선이다.
