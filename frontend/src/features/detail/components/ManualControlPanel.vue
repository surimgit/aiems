<script setup lang="ts">
const emit = defineEmits<{
  (e: 'start'): void
  (e: 'stop'): void
  (e: 'block'): void
}>()
</script>

<template>
  <section class="panel-card">
    <h3 class="title">설비 제어</h3>
    <div class="actions">
      <button class="btn success" @click="emit('start')">가동</button>
      <button class="btn warning" @click="emit('stop')">중지</button>
      <button class="btn danger" @click="emit('block')">차단</button>
    </div>
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}

.title {
  @apply font-semibold mb-3;
}

.actions {
  @apply grid grid-cols-3 gap-2;
}

.btn {
  @apply rounded px-3 py-2 text-sm font-medium;
}

.success {
  @apply bg-emerald-600;
}

.warning {
  @apply bg-amber-600;
}

.danger {
  @apply bg-red-600;
}
</style>
