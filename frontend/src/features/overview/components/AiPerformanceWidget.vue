<template>
  <section class="panel-card">
    <h3 class="title">AI 성과</h3>
    <div class="content">
      <p class="value">2,450,000 원</p>
      <div class="meta">
        <span>목표 1,850,000 원</span>
        <span>달성률 132%</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply mb-3 font-semibold;
}

.content {
  @apply flex h-40 flex-col justify-between rounded border border-slate-700 bg-slate-950/60 p-3;
}

.value {
  @apply text-2xl font-semibold text-cyan-300;
}

.meta {
  @apply flex items-center justify-between text-sm text-slate-300;
}
</style>
