# EMS Edge Simulator

현재 `simulator/` 기준 기본 실행 대상은 ESS 시뮬레이터입니다.

## Docker 구성

현재 [docker-compose.yml](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/docker-compose.yml) 은 다음 서비스만 올립니다.

- `mqtt-broker`
- `mqtt-logger`
- `ess-simulator`

즉, ESS 런타임은 Docker로 실행하고 TUI는 로컬 터미널에서 따로 실행하는 구조입니다.

## 실행

브로커 + ESS 런타임:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator
docker compose up --build
```

TUI:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\ess-simulator
python tui\app.py
```

상세 문서는 [ess-simulator/docs/README.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/docs/README.md) 를 보면 됩니다.
