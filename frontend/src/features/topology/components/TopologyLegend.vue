<template>
  <aside class="topology-legend">
    <h3 class="font-semibold mb-2">범례</h3>
    <ul class="space-y-1 text-sm">
      <li>전력 흐름</li>
      <li>정상 / 경고 / 비상</li>
      <li>인터록 차단</li>
    </ul>
  </aside>
</template>

<style scoped>
.topology-legend {
  @apply rounded border border-slate-700 bg-slate-900/80 p-3 text-slate-100;
}
</style>
