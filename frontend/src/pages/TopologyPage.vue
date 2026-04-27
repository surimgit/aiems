<script setup lang="ts">
/**
 * TopologyPage.vue - 토폴로지 페이지
 * 
 * [중요] 이 페이지는 조합 전용 페이지입니다.
 * - API를 직접 호출하지 마세요.
 */

import { useTopologyFeature } from '@/features/topology'
import { onMounted } from 'vue'

// biome-ignore lint/correctness/noUnusedVariables: used in template
const { nodes, links, initialize } = useTopologyFeature()

onMounted(async () => {
  await initialize()
})
</script>

<template>
  <div class="topology-page">
    <h1 class="page-title">설비 토폴로지</h1>
    
    <!-- 토폴로지 다이어그램 -->
    <section class="topology-diagram">
      <div class="node-list">
        <div 
          v-for="node in nodes" 
          :key="node.id" 
          class="node"
          :class="node.type"
        >
          <span class="node-name">{{ node.name }}</span>
          <span class="node-power">{{ node.power }} kW</span>
          <span class="node-status">{{ node.status }}</span>
        </div>
      </div>
      
      <div class="link-list">
        <div 
          v-for="(link, index) in links" 
          :key="index"
          class="link"
        >
          {{ link.source }} → {{ link.target }} ({{ link.power }} kW)
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.topology-page {
  @apply p-6;
}

.page-title {
  @apply text-2xl font-bold mb-6;
}

.topology-diagram {
  @apply bg-gray-100 p-4 rounded;
}

.node-list {
  @apply flex gap-4 mb-4;
}

.node {
  @apply p-4 bg-white rounded shadow;
}

.node.grid { @apply border-blue-500; }
.node.pv { @apply border-yellow-500; }
.node.ess { @apply border-green-500; }
.node.load { @apply border-red-500; }

.node-name {
  @apply block font-semibold;
}

.node-power {
  @apply block text-lg;
}

.node-status {
  @apply text-sm text-gray-500;
}
</style>
