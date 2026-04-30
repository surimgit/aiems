# EMS 설비 제어 UI 예시 정리

## 0. 공통 패널 구조

```txt
[선택된 장비 정보]
- 설비명
- 설비 타입
- 상태
- 주요 실시간 값

[설비 제어]
- 선택 설비
- 현재 상태

[간단 제어]
- 설비별 주요 명령 버튼

[상세 제어 ▼]
- 백엔드 payload에 들어갈 세부 입력값

[제어 진행]
- 명령 생성
- 전송
- 응답 대기
- 결과
```

---

## 1. 태양광 Solar 제어 UI

```txt
[선택된 장비 정보]

태양광 1 (태양광 발전 장치)        상태: 정상

장비 ID        SOLAR-01
용량           640 kW
현재 출력      480 kW (75%)
운전 상태      생산중
전압           380 V
전류           126.3 A
온도           32.1 °C
최근 업데이트  2025-05-20 14:35:10
```

```txt
[설비 제어]

선택 설비: 태양광 1        상태: 정상

간단 제어
[출력 제한] [제한 해제] [리셋]

상세 제어 ▼
최대 출력 허용량
[ 500 ] kW

허용 범위: 0 ~ 640 kW

[설정 전송]

제어 진행
● 명령 생성        완료
● 전송             완료
○ 응답 대기        대기 중
○ 결과             대기
```

### 백엔드 명령 매핑

```json
{
  "command_type": "curtailment",
  "payload": {
    "limit_kw": 500.0
  }
}
```

```json
{
  "command_type": "clear_curtailment",
  "payload": {}
}
```

```json
{
  "command_type": "mode_change",
  "payload": {
    "action": "RESET"
  }
}
```

---

## 2. ESS 제어 UI

```txt
[선택된 장비 정보]

ESS (에너지 저장 장치)        상태: 정상

장비 ID        ESS-01
용량           500 kWh / 250 kW
현재 SOC       68%
운전 상태      방전 중
전력           -120 kW
전압           675 V
전류           178.6 A
온도           28.4 °C
최근 업데이트  2025-05-20 14:35:10
```

```txt
[설비 제어]

선택 설비: ESS-01        상태: 방전 중

간단 제어
[충전] [방전] [대기]

상세 제어 ▼
목표 전력
[ 100 ] kW

장비 스펙
최대 출력 제한
[ 500 ] kW

통신 주기
[ 1.0 ] sec

안전 설정
SoC 하한
[ 10 ] %

SoC 상한
[ 95 ] %

[설정 전송]

제어 진행
● 명령 생성        완료
● 전송             완료
○ 응답 대기        대기 중
○ 결과             대기
```

### 백엔드 명령 매핑

```json
{
  "command_type": "ess_mode",
  "payload": {
    "mode": "discharge",
    "target_power_kw": 100.0
  }
}
```

```json
{
  "command_type": "update_device_spec",
  "payload": {
    "power_limit_kw": 500.0,
    "publish_interval_sec": 1.0
  }
}
```

```json
{
  "command_type": "update_safety_spec",
  "payload": {
    "low_soc_threshold": 10.0,
    "high_soc_threshold": 95.0
  }
}
```

---

## 3. 디젤 발전기 Diesel 제어 UI

```txt
[선택된 장비 정보]

디젤 발전기        상태: 대기

장비 ID        DIESEL-01
정격 출력      320 kW
현재 출력      0 kW
운전 상태      대기중
연료 잔량      15%
전압           380 V
주파수         60.0 Hz
최근 업데이트  2025-05-20 14:35:10
```

```txt
[설비 제어]

선택 설비: 디젤 발전기        상태: 대기

간단 제어
[기동] [정지] [리셋]

상세 제어 ▼
목표 발전량
[ 300 ] kW

허용 범위: 0 ~ 320 kW

[설정 전송]

제어 진행
● 명령 생성        완료
● 전송             완료
○ 응답 대기        대기 중
○ 결과             대기
```

### 백엔드 명령 매핑

```json
{
  "command_type": "start",
  "payload": {}
}
```

```json
{
  "command_type": "stop",
  "payload": {}
}
```

```json
{
  "command_type": "load_control",
  "payload": {
    "target_kw": 300.0
  }
}
```

```json
{
  "command_type": "mode_change",
  "payload": {
    "action": "RESET"
  }
}
```

---

## 4. 부하 Load 제어 UI

```txt
[선택된 장비 정보]

부하 센터 3        상태: 심각

장비 ID        LOAD-03
현재 부하      250 kW
사용률         120%
운전 상태      과부하
전압           380 V
주파수         60.0 Hz
통신 상태      정상
최근 업데이트  2025-05-20 14:35:10
```

```txt
[설비 제어]

선택 설비: 부하 센터 3        상태: 심각

간단 제어
[부하 감축] [비상 연락]

상세 제어 ▼
감축 비율
[ 15 ] %

실제 전송값: 0.15

[설정 전송]

제어 진행
● 명령 생성        완료
● 전송             완료
○ 응답 대기        대기 중
○ 결과             대기
```

### 백엔드 명령 매핑

```json
{
  "command_type": "load_shed",
  "payload": {
    "reduction_ratio": 0.15
  }
}
```

---

## 5. 스위치 Switch 제어 UI

```txt
[선택된 장비 정보]

SW-02        상태: CLOSED

장비 ID        SW-02
현재 상태      CLOSED
제어 가능      가능
통신 상태      정상
최근 업데이트  2025-05-20 14:35:10
```

```txt
[설비 제어]

선택 설비: SW-02        상태: CLOSED

간단 제어
[개방] [폐쇄] [리셋]

상세 제어 ▼
현재 상태
CLOSED

예상 동작
스위치 개방 시 해당 선로의 전력 흐름이 차단됩니다.

[명령 전송]

제어 진행
● 명령 생성        완료
● 전송             완료
○ 응답 대기        대기 중
○ 결과             대기
```

### 백엔드 명령 매핑

```json
{
  "command_type": "open",
  "payload": {}
}
```

```json
{
  "command_type": "close",
  "payload": {}
}
```

```json
{
  "command_type": "mode_change",
  "payload": {
    "action": "RESET"
  }
}
```

---

## 6. 공통 제어 진행 상태 UI

```txt
제어 진행

● 명령 생성        완료
● 전송             완료
◐ 응답 대기        진행 중
○ 결과             대기
```

### 성공 상태

```txt
제어 진행

● 명령 생성        완료
● 전송             완료
● 응답 수신        accepted
● 결과             성공
```

### 실패 상태

```txt
제어 진행

● 명령 생성        완료
● 전송             완료
● 응답 수신        rejected
● 결과             실패

사유
거부 사유 메시지 표시
```

---

## 7. Vue 렌더링 기준 요약

```txt
selectedDevice.type === 'solar'
→ 태양광 제어 UI 표시

selectedDevice.type === 'ess'
→ ESS 제어 UI 표시

selectedDevice.type === 'diesel'
→ 디젤 발전기 제어 UI 표시

selectedDevice.type === 'load'
→ 부하 제어 UI 표시

selectedDevice.type === 'switch'
→ 스위치 제어 UI 표시
```

---

## 8. 화면 배치 추천

```txt
오른쪽 패널 상단
[선택된 장비 정보]

오른쪽 패널 하단
[설비 제어]
  - 간단 제어
  - 상세 제어
  - 제어 진행
```

