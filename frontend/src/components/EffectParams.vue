<template>
  <div class="effect-params">
    <!-- Gain -->
    <template v-if="effectType === 'gain'">
      <Knob label="增益 (dB)" :value="params.gain_db" :min="-24" :max="24" :step="0.5"
            @update="v => emitUpdate({ gain_db: v })" />
    </template>

    <!-- Compressor -->
    <template v-if="effectType === 'compressor'">
      <div class="params-grid">
        <Knob label="阈值 (dB)" :value="params.threshold_db" :min="-60" :max="0" :step="1"
              @update="v => emitUpdate({ ...params, threshold_db: v })" />
        <Knob label="比率" :value="params.ratio" :min="1" :max="20" :step="0.5"
              @update="v => emitUpdate({ ...params, ratio: v })" />
        <Knob label="启动 (ms)" :value="params.attack_ms" :min="0.1" :max="100" :step="0.5"
              @update="v => emitUpdate({ ...params, attack_ms: v })" />
        <Knob label="释放 (ms)" :value="params.release_ms" :min="10" :max="500" :step="5"
              @update="v => emitUpdate({ ...params, release_ms: v })" />
        <Knob label="补偿增益" :value="params.makeup_gain_db" :min="0" :max="24" :step="0.5"
              @update="v => emitUpdate({ ...params, makeup_gain_db: v })" />
      </div>
    </template>

    <!-- Reverb -->
    <template v-if="effectType === 'reverb'">
      <div class="params-grid">
        <Knob label="房间大小" :value="params.room_size" :min="0.1" :max="1.0" :step="0.05"
              @update="v => emitUpdate({ ...params, room_size: v })" />
        <Knob label="阻尼" :value="params.damping" :min="0" :max="1.0" :step="0.05"
              @update="v => emitUpdate({ ...params, damping: v })" />
        <Knob label="干/湿比" :value="params.wet_dry" :min="0" :max="1.0" :step="0.05"
              @update="v => emitUpdate({ ...params, wet_dry: v })" />
      </div>
    </template>

    <!-- Noise Reduction -->
    <template v-if="effectType === 'noise_reduction'">
      <div class="params-grid">
        <Knob label="降噪量 (dB)" :value="params.noise_reduction_db" :min="0" :max="30" :step="1"
              @update="v => emitUpdate({ ...params, noise_reduction_db: v })" />
        <Knob label="噪声底限 (dB)" :value="params.noise_floor_db" :min="-80" :max="-20" :step="1"
              @update="v => emitUpdate({ ...params, noise_floor_db: v })" />
        <Knob label="平滑" :value="params.smoothing" :min="0" :max="0.99" :step="0.01"
              @update="v => emitUpdate({ ...params, smoothing: v })" />
      </div>
    </template>

    <!-- EQ -->
    <template v-if="effectType === 'eq'">
      <div class="eq-bands">
        <div v-for="(band, i) in params.bands" :key="i" class="eq-band">
          <span class="band-freq">{{ band.freq }}Hz</span>
          <Knob :label="`${band.freq}Hz`" :value="band.gain_db" :min="-12" :max="12" :step="0.5"
                @update="v => updateBand(i, 'gain_db', v)" />
          <Knob label="Q" :value="band.q" :min="0.1" :max="10" :step="0.1"
                @update="v => updateBand(i, 'q', v)" />
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import Knob from './Knob.vue'

const props = defineProps({
  effectType: String,
  params: Object
})

const emit = defineEmits(['update'])

function emitUpdate(newParams) {
  emit('update', newParams)
}

function updateBand(index, key, value) {
  const bands = props.params.bands.map((b, i) =>
    i === index ? { ...b, [key]: value } : { ...b }
  )
  emit('update', { bands })
}
</script>

<style scoped>
.params-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.eq-bands {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.eq-band {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.band-freq {
  font-size: 11px;
  color: #64ffda;
}
</style>
