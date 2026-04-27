# Frontend Conventions

## Naming Conventions

### 파일命名
- **Vue 컴포넌트**: PascalCase (e.g., `OverviewPage.vue`)
- **TS 모듈**: kebab-case (e.g., `dashboard.client.ts`)
- **스토어**: `[name].store.ts` (e.g., `alarm.store.ts`)

###変数命名
- **컴포넌트**: PascalCase
- **함수/변수**: camelCase
- **상수**: UPPER_SNAKE_CASE
- **비私密属性**: _camelCase (underscore prefix)

###类型命名
- **인터페이스**: PascalCase (e.g., `PowerSummary`)
- **타입Alias**: PascalCase
- **enum**: PascalCase

## Import 규칙

### 경로 Alias
```typescript
// @ = src 디렉토리
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { interpretPowerSign } from '@/domain/sign'
```

### 순서
1. extern libraries (vue, pinia, etc.)
2. internal aliases (@/)
3. relative paths (./, ../)

### 예시
```typescript
import { ref, computed, onMounted } from 'vue'
import { defineStore } from 'pinia'
import { useDashboardStore } from '@/stores/dashboard/dashboard.store'
import { interpretPowerSign } from '@/domain/sign'
import type { PowerSummary } from '@/types/common'
```

## 금지 규칙

### 1. 페이지에서 API 직접 호출 금지
```typescript
// ❌ 금지
import { getPowerSummary } from '@/api/dashboard.client'
const data = await getPowerSummary('plant-01')

// ✅ 허용
import { useOverviewFeature } from '@/features/overview'
const { powerSummary } = useOverviewFeature()
```

### 2. sign 규칙 중복 구현 금지
```typescript
// ❌ 금지
const isDischarging = (power: number) => power > 0

// ✅ 허용
import { isDischarging } from '@/domain/sign'
```

### 3. 스토어에서 직접 UI 로직 금지
```typescript
// ❌ 금지 (스토어에서 view 로직)
// ✅ 허용 (스토어: 상태만, Feature: 조합)
```

### 4. ProjectDocs 계약 불일치 금지
```typescript
// ❌ 금지: 문서와 다른 임시 endpoint 유지
const path = '/dashboard/power/summary'

// ✅ 허용: ProjectDocs 계약 경로 사용
const path = `/api/plants/${siteId}/summary`
```

## 코드 스타일

### Vue 컴포지션 API 사용
```typescript
<script setup lang="ts">
// composition API 사용
const count = ref(0)
const doubled = computed(() => count.value * 2)
</script>
```

### 컴포넌트 구조
```typescript
<script setup lang="ts">
// 1. imports
import { ref } from 'vue'

// 2. types (있을 경우)
interface Props {
  title: string
}

// 3. props
const props = defineProps<Props>()

// 4. emits
const emit = defineEmits<{
  (e: 'update', value: string): void
}>()

// 5. reactive state
const isOpen = ref(false)

// 6. computed
const status = computed(() => ...)

// 7. methods
const handleClick = () => { ... }

// 8. lifecycle
onMounted(() => { ... })
</script>

<template>
  <!-- template -->
</template>

<style scoped>
/* scoped styles */
</style>
```

## 폴더 구조 규칙

### Feature 구조
```
features/
  overview/
    index.ts      # useOverviewFeature hook
  detail/
    index.ts     # useDetailFeature hook
```

### Store 구조
```
stores/
  alarm/
    alarm.store.ts    # defineStore
```
