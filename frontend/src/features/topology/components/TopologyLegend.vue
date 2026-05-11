<script setup lang="ts">
import { useI18n } from "vue-i18n";

const { t } = useI18n();
</script>

<template>
  <aside class="topology-legend">
    <p class="mb-1 text-[12px] font-semibold">범례</p>
    <div class="space-y-1 text-[11px]">
      <p class="font-semibold text-slate-200">상태</p>
      <div class="legend-row">
        <span class="legend-item"><span class="dot normal" />정상</span>
        <span class="legend-item"><span class="dot stopped" />중지/대기</span>
        <span class="legend-item"><span class="dot error" />이상</span>
      </div>
      <p class="font-semibold text-slate-200">연결</p>
      <div class="legend-row">
        <span class="legend-item"><span class="line valid" />유효</span>
        <span class="legend-item"><span class="line stopped" />차단</span>
        <span class="legend-item"><span class="line error" />장애</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.topology-legend {
  @apply inline-block w-auto max-w-[78vw] rounded border border-slate-700 bg-slate-900/80 p-2 text-slate-100;
}

.legend-row {
  @apply flex flex-wrap items-center gap-2;
}

.legend-item {
  @apply inline-flex items-center gap-1.5;
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
  @apply inline-block h-0 w-4 border-t-2 border-slate-200;
}

.line.valid {
  border-top-style: dashed;
  border-top-color: #e2e8f0;
}

.line.stopped {
  border-top-style: solid;
  border-top-color: #94a3b8;
}

.line.error {
  border-top-style: dashed;
  border-top-color: #f87171;
}
</style>
