<template>
  <div class="knob-wrapper">
    <div class="knob-container" @mousedown="startDrag" @wheel.prevent="onWheel">
      <canvas ref="canvas" width="48" height="48"></canvas>
    </div>
    <span class="knob-value">{{ displayValue }}</span>
    <span class="knob-label">{{ label }}</span>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'

const props = defineProps({
  label: String,
  value: Number,
  min: { type: Number, default: 0 },
  max: { type: Number, default: 1 },
  step: { type: Number, default: 0.01 }
})

const emit = defineEmits(['update'])
const canvas = ref(null)

const normalizedValue = computed(() => (props.value - props.min) / (props.max - props.min))
const displayValue = computed(() => {
  if (Math.abs(props.value) >= 100) return props.value.toFixed(0)
  if (Math.abs(props.value) >= 10) return props.value.toFixed(1)
  return props.value.toFixed(2)
})

function drawKnob() {
  const ctx = canvas.value?.getContext('2d')
  if (!ctx) return

  const size = 48
  const center = size / 2
  const radius = 18
  const startAngle = 0.75 * Math.PI
  const endAngle = 2.25 * Math.PI
  const angle = startAngle + normalizedValue.value * (endAngle - startAngle)

  ctx.clearRect(0, 0, size, size)

  // Track
  ctx.beginPath()
  ctx.arc(center, center, radius, startAngle, endAngle)
  ctx.strokeStyle = '#333'
  ctx.lineWidth = 3
  ctx.lineCap = 'round'
  ctx.stroke()

  // Value arc
  ctx.beginPath()
  ctx.arc(center, center, radius, startAngle, angle)
  ctx.strokeStyle = '#64ffda'
  ctx.lineWidth = 3
  ctx.lineCap = 'round'
  ctx.stroke()

  // Indicator dot
  const dotX = center + (radius - 6) * Math.cos(angle)
  const dotY = center + (radius - 6) * Math.sin(angle)
  ctx.beginPath()
  ctx.arc(dotX, dotY, 3, 0, Math.PI * 2)
  ctx.fillStyle = '#fff'
  ctx.fill()
}

onMounted(drawKnob)
watch(() => props.value, drawKnob)

let dragStartY = 0
let dragStartValue = 0

function startDrag(e) {
  dragStartY = e.clientY
  dragStartValue = props.value
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e) {
  const delta = (dragStartY - e.clientY) * (props.max - props.min) / 200
  let newVal = dragStartValue + delta
  newVal = Math.round(newVal / props.step) * props.step
  newVal = Math.max(props.min, Math.min(props.max, newVal))
  emit('update', newVal)
}

function stopDrag() {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

function onWheel(e) {
  const direction = e.deltaY > 0 ? -1 : 1
  let newVal = props.value + direction * props.step
  newVal = Math.max(props.min, Math.min(props.max, newVal))
  emit('update', newVal)
}
</script>

<style scoped>
.knob-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 56px;
}

.knob-container {
  cursor: ns-resize;
  user-select: none;
}

.knob-value {
  font-size: 11px;
  color: #64ffda;
  font-family: monospace;
}

.knob-label {
  font-size: 10px;
  color: #888;
  text-align: center;
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
