# Load Simulator Multi-Panel Domain Model

## Goal

This document defines the scope of Jira task `다중 분전함 설정/도메인 모델 정의`.

The load simulator must support multiple electrical panels under a single edge.
Each panel must have its own identifier, runtime state, and telemetry stream while
still belonging to one site and one edge context.

This document is a design baseline for the following tasks:

- MQTT topic and message handling
- Panel-specific consumption scenario engine
- Load shedding command handling
- Runtime bootstrap and integration tests

## Design Principles

- One edge can own multiple load devices.
- One electrical panel maps to one load device.
- Each panel must have a unique `device_id`.
- `device_id` is the MQTT routing key for telemetry, command, and ack.
- `panel_id` is the domain identifier for the physical panel.
- The simulator must keep per-panel state and allow aggregate edge-level handling.

## Identifier Model

The simulator uses three identifier layers.

| Field | Meaning | Example | Notes |
| --- | --- | --- | --- |
| `site_id` | Plant or site identifier | `PLANT-ALPHA` | Shared by all devices in the same site |
| `edge_id` | Edge simulator identifier | `edge-01` | Shared by all panels managed by one edge |
| `device_id` | MQTT-facing load device identifier | `load-01` | Must be unique within the site |
| `panel_id` | Domain identifier of a panel | `panel-01` | Used for panel semantics and display |

Rule:

- `panel_id` identifies the panel in the domain.
- `device_id` identifies the MQTT device endpoint.
- In this simulator, one panel maps to one load device, so both move together.

## Configuration Model

Two configuration files define the multi-panel structure.

### `config/devices.yaml`

Purpose:

- define the edge context
- declare the list of load panels
- define static electrical attributes

Suggested shape:

```yaml
site_id: PLANT-ALPHA
edge_id: edge-01

loads:
  - device_id: load-01
    panel_id: panel-01
    name: office-panel
    rated_kw: 120.0
    base_kw: 80.0
    power_factor: 0.98
    voltage_v: 380.0
    frequency_hz: 60.0
    enabled: true
    scenario_profile: office-day

  - device_id: load-02
    panel_id: panel-02
    name: hvac-panel
    rated_kw: 90.0
    base_kw: 45.0
    power_factor: 0.96
    voltage_v: 380.0
    frequency_hz: 60.0
    enabled: true
    scenario_profile: hvac-heavy
```

Required fields per load:

- `device_id`
- `panel_id`
- `name`
- `rated_kw`
- `base_kw`
- `power_factor`
- `voltage_v`
- `frequency_hz`
- `enabled`
- `scenario_profile`

Validation rules:

- `device_id` must be unique.
- `panel_id` must be unique within one edge.
- `rated_kw` must be greater than `0`.
- `base_kw` must be between `0` and `rated_kw`.
- `power_factor` must be between `0` and `1`.
- `enabled=false` devices are loaded but do not publish telemetry.

### `config/scenario.yaml`

Purpose:

- define reusable scenario profiles
- separate static device definitions from dynamic load patterns

Suggested shape:

```yaml
profiles:
  office-day:
    noise_ratio: 0.05
    peak_hours: [9, 10, 11, 14, 15, 16]
    peak_multiplier: 1.20

  hvac-heavy:
    noise_ratio: 0.08
    peak_hours: [12, 13, 14, 15]
    peak_multiplier: 1.35
```

This task does not implement the full scenario engine.
It only fixes the shape that later tasks must consume.

## Runtime Domain Model

The current `load-simulator` layout already uses `core/`.
For Jira task 1, the design keeps that layout and defines the core objects below.

### `core/load.py`

Primary objects:

- `LoadDeviceConfig`
- `LoadMeasurement`
- `LoadState`
- `LoadDevice`

Responsibilities:

- store static panel attributes
- store current electrical measurements
- store panel runtime flags
- provide a stable domain shape for later telemetry generation

Suggested model split:

#### `LoadDeviceConfig`

Static configuration loaded from `devices.yaml`.

Fields:

- `site_id`
- `edge_id`
- `device_id`
- `panel_id`
- `name`
- `rated_kw`
- `base_kw`
- `power_factor`
- `voltage_v`
- `frequency_hz`
- `enabled`
- `scenario_profile`

#### `LoadMeasurement`

Latest calculated or emitted electrical values.

Fields:

