# EMS Edge Simulator

EMS 설계 문서의 `Edge_Simulator_System.md`를 기준으로 만든 시뮬레이터 작업용 폴더입니다.

이 프로젝트는 단일 앱이 아니라, 자원별 Edge Simulator를 독립 서비스로 나누는 구조를 전제로 합니다.

## 구조

- `shared/`: 공통 모델, enum, MQTT 베이스, 제약식
- `solar-simulator/`: 태양광 시뮬레이터
- `load-simulator/`: 부하 시뮬레이터
- `ess-simulator/`: ESS 시뮬레이터
- `diesel-simulator/`: 디젤 발전기 시뮬레이터
- `docker-compose.yml`: 전체 서비스 실행 조합

각 시뮬레이터는 아래 구조를 공통으로 가집니다.

- `core/`: 순수 시뮬레이션 로직
- `adapters/`: MQTT 입출력
- `tui/`: 로컬 모니터링 UI
- `config/`: 장치 및 시나리오 설정
- `tests/`: 단위 테스트


## 현재 상태

현재는 폴더 구조와 빈 파일만 생성된 상태입니다.
