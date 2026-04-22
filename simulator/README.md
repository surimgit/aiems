# EMS Edge Simulator

`simulator/` contains the local MQTT broker and edge simulators used for EMS integration testing.

## Included Services

- `mqtt-broker`
- `mqtt-logger`
- `ess-simulator`
- `load-simulator`

## Docker Compose

Use [docker-compose.yml](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/docker-compose.yml) to start the local test stack.

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator
docker compose up --build
```

## Local Runtime

Load simulator:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\load-simulator
python main.py
```

Run a short smoke cycle:

```powershell
python main.py --cycles 3
```

ESS simulator details:

- [ess-simulator/docs/README.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/docs/README.md)

Load simulator details:

- [load-simulator/docs/README.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/README.md)