- `p_kw`
- `q_kvar`
- `v_v`
- `i_a`
- `f_hz`
- `pf`
- `kwh`
- `kvarh`
- `demand_max_kw`

#### `LoadState`

Runtime state that changes during simulation.

Fields:

- `operating_state`
- `comms_health`
- `shed_ratio`
- `last_updated_at`
- `last_command_id`
- `enabled`

Notes:

- `shed_ratio` starts at `0.0`.
- later command handling updates `shed_ratio`.
- telemetry uses the current `LoadMeasurement` plus `LoadState`.

#### `LoadDevice`

Aggregate object binding config, state, and measurements.

Responsibilities:

- expose current panel identity
- hold latest measurement snapshot
- apply scenario result into measurement fields
- expose values needed by MQTT publisher

### `core/state_machine.py`

Purpose:

- define minimal runtime states for a panel
- provide a consistent base for later command handling

Suggested states:

- `IDLE`
- `RUNNING`
- `SHED`
- `FAULT`
- `DISABLED`

Initial transition rules:

- enabled panel starts in `IDLE`
- first valid measurement tick moves `IDLE -> RUNNING`
- non-zero shed ratio moves `RUNNING -> SHED`
- shed ratio back to zero moves `SHED -> RUNNING`
- internal error moves any state to `FAULT`
- disabled config moves panel to `DISABLED`

This task only defines the state vocabulary and transition intent.

### `core/scenario.py`

Purpose in task 1:

- define input and output shape of scenario processing

Expected interface:

- input: `LoadDeviceConfig`, scenario profile, current time
- output: updated `LoadMeasurement`

Implementation is deferred to the scenario task.

### `core/command_handler.py`

Purpose in task 1:

- reserve the command processing boundary for per-panel command routing

Expected interface:

- input: `device_id`, command payload, current state
- output: ack decision and state mutation intent

Implementation is deferred to the command task.

## Edge-Level Aggregation Model

Although telemetry is panel-specific, one edge manages multiple panels.

Suggested edge-level object:

- `LoadFleet` or `LoadDeviceManager`

Responsibilities:

- register all panel devices for one edge
- look up a panel by `device_id`
- iterate all active panels for publish cycles
- compute optional aggregate load for TUI or diagnostics

Minimum edge-level behavior required by later tasks:

- `register(device)`
- `get(device_id)`
- `list_enabled()`
- `total_active_power_kw()`

## MQTT Mapping Assumptions

This task does not implement MQTT logic, but it fixes the mapping that later tasks use.

Per-panel telemetry topic:

```text
{site_id}/load/{device_id}/telemetry
```

Per-panel command topic:

```text
{site_id}/load/{device_id}/command
```

Per-panel ack topic:

```text
{site_id}/load/{device_id}/ack
```

Important consequence:

- telemetry is emitted per panel, not as one aggregated edge load message
- edge-level totals are internal helper data unless a separate requirement is added

## Comparison With Existing Simulators

The current workspace already contains `solar-simulator`, `diesel-simulator`, and `ess-simulator`.

Alignment strategy for load simulator:

- keep the same high-level simulator placement under `simulator/`
- keep config-driven bootstrapping
- keep device-centric runtime objects
- add one extra requirement: multiple load devices under one edge

Difference from other simulators:

- solar and diesel currently act like single-resource device flows
- load simulator must explicitly support multiple panel instances from day one

## Scope Boundary For Jira Task 1

Included:

- identifier model
- config shape
- required per-panel fields
- runtime object definitions
- state vocabulary
- edge-level manager concept

Not included:

- real MQTT publishing
- scenario calculation logic
- load shedding execution logic
- Docker/runtime wiring
- end-to-end tests

## Done Criteria

This task is complete when the implementation matches these expectations:

- `load-simulator` contains a documented multi-panel config model
- each panel is represented by a unique `device_id`
- one edge can declare multiple panels in `devices.yaml`
- the codebase has a clear per-panel runtime model and an edge-level collection model
- later tasks can implement MQTT, scenarios, and commands without changing identifier semantics

## Suggested Next Implementation Steps

1. Create typed config and runtime models in `core/load.py`.
2. Define the state enum in `core/state_machine.py`.
3. Add sample `devices.yaml` and `scenario.yaml`.
4. Add a simple loader that instantiates multiple load devices from config.

