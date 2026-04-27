<script setup lang="ts">
import type { TopologyNode } from '@/types/common'

defineProps<{
  nodes: TopologyNode[]
}>()

const emit = defineEmits<{
  (e: 'select-node', nodeId: string): void
}>()
</script>

<template>
  <g class="node-layer">
    <g
      v-for="node in nodes"
      :key="node.node_id"
      class="cursor-pointer"
      :transform="`translate(${node.position.x}, ${node.position.y})`"
      @click="emit('select-node', node.node_id)"
    >
      <circle r="24" class="fill-slate-900 stroke-emerald-400" />
      <text y="40" text-anchor="middle" class="fill-slate-200 text-[12px]">{{ node.resource_id }}</text>
    </g>
  </g>
</template>
