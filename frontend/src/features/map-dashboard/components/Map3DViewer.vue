<template>
  <div ref="mapContainer" class="h-full w-full" :class="{ 'cursor-crosshair': isAddArmed }" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { MapConnection, MapEquipment } from '../types'

const props = defineProps<{
  equipmentData: MapEquipment[]
  connections: MapConnection[]
  isEditMode: boolean
  isAddArmed: boolean
}>()

const emit = defineEmits<{
  (e: 'update-positions', value: Record<string, { x: number; y: number }>): void
  (e: 'map-click', lngLat: [number, number]): void
  (e: 'equip-click', id: string): void
  (e: 'zoom-change', zoom: number): void
}>()

const mapContainer = ref<HTMLElement | null>(null)
let map: maplibregl.Map | null = null
let animationId: number | null = null

const toPointFeatureCollection = () => ({
  type: 'FeatureCollection',
  features: props.equipmentData.map((e) => ({
    type: 'Feature',
    properties: { id: e.id },
    geometry: { type: 'Point', coordinates: e.lngLat }
  }))
})

const toBoxFeatureCollection = () => ({
  type: 'FeatureCollection',
  features: props.equipmentData.map((e) => {
    const size = 0.00016
    const [lng, lat] = e.lngLat
    return {
      type: 'Feature',
      properties: {
        id: e.id,
        status: e.status,
        height: 36
      },
      geometry: {
        type: 'Polygon',
        coordinates: [[
          [lng - size, lat - size],
          [lng + size, lat - size],
          [lng + size, lat + size],
          [lng - size, lat + size],
          [lng - size, lat - size]
        ]]
      }
    }
  })
})

const toLineFeatureCollection = () => {
  const equipmentMap = new Map(props.equipmentData.map((item) => [item.id, item]))
  return {
    type: 'FeatureCollection',
    features: props.connections
      .map((line) => {
        const from = equipmentMap.get(line.fromEquipmentId)
        const to = equipmentMap.get(line.toEquipmentId)
        if (!from || !to) return null

        const busLng = (from.lngLat[0] + to.lngLat[0]) / 2
        return {
          type: 'Feature',
          properties: {
            id: line.id,
            status: line.status,
            direction: line.direction,
            arrow: line.direction === 'FORWARD' ? '▶' : line.direction === 'REVERSE' ? '◀' : '◀▶'
          },
          geometry: {
            type: 'LineString',
            coordinates: [
              from.lngLat,
              [busLng, from.lngLat[1]],
              [busLng, to.lngLat[1]],
              to.lngLat
            ]
          }
        }
      })
      .filter(Boolean)
  }
}

const refreshMapSources = () => {
  if (!map) return
  const points = map.getSource('points-source') as maplibregl.GeoJSONSource | undefined
  if (points) points.setData(toPointFeatureCollection() as any)
  const boxes = map.getSource('3d-boxes-source') as maplibregl.GeoJSONSource | undefined
  if (boxes) boxes.setData(toBoxFeatureCollection() as any)
  const lines = map.getSource('power-lines-source') as maplibregl.GeoJSONSource | undefined
  if (lines) lines.setData(toLineFeatureCollection() as any)
}

const startAnimation = () => {
  const dashLen = 2
  const gapLen = 2
  const steps = 12
  const sequence: number[][] = []
  const total = dashLen + gapLen
  for (let i = 0; i < steps; i += 1) {
    const offset = (total * i) / steps
    if (offset < dashLen) sequence.push([dashLen - offset, gapLen, offset, 0])
    else sequence.push([0, gapLen - (offset - dashLen), dashLen, offset - dashLen])
  }

  let stepIndex = 0
  let lastTime = 0

  const animate = (timestamp: number) => {
    if (!map) return
    if (!lastTime) lastTime = timestamp
    const progress = timestamp - lastTime
    const blink = 0.6 + 0.3 * Math.sin(timestamp / 140)

    if (map.getLayer('lines-main-error')) {
      map.setPaintProperty('lines-main-error', 'line-opacity', blink)
      map.setPaintProperty('lines-glow-error', 'line-opacity', blink * 0.5)
    }
    if (map.getLayer('boxes-error')) {
      map.setPaintProperty('boxes-error', 'fill-extrusion-opacity', blink)
    }

    if (progress > 42) {
      stepIndex = (stepIndex - 1 + steps) % steps
      const dash = sequence[stepIndex]
      if (map.getLayer('lines-main-normal')) map.setPaintProperty('lines-main-normal', 'line-dasharray', dash)
      if (map.getLayer('lines-main-error')) map.setPaintProperty('lines-main-error', 'line-dasharray', dash)
      lastTime = timestamp
    }

    animationId = requestAnimationFrame(animate)
  }

  animationId = requestAnimationFrame(animate)
}

