<template>
  <div class="playback-controls">
    <div class="controls-row">
      <button @click="togglePlay" class="play-btn">
        {{ playing ? '⏸' : '▶' }}
      </button>
      <button @click="stop" class="stop-btn">⏹</button>
      <span class="time-display">
        {{ formatTime(currentTime) }} / {{ formatTime(audioFile.duration) }}
      </span>
      <div class="audition-indicator" v-if="auditioning">
        <span class="audition-dot"></span> 试听中
      </div>
      <label class="source-toggle">
        <input type="checkbox" v-model="autoAudition" />
        <span>实时试听</span>
      </label>
      <label class="source-toggle">
        <input type="checkbox" v-model="playProcessed" :disabled="!processedBlob" />
        <span>播放处理后</span>
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  audioFile: Object,
  processedBlob: Blob
})

const emit = defineEmits(['time-update', 'play-state'])

const playing = ref(false)
const currentTime = ref(0)
const playProcessed = ref(false)
const autoAudition = ref(true)
const auditioning = ref(false)

let audioContext = null
let sourceNode = null
let auditionSource = null
let startOffset = 0
let startTime = 0
let animFrame = null

watch(() => props.processedBlob, () => {
  if (!props.processedBlob) playProcessed.value = false
})

function getAudioContext() {
  if (!audioContext) {
    audioContext = new (window.AudioContext || window.webkitAudioContext)()
  }
  return audioContext
}

async function togglePlay() {
  if (playing.value) {
    pause()
  } else {
    await play()
  }
}

async function play() {
  const ctx = getAudioContext()

  if (sourceNode) {
    sourceNode.stop()
    sourceNode = null
  }

  let arrayBuffer
  if (playProcessed.value && props.processedBlob) {
    arrayBuffer = await props.processedBlob.arrayBuffer()
  } else {
    const res = await fetch(`/api/audio/${props.audioFile.id}/download`)
    arrayBuffer = await res.arrayBuffer()
  }

  const audioBuffer = await ctx.decodeAudioData(arrayBuffer)
  sourceNode = ctx.createBufferSource()
  sourceNode.buffer = audioBuffer
  sourceNode.connect(ctx.destination)

  startOffset = currentTime.value
  startTime = ctx.currentTime
  sourceNode.start(0, startOffset)
  playing.value = true
  emit('play-state', true)

  sourceNode.onended = () => {
    if (playing.value) {
      playing.value = false
      emit('play-state', false)
      currentTime.value = 0
      emit('time-update', 0)
    }
  }

  updateTime()
}

function pause() {
  if (sourceNode) {
    sourceNode.stop()
    sourceNode = null
  }
  playing.value = false
  emit('play-state', false)
  if (animFrame) cancelAnimationFrame(animFrame)
}

function stop() {
  pause()
  currentTime.value = 0
  startOffset = 0
  emit('time-update', 0)
}

function updateTime() {
  if (!playing.value || !audioContext) return
  currentTime.value = startOffset + (audioContext.currentTime - startTime)
  if (currentTime.value >= props.audioFile.duration) {
    stop()
    return
  }
  emit('time-update', currentTime.value)
  animFrame = requestAnimationFrame(updateTime)
}

async function playAuditionBlob(blob) {
  if (!autoAudition.value) return
  const ctx = getAudioContext()

  if (auditionSource) {
    auditionSource.stop()
    auditionSource = null
  }

  try {
    auditioning.value = true
    const arrayBuffer = await blob.arrayBuffer()
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer)
    auditionSource = ctx.createBufferSource()
    auditionSource.buffer = audioBuffer
    auditionSource.connect(ctx.destination)
    auditionSource.start()
    auditionSource.onended = () => {
      auditioning.value = false
      auditionSource = null
    }
  } catch {
    auditioning.value = false
  }
}

function getCurrentTime() {
  return currentTime.value
}

function isAutoAuditionEnabled() {
  return autoAudition.value
}

function formatTime(t) {
  const m = Math.floor(t / 60)
  const s = (t % 60).toFixed(1)
  return `${m}:${s.padStart(4, '0')}`
}

onBeforeUnmount(() => {
  if (sourceNode) sourceNode.stop()
  if (auditionSource) auditionSource.stop()
  if (animFrame) cancelAnimationFrame(animFrame)
  if (audioContext) audioContext.close()
})

defineExpose({ playAuditionBlob, getCurrentTime, isAutoAuditionEnabled })
</script>

<style scoped>
.playback-controls {
  margin-top: 12px;
}

.controls-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.play-btn, .stop-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  background: #0f3460;
  border: 1px solid #1a5276;
}

.play-btn:hover {
  background: #1a5276;
}

.time-display {
  font-family: monospace;
  font-size: 13px;
  color: #8bb4ff;
}

.audition-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #ff6b6b;
}

.audition-dot {
  width: 6px;
  height: 6px;
  background: #ff6b6b;
  border-radius: 50%;
  animation: pulse 0.8s infinite alternate;
}

@keyframes pulse {
  from { opacity: 0.4; }
  to { opacity: 1; }
}

.source-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #888;
  cursor: pointer;
  margin-left: auto;
}

.source-toggle input {
  width: auto;
}
</style>
