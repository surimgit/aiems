# S14P31S305-215 컬러 시스템 정의

## 1. 목적
- Primary / Status / Background 색상 체계를 고정한다.

## 2. 토큰 정의

### 2.1 Brand / Primary
| Token | Hex | 용도 |
|---|---|---|
| `color.primary` | `#2F6BFF` | 주요 CTA, 활성 상태 |
| `color.primary.hover` | `#3E7DFF` | 버튼 hover |

### 2.2 Background / Surface
| Token | Hex | 용도 |
|---|---|---|
| `color.bg.base` | `#071426` | 앱 전체 배경 |
| `color.bg.surface` | `#0B1B31` | 카드/패널 배경 |
| `color.border.default` | `#1E3557` | 카드/패널 경계 |

### 2.3 Status
| Token | Hex | 의미 |
|---|---|---|
| `color.status.normal` | `#22C55E` | 정상 |
| `color.status.warning` | `#F59E0B` | 경고 |
| `color.status.critical` | `#EF4444` | 심각/위험 |
| `color.status.offline` | `#6B7280` | 오프라인 |

## 3. 사용 규칙
- 상태는 색상 + 텍스트를 함께 표시한다.
- `critical`은 아이콘 배지/패널 헤더에서도 동일 색상을 사용한다.

## 4. 우측 패널 모드 강조 규칙

| 모드 | 강조 색상 | 사용 위치 |
|---|---|---|
| 알람 패널 | `color.status.warning`, `color.status.critical` | 행 텍스트, 아이콘, 배지 |
| 최근 명령 패널 | 정상=`color.status.normal`, 실패=`color.status.critical` | 결과 상태 텍스트 |
| 국가/언어 패널 | `color.primary` | 선택 카드, 적용 버튼 |
| 설비 제어 패널 | Primary / Danger | 전송 버튼, 파괴적 액션 |

## 5. 배경 깊이(Depth) 규칙

- 앱 배경: `color.bg.base`
- 메인 카드/단선도 카드: `color.bg.surface`
- 우측 패널: `color.bg.surface` + 경계 `color.border.default`
- 강조 박스(선택/활성): `color.primary` 계열 보더

> 원칙: 평시에는 색을 절제하고, 이상 상태에서만 색 대비를 강하게 사용한다.

## 6. DoD
- [ ] 토큰이 Figma Variables에 등록됨
- [ ] Tailwind theme에 동일 값 반영됨
- [ ] 상태칩 샘플(정상/경고/심각/오프라인) 확인 완료
