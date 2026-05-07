<template>
  <section class="panel-card">
    <h3 class="title">명령 실행 타임라인</h3>
    <ol class="space-y-2 text-sm text-slate-300">
      <li>요청 -> 승인 -> 실행 -> 성공/실패</li>
      <li>실패 사유 표시 (예: INTERLOCK_VIOLATION)</li>
    </ol>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-3;
}
</style>
