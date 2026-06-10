<template>
  <div class="chain-editor">
    <div class="chain-header">
      <h3>效果链</h3>
      <div class="chain-controls">
        <select v-model="selectedChainId" @change="loadChain">
          <option :value="null" disabled>选择效果链</option>
          <option v-for="c in chains" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <button @click="createChain">新建</button>
        <button v-if="selectedChainId" @click="deleteCurrentChain" class="delete-btn">删除</button>
      </div>
    </div>

    <div v-if="chain" class="chain-content">
      <div class="add-effect">
        <select v-model="newEffectType">
          <option :value="null" disabled>添加效果...</option>
          <option v-for="(info, key) in effectTypes" :key="key" :value="key">
            {{ info.name }}
          </option>
        </select>
        <button @click="addEffect" :disabled="!newEffectType">添加</button>
      </div>

      <div class="nodes-list"
           @dragover.prevent
           @drop="onDrop">
        <div
          v-for="(node, index) in chain.nodes"
          :key="node.id"
          class="effect-node"
          :class="{ disabled: !node.enabled, dragging: dragIndex === index }"
          draggable="true"
          @dragstart="onDragStart(index, $event)"
          @dragover.prevent="onDragOver(index)"
          @dragend="onDragEnd"
        >
          <div class="node-header">
            <span class="drag-handle">⠿</span>
            <span class="node-name">{{ getEffectName(node.effect_type) }}</span>
            <label class="toggle">
              <input type="checkbox" :checked="node.enabled" @change="toggleNode(node)" />
              <span class="toggle-slider"></span>
            </label>
            <button class="node-delete" @click="removeNode(node)">×</button>
          </div>
          <div class="node-params" v-if="node.enabled">
            <EffectParams
              :effect-type="node.effect_type"
              :params="node.params"
              @update="(p) => updateParams(node, p)"
            />
          </div>
        </div>
      </div>

      <div v-if="chain.nodes.length === 0" class="empty-chain">
        拖拽添加效果节点到链中
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { api } from '../api.js'
import EffectParams from './EffectParams.vue'

const props = defineProps({
  projectId: Number
})

const emit = defineEmits(['chain-changed', 'chain-selected', 'params-tweaked'])

const chains = ref([])
const chain = ref(null)
const selectedChainId = ref(null)
const effectTypes = ref({})
const newEffectType = ref(null)
const dragIndex = ref(null)
const dragOverIndex = ref(null)

onMounted(async () => {
  effectTypes.value = await api.getEffectTypes()
  await loadChains()
})

watch(() => props.projectId, loadChains)

async function loadChains() {
  if (!props.projectId) return
  chains.value = await api.listChains(props.projectId)
  if (chains.value.length > 0 && !selectedChainId.value) {
    selectedChainId.value = chains.value[0].id
    await loadChain()
  }
}

async function loadChain() {
  if (!selectedChainId.value) return
  chain.value = await api.getChain(selectedChainId.value)
  emit('chain-selected', selectedChainId.value)
}

async function createChain() {
  const name = prompt('效果链名称:')
  if (!name) return
  const newChain = await api.createChain(name, props.projectId)
  chains.value.push(newChain)
  selectedChainId.value = newChain.id
  await loadChain()
}

async function deleteCurrentChain() {
  if (!confirm('确定删除此效果链?')) return
  await api.deleteChain(selectedChainId.value)
  chains.value = chains.value.filter(c => c.id !== selectedChainId.value)
  selectedChainId.value = null
  chain.value = null
  emit('chain-selected', null)
}

async function addEffect() {
  if (!newEffectType.value || !selectedChainId.value) return
  const position = chain.value.nodes.length
  const defaultParams = effectTypes.value[newEffectType.value].default_params
  await api.addNode(selectedChainId.value, {
    effect_type: newEffectType.value,
    position,
    enabled: true,
    params: defaultParams
  })
  await loadChain()
  newEffectType.value = null
  emit('chain-changed')
  emitNodeSnapshot()
}

async function toggleNode(node) {
  await api.updateNode(node.id, { enabled: !node.enabled })
  node.enabled = !node.enabled
  emit('chain-changed')
  emitNodeSnapshot()
}

async function removeNode(node) {
  await api.deleteNode(node.id)
  await loadChain()
  emit('chain-changed')
  emitNodeSnapshot()
}

async function updateParams(node, params) {
  node.params = params
  // Fire real-time preview immediately (debounce happens in parent)
  emitNodeSnapshot()
  // Persist to DB in background (don't await before preview)
  api.updateNode(node.id, { params })
}

function emitNodeSnapshot() {
  if (!chain.value) return
  const snapshot = chain.value.nodes.map(n => ({
    effect_type: n.effect_type,
    enabled: n.enabled,
    params: n.params
  }))
  emit('params-tweaked', snapshot)
}

function getEffectName(type) {
  return effectTypes.value[type]?.name || type
}

function onDragStart(index, event) {
  dragIndex.value = index
  event.dataTransfer.effectAllowed = 'move'
}

function onDragOver(index) {
  dragOverIndex.value = index
}

async function onDrop() {
  if (dragIndex.value === null || dragOverIndex.value === null) return
  if (dragIndex.value === dragOverIndex.value) return

  const nodes = [...chain.value.nodes]
  const [moved] = nodes.splice(dragIndex.value, 1)
  nodes.splice(dragOverIndex.value, 0, moved)

  const nodeIds = nodes.map(n => n.id)
  await api.reorderNodes(selectedChainId.value, nodeIds)
  await loadChain()
  emit('chain-changed')
  emitNodeSnapshot()
}

function onDragEnd() {
  dragIndex.value = null
  dragOverIndex.value = null
}
</script>

<style scoped>
.chain-editor {
  background: #16213e;
  border-radius: 8px;
  padding: 16px;
}

.chain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.chain-header h3 {
  color: #64ffda;
}

.chain-controls {
  display: flex;
  gap: 8px;
}

.add-effect {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.nodes-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.effect-node {
  background: #1a2744;
  border: 1px solid #2a4a7a;
  border-radius: 8px;
  padding: 12px;
  transition: all 0.2s;
}

.effect-node.disabled {
  opacity: 0.5;
  border-color: #333;
}

.effect-node.dragging {
  opacity: 0.4;
  transform: scale(0.98);
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drag-handle {
  cursor: grab;
  color: #666;
  font-size: 16px;
  user-select: none;
}

.node-name {
  flex: 1;
  font-weight: 500;
  color: #8bb4ff;
}

.toggle {
  position: relative;
  width: 36px;
  height: 20px;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: #333;
  border-radius: 20px;
  cursor: pointer;
  transition: 0.2s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 2px;
  bottom: 2px;
  background: #666;
  border-radius: 50%;
  transition: 0.2s;
}

.toggle input:checked + .toggle-slider {
  background: #0f3460;
}

.toggle input:checked + .toggle-slider::before {
  transform: translateX(16px);
  background: #64ffda;
}

.node-delete {
  background: transparent;
  border: none;
  color: #e94560;
  font-size: 18px;
  cursor: pointer;
  padding: 2px 6px;
}

.node-params {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #2a3a5a;
}

.empty-chain {
  text-align: center;
  color: #555;
  padding: 24px;
}

.delete-btn {
  background: #e94560;
  border-color: #e94560;
}
</style>
