# LLM Role

## Position In The System

LLM은 학습 모델 본체가 아니라 `추론 시점의 context interpreter`로 둔다.

즉 역할은:

- 사용자가 입력한 자연어 운영 맥락 해석
- 구조화된 feature 생성
- 예측 모델 입력 보조

## Why LLM Is Useful

마이크로그리드는 사이트마다 운영 패턴이 다르다.

예:

- 병원: 수술 시간대, 중환자실, 비상전원 우선
- 공장: 생산 일정, 주야간 교대
- 캠퍼스: 수업 시간표, 방학
- 리조트: 예약률, 성수기 이벤트

이런 정보는 숫자 센서 데이터만으로 바로 드러나지 않는다.

## Recommended Usage

### Input

운영자 프롬프트 예:

- `내일 오전 8시~12시 수술실 풀가동`
- `이번 주말 외래 진료 축소`
- `행사로 냉방 부하 증가 예상`

### LLM Output

LLM은 이를 직접 예측값으로 내놓지 않고, 아래 같은 구조화 값으로 바꾼다.

- `site_type = hospital`
- `surgery_load_level = high`
- `outpatient_mode = reduced`
- `cooling_bias = positive`

### Final Inference Input

최종 입력:

- 실제 수치 feature
- 날씨
- 과거 이력
- 시간 파생 feature
- LLM context feature

## Model Access

현재 가정하는 방식은 외부 API 호출이다.

- ChatGPT API 사용
- API key 기반 호출
- 프롬프트 -> 구조화 JSON 응답

## Important Constraint

LLM은 지금 단계에서 재학습 모델이 아니라 `추론 보조기`다.

즉:

- 숫자 예측 자체는 ML 모델이 담당
- LLM은 운영 맥락을 구조화하는 계층

이 분리가 유지되어야 시스템이 안정적이다.
