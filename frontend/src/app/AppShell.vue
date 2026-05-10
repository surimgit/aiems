<script setup lang="ts">
</script>

<template>
  <div class="app-shell">
    <div class="app-layout">
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  @apply h-screen w-screen flex flex-col overflow-hidden bg-slate-950 text-slate-100;
}

.app-layout {
  @apply flex flex-1 min-h-0 overflow-hidden;
}

.main-content {
  @apply flex-1 min-h-0 overflow-hidden p-4 md:p-6;
}
</style>
