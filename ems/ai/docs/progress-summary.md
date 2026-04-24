# AI Progress Summary

## Done

- KMA ASOS 수집 스크립트 작성 및 수집 완료
- `station_165 = 목포` 확인
- Google Drive 데이터 루트 구조 생성
- KPX 태양광 CSV 정규화 완료
- KMA + KPX 병합 CSV 생성 완료
- `KMA + KPX 2025` 기반 태양광 학습용 train/val split 생성 완료
- West Power API 수집 스크립트 초안 작성
- 문서 구조 재정리 시작

## Current Training Target

- 문제: 다음 1시간 태양광 발전량 예측
- 입력: 목포 기상 + 전남 태양광 최근 이력
- 출력: `future_solar_P_kw`

## Current Limitation

- 소비 예측용 실제 현장 부하 데이터가 아직 없다.
- 공공 통계 데이터는 소비 baseline 용도로는 유용하지만, 시간 단위 load 정답 데이터는 아니다.

## Next

- 태양광 baseline 학습 실행
- 오프라인 백테스트 흐름 정리
- 소비 예측에 필요한 현장 데이터 스키마 정의
- LLM context 입력 포맷 초안 정의
