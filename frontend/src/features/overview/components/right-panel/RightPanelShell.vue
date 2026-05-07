<script setup lang="ts">
defineProps<{
  title: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()
</script>

<template>
  <aside class="right-panel-shell">
    <header class="right-panel-header">
      <h3 class="right-panel-title">{{ title }}</h3>
      <button class="close-button" type="button" @click="emit('close')">✕</button>
    </header>

    <section class="right-panel-body">
      <slot />
    </section>

    <footer class="right-panel-footer">
      <slot name="footer" />
    </footer>
  </aside>
</template>

<style scoped>
.right-panel-shell {
  @apply h-full rounded border border-slate-700 bg-slate-900/90 p-4 text-slate-100;
}

.right-panel-header {
  @apply mb-4 flex items-center justify-between;
}

.right-panel-title {
  @apply text-lg font-semibold;
}

.close-button {
  @apply rounded border border-slate-600 px-2 py-1 text-sm text-slate-300;
}

.right-panel-body {
  @apply space-y-3;
}

.right-panel-footer {
  @apply mt-4;
}
</style>
