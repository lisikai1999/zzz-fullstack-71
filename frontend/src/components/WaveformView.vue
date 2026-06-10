<template>
  <div class="waveform-view">
    <h4>波形</h4>
    <div class="canvas-container" ref="container">
      <canvas ref="canvas" @click="handleClick" @wheel.prevent="handleZoom"
              @mousedown="startSelect" @mousemove="onMouseMove" @mouseup="endSelect"></canvas>
    </div>
    <div class="waveform-info">
      <span>{{ formatTime(viewStart) }} - {{ formatTime(viewEnd) }}</span>
      <button v-if="viewStart > 0 || viewEnd < duration" @click="resetZoom">重置缩放</button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  audioFileId: Number,
  currentTime: Number,
  duration: Number,
  isPlaying: Boolean
})

const emit = defineEmits(['seek'])

const canvas = ref(null)
const container = ref(null)
const peaks = ref([])
const viewStart = ref(0)
const viewEnd = ref(0)
const selecting = ref(false)
const selectStart = ref(0)

let animFrame = null

onMounted(() => {
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)
})

watch(() => props.audioFileId, loadWaveform, { immediate: true })
watch(() => props.currentTime, drawFrame)
watch(() => props.duration, (d) => { viewEnd.value = d })

async function loadWaveform() {
  if (!props.audioFileId) return
  viewStart.value = 0
  viewEnd.value = props.duration || 10
  const data = await api.getWaveform(props.audioFileId, viewStart.value, viewEnd.value)
  peaks.value = data.peaks
  await nextTick()
  drawFrame()
}

async function loadVisibleWaveform() {
  const data = await api.getWaveform(props.audioFileId, viewStart.value, viewEnd.value)
  peaks.value = data.peaks
  drawFrame()
}

function resizeCanvas() {
  if (!canvas.value || !container.value) return
  canvas.value.width = container.value.clientWidth
  canvas.value.height = 120
  drawFrame()
}

function drawFrame() {
  const ctx = canvas.value?.getContext('2d')
  if (!ctx || peaks.value.length === 0) return

  const w = canvas.value.width
  const h = canvas.value.height
  const mid = h / 2

  ctx.clearRect(0, 0, w, h)

  // Background
  ctx.fillStyle = '#0d1b2a'
  ctx.fillRect(0, 0, w, h)

  // Center line
  ctx.strokeStyle = '#1a3a5c'
  ctx.beginPath()
  ctx.moveTo(0, mid)
  ctx.lineTo(w, mid)
  ctx.stroke()

  // Waveform
  const barWidth = w / peaks.value.length
  ctx.fillStyle = '#4ecdc4'
  for (let i = 0; i < peaks.value.length; i++) {
    const peak = peaks.value[i]
    const x = i * barWidth
    const minY = mid + peak.min * mid
    const maxY = mid + peak.max * mid
    ctx.fillRect(x, maxY, Math.max(1, barWidth - 0.5), minY - maxY)
  }

  // Playback cursor
  const viewDuration = viewEnd.value - viewStart.value
  if (props.currentTime >= viewStart.value && props.currentTime <= viewEnd.value) {
    const cursorX = ((props.currentTime - viewStart.value) / viewDuration) * w
    ctx.strokeStyle = '#e94560'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(cursorX, 0)
    ctx.lineTo(cursorX, h)
    ctx.stroke()
  }
}

function handleClick(e) {
  if (selecting.value) return
  const rect = canvas.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const ratio = x / canvas.value.width
  const time = viewStart.value + ratio * (viewEnd.value - viewStart.value)
  emit('seek', time)
}

function handleZoom(e) {
  const rect = canvas.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const ratio = x / canvas.value.width
  const center = viewStart.value + ratio * (viewEnd.value - viewStart.value)

  const currentRange = viewEnd.value - viewStart.value
  const factor = e.deltaY > 0 ? 1.3 : 0.7
  const newRange = Math.max(0.1, Math.min(props.duration, currentRange * factor))

  viewStart.value = Math.max(0, center - newRange * ratio)
  viewEnd.value = Math.min(props.duration, viewStart.value + newRange)

  loadVisibleWaveform()
}

function resetZoom() {
  viewStart.value = 0
  viewEnd.value = props.duration
  loadVisibleWaveform()
}

function startSelect(e) {
  if (e.shiftKey) {
    selecting.value = true
    const rect = canvas.value.getBoundingClientRect()
    selectStart.value = (e.clientX - rect.left) / canvas.value.width
  }
}

function onMouseMove() {}

function endSelect(e) {
  if (!selecting.value) return
  selecting.value = false
  const rect = canvas.value.getBoundingClientRect()
  const selectEnd = (e.clientX - rect.left) / canvas.value.width
  const range = viewEnd.value - viewStart.value

  const start = viewStart.value + Math.min(selectStart.value, selectEnd) * range
  const end = viewStart.value + Math.max(selectStart.value, selectEnd) * range

  if (end - start > 0.01) {
    viewStart.value = start
    viewEnd.value = end
    loadVisibleWaveform()
  }
}

function formatTime(t) {
  const m = Math.floor(t / 60)
  const s = (t % 60).toFixed(1)
  return `${m}:${s.padStart(4, '0')}`
}
</script>

<style scoped>
.waveform-view {
  background: #16213e;
  border-radius: 8px;
  padding: 12px;
}

.waveform-view h4 {
  color: #64ffda;
  margin-bottom: 8px;
  font-size: 13px;
}

.canvas-container {
  width: 100%;
  border-radius: 4px;
  overflow: hidden;
}

canvas {
  width: 100%;
  height: 120px;
  display: block;
  cursor: crosshair;
}

.waveform-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  font-size: 11px;
  color: #666;
}

.waveform-info button {
  font-size: 11px;
  padding: 4px 8px;
}
</style>
