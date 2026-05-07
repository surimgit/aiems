<template>
  <section class="panel-card">
    <slot />
  </section>
</template>

<style scoped>
.panel-card {
  @apply rounded border border-slate-700 bg-slate-900/80 p-4 text-slate-100;
}
</style>
