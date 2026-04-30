<template>
  <section class="panel-card">
    <h3 class="title">전력 밸런스 추이</h3>
    <div class="chart-placeholder">production / consumption / net_power (1h, 6h, 24h)</div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-3;
}

.chart-placeholder {
  @apply h-40 rounded border border-slate-700 bg-slate-950/60 p-3 text-sm text-slate-400;
}
</style>