onMounted(() => {
  if (!mapContainer.value) return

  map = new maplibregl.Map({
    container: mapContainer.value,
    style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    center: [129.0755, 35.1785],
    zoom: 16.5,
    pitch: 60,
    bearing: -15
  })

  map.on('zoom', () => {
    if (!map) return
    emit('zoom-change', map.getZoom())
  })

  map.on('load', () => {
    if (!map) return

    map.addSource('points-source', { type: 'geojson', data: toPointFeatureCollection() as any, cluster: true, clusterRadius: 50, clusterMaxZoom: 16 })
    map.addSource('3d-boxes-source', { type: 'geojson', data: toBoxFeatureCollection() as any })
    map.addSource('power-lines-source', { type: 'geojson', data: toLineFeatureCollection() as any })

    map.addLayer({ id: 'cluster-circles', type: 'circle', source: 'points-source', filter: ['has', 'point_count'], maxzoom: 16.0, paint: { 'circle-color': '#3b82f6', 'circle-radius': 20, 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff' } })
    map.addLayer({ id: 'cluster-count', type: 'symbol', source: 'points-source', filter: ['has', 'point_count'], maxzoom: 16.0, layout: { 'text-field': '{point_count}', 'text-size': 14 }, paint: { 'text-color': '#ffffff' } })

    map.addLayer({ id: 'lines-glow-normal', type: 'line', source: 'power-lines-source', minzoom: 16.0, filter: ['==', ['get', 'status'], 'normal'], paint: { 'line-color': '#ffffff', 'line-width': 8, 'line-opacity': 0.18, 'line-blur': 4 } })
    map.addLayer({ id: 'lines-glow-error', type: 'line', source: 'power-lines-source', minzoom: 16.0, filter: ['==', ['get', 'status'], 'error'], paint: { 'line-color': '#ef4444', 'line-width': 10, 'line-opacity': 0.45, 'line-blur': 6 } })
    map.addLayer({ id: 'lines-glow-stopped', type: 'line', source: 'power-lines-source', minzoom: 16.0, filter: ['==', ['get', 'status'], 'stopped'], paint: { 'line-color': '#9ca3af', 'line-width': 6, 'line-opacity': 0.14, 'line-blur': 2 } })

    map.addLayer({ id: 'lines-main-normal', type: 'line', source: 'power-lines-source', minzoom: 16.0, filter: ['==', ['get', 'status'], 'normal'], paint: { 'line-color': '#ffffff', 'line-width': 3, 'line-dasharray': [2, 2] } })
    map.addLayer({ id: 'lines-main-error', type: 'line', source: 'power-lines-source', minzoom: 16.0, filter: ['==', ['get', 'status'], 'error'], paint: { 'line-color': '#ef4444', 'line-width': 3, 'line-dasharray': [2, 2] } })
    map.addLayer({ id: 'lines-main-stopped', type: 'line', source: 'power-lines-source', minzoom: 16.0, filter: ['==', ['get', 'status'], 'stopped'], paint: { 'line-color': '#9ca3af', 'line-width': 2 } })
    map.addLayer({ id: 'lines-direction', type: 'symbol', source: 'power-lines-source', minzoom: 16.0, layout: { 'symbol-placement': 'line', 'text-field': ['get', 'arrow'], 'text-size': 10, 'symbol-spacing': 100 }, paint: { 'text-color': '#e2e8f0', 'text-opacity': 0.8 } })

    map.addLayer({ id: 'boxes-base', type: 'fill-extrusion', source: '3d-boxes-source', minzoom: 16.0, filter: ['!=', ['get', 'status'], 'error'], paint: { 'fill-extrusion-color': ['match', ['get', 'status'], 'normal', '#ffffff', 'stopped', '#9ca3af', '#ffffff'], 'fill-extrusion-height': ['get', 'height'], 'fill-extrusion-base': 0, 'fill-extrusion-opacity': 0.9 } })
    map.addLayer({ id: 'boxes-error', type: 'fill-extrusion', source: '3d-boxes-source', minzoom: 16.0, filter: ['==', ['get', 'status'], 'error'], paint: { 'fill-extrusion-color': '#ef4444', 'fill-extrusion-height': ['get', 'height'], 'fill-extrusion-base': 0, 'fill-extrusion-opacity': 0.9 } })

    map.on('render', () => {
      if (!map) return
      const positions: Record<string, { x: number; y: number }> = {}
      props.equipmentData.forEach((e) => {
        const point = map!.project(e.lngLat)
        positions[e.id] = { x: point.x, y: point.y }
      })
      emit('update-positions', positions)
    })

    map.on('click', (event) => {
      if (!map) return
      const features = map.queryRenderedFeatures(event.point, { layers: ['boxes-base', 'boxes-error'] })
      if (features.length > 0) {
        const id = features[0].properties?.id
        if (id) emit('equip-click', String(id))
        return
      }
      if (props.isEditMode && props.isAddArmed) {
        emit('map-click', [event.lngLat.lng, event.lngLat.lat])
      }
    })

    map.on('mouseenter', 'boxes-base', () => {
      if (!map || !props.isEditMode) return
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', 'boxes-base', () => {
      if (!map) return
      map.getCanvas().style.cursor = ''
    })

    startAnimation()
  })
})

onBeforeUnmount(() => {
  if (animationId) cancelAnimationFrame(animationId)
  if (map) map.remove()
})

watch(() => props.equipmentData, refreshMapSources, { deep: true })
watch(() => props.connections, refreshMapSources, { deep: true })
</script>
