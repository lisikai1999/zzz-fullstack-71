<template>
  <div class="app">
    <header class="app-header">
      <h1>音频效果链处理器</h1>
      <div class="project-controls">
        <select v-model="currentProjectId" @change="loadProject">
          <option :value="null" disabled>选择项目</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
        <button @click="createNewProject">新建项目</button>
      </div>
    </header>

    <main class="app-main" v-if="currentProjectId">
      <div class="top-section">
        <div class="audio-panel">
          <div class="panel-header">
            <h3>音频文件</h3>
            <label class="upload-btn">
              上传WAV
              <input type="file" accept=".wav" @change="handleUpload" hidden />
            </label>
          </div>
          <div v-if="audioFile" class="audio-info">
            <span>{{ audioFile.filename }}</span>
            <span>{{ audioFile.duration.toFixed(1) }}s / {{ audioFile.sample_rate }}Hz</span>
          </div>
          <PlaybackControls
            v-if="audioFile"
            ref="playbackRef"
            :audio-file="audioFile"
            :processed-blob="processedBlob"
            @time-update="onTimeUpdate"
            @play-state="onPlayState"
          />
        </div>
      </div>

      <div class="visualization-section" v-if="audioFile">
        <WaveformView
          :audio-file-id="audioFile.id"
          :current-time="currentTime"
          :duration="audioFile.duration"
          :is-playing="isPlaying"
          @seek="onSeek"
        />
        <SpectrumView
          :audio-file-id="audioFile.id"
          :current-time="currentTime"
          :chain-id="currentChainId"
          :comparison-data="spectrumComparison"
        />
      </div>

      <div class="chain-section">
        <EffectChainEditor
          v-if="currentProjectId"
          :project-id="currentProjectId"
          @chain-changed="onChainChanged"
          @chain-selected="onChainSelected"
          @params-tweaked="onParamsTweaked"
        />
      </div>

      <div class="process-section" v-if="audioFile && currentChainId">
        <button class="process-btn" @click="processAudio" :disabled="processing">
          {{ processing ? '处理中...' : '应用效果链（全量）' }}
        </button>
        <button v-if="processedBlob" class="download-btn" @click="downloadProcessed">
          下载处理结果
        </button>
      </div>
    </main>

    <div v-else class="empty-state">
      <p>请选择或创建一个项目开始</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from './api.js'
import EffectChainEditor from './components/EffectChainEditor.vue'
import WaveformView from './components/WaveformView.vue'
import SpectrumView from './components/SpectrumView.vue'
import PlaybackControls from './components/PlaybackControls.vue'

const projects = ref([])
const currentProjectId = ref(null)
const audioFile = ref(null)
const currentChainId = ref(null)
const currentTime = ref(0)
const isPlaying = ref(false)
const processing = ref(false)
const processedBlob = ref(null)
const spectrumComparison = ref(null)
const playbackRef = ref(null)

let previewDebounceTimer = null
let auditionDebounceTimer = null
let lastNodes = null
let previewAbortController = null

onMounted(async () => {
  projects.value = await api.listProjects()
})

async function createNewProject() {
  const name = prompt('项目名称:')
  if (!name) return
  const project = await api.createProject(name)
  projects.value.push(project)
  currentProjectId.value = project.id
}

async function loadProject() {
  audioFile.value = null
  processedBlob.value = null
  spectrumComparison.value = null
}

async function handleUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  audioFile.value = await api.uploadAudio(currentProjectId.value, file)
  processedBlob.value = null
  spectrumComparison.value = null
}

function onTimeUpdate(time) {
  currentTime.value = time
}

function onPlayState(playing) {
  isPlaying.value = playing
}

function onSeek(time) {
  currentTime.value = time
}

function onChainChanged() {
  processedBlob.value = null
}

function onChainSelected(chainId) {
  currentChainId.value = chainId
}

function onParamsTweaked(nodes) {
  lastNodes = nodes
  scheduleRealtimePreview(nodes)
  scheduleAudition(nodes)
}

function scheduleRealtimePreview(nodes) {
  if (previewDebounceTimer) clearTimeout(previewDebounceTimer)
  previewDebounceTimer = setTimeout(() => {
    fetchRealtimeSpectrum(nodes)
  }, 150)
}

function scheduleAudition(nodes) {
  if (auditionDebounceTimer) clearTimeout(auditionDebounceTimer)
  auditionDebounceTimer = setTimeout(() => {
    fetchAudition(nodes)
  }, 300)
}

async function fetchRealtimeSpectrum(nodes) {
  if (!audioFile.value) return

  if (previewAbortController) previewAbortController.abort()
  previewAbortController = new AbortController()

  try {
    const position = playbackRef.value?.getCurrentTime() || currentTime.value || 0
    const data = await api.realtimeSpectrum({
      audio_file_id: audioFile.value.id,
      nodes,
      position,
      duration: 2.0
    })
    spectrumComparison.value = data
  } catch (e) {
    if (e.name !== 'AbortError') console.warn('Spectrum preview failed:', e)
  }
}

async function fetchAudition(nodes) {
  if (!audioFile.value || !playbackRef.value) return
  if (!playbackRef.value.isAutoAuditionEnabled()) return

  try {
    const position = playbackRef.value.getCurrentTime() || currentTime.value || 0
    const blob = await api.realtimeAudition({
      audio_file_id: audioFile.value.id,
      nodes,
      position,
      duration: 2.0
    })
    playbackRef.value.playAuditionBlob(blob)
  } catch (e) {
    console.warn('Audition failed:', e)
  }
}

async function processAudio() {
  if (!audioFile.value || !currentChainId.value) return
  processing.value = true
  try {
    processedBlob.value = await api.processAudio({
      audio_file_id: audioFile.value.id,
      chain_id: currentChainId.value,
      preview: false
    })
  } finally {
    processing.value = false
  }
}

function downloadProcessed() {
  if (!processedBlob.value) return
  const url = URL.createObjectURL(processedBlob.value)
  const a = document.createElement('a')
  a.href = url
  a.download = `processed_${audioFile.value.filename}`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #1a1a2e;
  color: #e0e0e0;
  min-height: 100vh;
}

.app {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid #333;
  margin-bottom: 20px;
}

.app-header h1 {
  font-size: 1.5rem;
  color: #64ffda;
}

.project-controls {
  display: flex;
  gap: 8px;
}

select, button, input {
  font-size: 14px;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #444;
  background: #2a2a4a;
  color: #e0e0e0;
  cursor: pointer;
}

button:hover {
  background: #3a3a5a;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.top-section {
  margin-bottom: 20px;
}

.audio-panel {
  background: #16213e;
  border-radius: 8px;
  padding: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.panel-header h3 {
  color: #64ffda;
}

.upload-btn {
  padding: 8px 16px;
  background: #0f3460;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #1a5276;
}

.upload-btn:hover {
  background: #1a5276;
}

.audio-info {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #888;
  margin-bottom: 8px;
}

.visualization-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.chain-section {
  margin-bottom: 20px;
}

.process-section {
  display: flex;
  gap: 12px;
  justify-content: center;
  padding: 16px;
}

.process-btn {
  background: #e94560;
  border-color: #e94560;
  font-weight: bold;
  padding: 12px 24px;
}

.process-btn:hover {
  background: #ff6b6b;
}

.download-btn {
  background: #0f3460;
  border-color: #1a5276;
  padding: 12px 24px;
}

.empty-state {
  text-align: center;
  padding: 60px;
  color: #666;
}
</style>
