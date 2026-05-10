<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <aside class="topology-legend">
    <h3 class="font-semibold mb-2">{{ t('topology.legend.title') }}</h3>
    <div class="space-y-2 text-xs">
      <div>
        <p class="mb-1 font-semibold text-slate-200">상태 색상</p>
        <div class="space-y-1">
          <p class="flex items-center gap-2"><span class="dot normal" />정상</p>
          <p class="flex items-center gap-2"><span class="dot stopped" />중지/대기</p>
          <p class="flex items-center gap-2"><span class="dot error" />이상</p>
        </div>
      </div>
      <div>
        <p class="mb-1 font-semibold text-slate-200">선 스타일</p>
        <div class="space-y-1">
          <p class="flex items-center gap-2"><span class="line solid" />실선: 현재 유효 연결</p>
          <p class="flex items-center gap-2"><span class="line dashed" />점선: 예비/제어 경계</p>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.topology-legend {
  @apply w-[220px] max-w-[45vw] rounded border border-slate-700 bg-slate-900/80 p-2 text-slate-100;
}

.dot {
  @apply inline-block h-2.5 w-2.5 rounded-full;
}

.dot.normal {
  @apply bg-emerald-400;
}

.dot.stopped {
  @apply bg-amber-400;
}

.dot.error {
  @apply bg-red-400;
}

.line {
  @apply inline-block h-0 w-7 border-t-2 border-slate-200;
}

.line.dashed {
  border-top-style: dashed;
}

.line.solid {
  border-top-style: solid;
}
</style>
