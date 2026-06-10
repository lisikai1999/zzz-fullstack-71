<template>
  <div class="spectrum-view">
    <div class="spectrum-tabs">
      <button :class="{ active: mode === 'fft' }" @click="mode = 'fft'">频谱</button>
      <button :class="{ active: mode === 'spectrogram' }" @click="mode = 'spectrogram'; loadSpectrogram()">语谱图</button>
    </div>
    <div class="spectrum-legend" v-if="mode === 'fft' && comparisonData">
      <span class="legend-original">— 原始</span>
      <span class="legend-processed">— 处理后</span>
    </div>
    <div class="canvas-container">
      <canvas ref="canvas"></canvas>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  audioFileId: Number,
  currentTime: Number,
  chainId: Number,
  comparisonData: Object
})

const canvas = ref(null)
const mode = ref('fft')
const spectrumData = ref(null)
const spectrogramData = ref(null)

onMounted(() => {
  resizeCanvas()
  window.addEventListener('resize', resizeCanvas)
})

watch(() => props.currentTime, loadSpectrum)
watch(() => props.audioFileId, () => {
  if (mode.value === 'spectrogram') loadSpectrogram()
  else loadSpectrum()
})
watch(mode, () => {
  if (mode.value === 'fft') drawFFT()
})
watch(() => props.comparisonData, () => {
  if (mode.value === 'fft') drawFFT()
})

async function loadSpectrum() {
  if (!props.audioFileId || mode.value !== 'fft') return
  spectrumData.value = await api.getSpectrum(props.audioFileId, props.currentTime)
  drawFFT()
}

async function loadSpectrogram() {
  if (!props.audioFileId) return
  spectrogramData.value = await api.getSpectrogram(props.audioFileId)
  drawSpectrogram()
}

function resizeCanvas() {
  if (!canvas.value) return
  const container = canvas.value.parentElement
  canvas.value.width = container.clientWidth
  canvas.value.height = 160
  if (mode.value === 'fft') drawFFT()
  else drawSpectrogram()
}

function freqToX(freq, w) {
  return (Math.log10(freq) - Math.log10(20)) / (Math.log10(22050) - Math.log10(20)) * w
}

function dbToY(db, h) {
  return h * (1 - (Math.max(-80, Math.min(0, db)) + 80) / 80)
}

function drawFFT() {
  const ctx = canvas.value?.getContext('2d')
  if (!ctx) return

  const w = canvas.value.width
  const h = canvas.value.height

  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = '#0d1b2a'
  ctx.fillRect(0, 0, w, h)

  // Grid
  ctx.strokeStyle = '#1a2a4a'
  ctx.lineWidth = 0.5
  for (let db = -80; db <= 0; db += 20) {
    const y = dbToY(db, h)
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(w, y)
    ctx.stroke()
    ctx.fillStyle = '#555'
    ctx.font = '9px monospace'
    ctx.fillText(`${db}dB`, 2, y - 2)
  }

  const freqLabels = [100, 1000, 5000, 10000, 20000]
  for (const f of freqLabels) {
    const x = freqToX(f, w)
    ctx.fillStyle = '#444'
    ctx.font = '9px monospace'
    ctx.fillText(f >= 1000 ? `${f/1000}k` : `${f}`, x, h - 2)
  }

  // If we have comparison data (original + processed), draw both
  if (props.comparisonData) {
    drawSpectrumCurve(ctx, props.comparisonData.original, w, h, 'rgba(100, 255, 218, 0.6)', 'rgba(100, 255, 218, 0.05)')
    drawSpectrumCurve(ctx, props.comparisonData.processed, w, h, 'rgba(255, 107, 107, 0.9)', 'rgba(255, 107, 107, 0.08)')
  } else if (spectrumData.value) {
    drawSpectrumCurve(ctx, spectrumData.value, w, h, '#64ffda', 'rgba(100, 255, 218, 0.1)')
  }
}

function drawSpectrumCurve(ctx, data, w, h, strokeColor, fillColor) {
  const { frequencies, magnitude_db } = data
  if (!frequencies || frequencies.length === 0) return

  ctx.beginPath()
  ctx.strokeStyle = strokeColor
  ctx.lineWidth = 1.5

  let started = false
  let lastX = 0
  for (let i = 1; i < frequencies.length; i++) {
    const freq = frequencies[i]
    if (freq < 20) continue
    const x = freqToX(freq, w)
    const y = dbToY(magnitude_db[i], h)

    if (!started) {
      ctx.moveTo(x, y)
      started = true
    } else {
      ctx.lineTo(x, y)
    }
    lastX = x
  }
  ctx.stroke()

  // Fill under curve
  ctx.lineTo(lastX, h)
  ctx.lineTo(freqToX(20, w), h)
  ctx.closePath()
  ctx.fillStyle = fillColor
  ctx.fill()
}

function drawSpectrogram() {
  const ctx = canvas.value?.getContext('2d')
  if (!ctx || !spectrogramData.value) return

  const w = canvas.value.width
  const h = canvas.value.height
  const { magnitude_db, times, frequencies } = spectrogramData.value

  if (!magnitude_db || magnitude_db.length === 0) return

  ctx.clearRect(0, 0, w, h)

  const nFreqs = magnitude_db.length
  const nTimes = magnitude_db[0].length
  const cellW = w / nTimes
  const cellH = h / Math.min(nFreqs, 128)
  const maxBin = Math.min(nFreqs, 128)

  for (let t = 0; t < nTimes; t++) {
    for (let f = 0; f < maxBin; f++) {
      const db = magnitude_db[f][t]
      const norm = Math.max(0, Math.min(1, (db + 80) / 80))
      const r = Math.floor(norm * 200)
      const g = Math.floor(norm * 100 + (1 - norm) * 30)
      const b = Math.floor(norm * 255)
      ctx.fillStyle = `rgb(${r},${g},${b})`
      ctx.fillRect(t * cellW, h - (f + 1) * cellH, cellW + 1, cellH + 1)
    }
  }

  if (props.currentTime && times.length > 0) {
    const maxTime = times[times.length - 1]
    const cursorX = (props.currentTime / maxTime) * w
    ctx.strokeStyle = '#e94560'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(cursorX, 0)
    ctx.lineTo(cursorX, h)
    ctx.stroke()
  }
}
</script>

<style scoped>
.spectrum-view {
  background: #16213e;
  border-radius: 8px;
  padding: 12px;
}

.spectrum-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 8px;
}

.spectrum-tabs button {
  font-size: 12px;
  padding: 4px 12px;
  background: #1a2a4a;
  border: 1px solid #2a4a7a;
}

.spectrum-tabs button.active {
  background: #0f3460;
  color: #64ffda;
  border-color: #64ffda;
}

.spectrum-legend {
  display: flex;
  gap: 16px;
  font-size: 11px;
  margin-bottom: 6px;
  padding-left: 4px;
}

.legend-original {
  color: rgba(100, 255, 218, 0.8);
}

.legend-processed {
  color: rgba(255, 107, 107, 0.9);
}

.canvas-container {
  width: 100%;
  border-radius: 4px;
  overflow: hidden;
}

canvas {
  width: 100%;
  height: 160px;
  display: block;
}
</style>
