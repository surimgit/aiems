<script setup lang="ts">
import { computed } from 'vue'
import type { TopologyLine } from '@/types/common'

const props = defineProps<{
  lines: TopologyLine[]
}>()

const lineStyles = computed(() =>
  props.lines.map((line) => {
    const width = Math.min(10, Math.max(1, Math.abs(line.flow_kw) / 100))
    const color = line.status === 'BLOCKED' ? '#f59e0b' : line.status === 'FAULT' ? '#ef4444' : '#22c55e'
    return { id: line.line_id, width, color }
  })
)
</script>

<template>
  <g class="line-layer">
    <line
      v-for="(line, idx) in lines"
      :key="line.line_id"
      :x1="200 + idx * 60"
      y1="180"
      :x2="320 + idx * 60"
      y2="280"
      :stroke="lineStyles[idx].color"
      :stroke-width="lineStyles[idx].width"
      stroke-linecap="round"
    />
  </g>
</template>
