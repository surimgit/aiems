# GK2A Download Ops Note

이 문서는 GK2A 위성 데이터 수집/전처리/운영 추론 연결 상태를 정리한다.

## Current Role

GK2A 데이터는 두 갈래로 쓴다.

```text
offline training:
  2025 GK2A archive NetCDF
  -> 지역별 64x64 patch
  -> CA, CF, CT, CLD image tensor

live inference:
  KMA APIHub GK2A area API
  -> scalar area value
  -> gk2a_area_proxy image tensor
```

현재 운영 후보 `satellite_wind_safe_v6`는 위성 image tensor를 입력으로 받는다. 다만 live 추론은 아직 실제 NetCDF crop이 아니라 `gk2a_area_proxy`이다.

## Training Archive

학습용 archive는 `.nc` NetCDF 파일이다.

확인된 projection:

```text
Lambert Conformal
```

전처리 기준:

- 원본 `.nc`는 보존한다.
- `pyproj`로 projection을 해석한다.
- 지역별 bounding box 또는 중심좌표 주변 grid를 잡는다.
- CA, CF, CT, CLD 채널을 64x64 patch로 만든다.
- 학습용 image shard는 `.npz`로 저장한다.
- metadata는 parquet로 저장한다.

## Current Packaged Dataset

현재 최종 운영 후보의 학습 기준은 v6 safe wind bundle이다.

```text
satellite_image_wind_safe_regions_2025_20260507_095435.zip
```

v5는 폐기한다.

- ASOS `WD` 해석이 잘못됐다.
- ASOS 후반 컬럼 `CA_TOT`, `CA_MID`, `SS`, `SI`, `VS`는 텍스트 필드 파싱 밀림 위험이 있다.

v7은 현재 채택하지 않는다.

- upwind/visibility feature를 추가했지만 v6보다 검증 성능이 낮았다.

## Live API Status

현재 live endpoint에서 붙인 KMA APIHub GK2A 기능:

```text
getGk2aclaArea
  - GK2A cloud amount area data

getGk2acldArea
  - GK2A cloud detection area data
```

현재 방식:

```text
GK2A area scalar
-> CA / CLD proxy encoding
-> CF_PROXY / CT_PROXY 생성
-> shape (3, 4, 64, 64)
```

즉, live 추론은 학습과 동일한 실제 위성 crop 입력이 아니다.

## Production Gap

정식 운영 입력 일치를 위해 필요한 작업:

1. KMA APIHub에서 live GK2A LE2 NetCDF 또는 equivalent grid file을 받는다.
2. `xarray`, `pyproj`로 projection 좌표를 해석한다.
3. 사용자 위치 주변 64x64 patch를 crop한다.
4. CA, CF, CT, CLD 채널을 학습과 동일하게 정규화한다.
5. `gk2a_area_proxy`를 실제 crop tensor로 교체한다.

## Related Docs

- [Satellite v6 RunPod Live Inference - 2026-05-07](./satellite-v6-runpod-live-inference-2026-05-07.md)
- [Satellite Image Training Handoff - 2026-05-06](../ml/satellite-image-training-handoff-2026-05-06.md)
