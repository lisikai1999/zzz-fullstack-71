const API_BASE = '/api'

export async function fetchJSON(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function uploadFile(url, formData) {
  const res = await fetch(`${API_BASE}${url}`, {
    method: 'POST',
    body: formData
  })
  if (!res.ok) throw new Error(`Upload error: ${res.status}`)
  return res.json()
}

export async function fetchBlob(url, options = {}) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.blob()
}

export const api = {
  listProjects: () => fetchJSON('/projects'),
  createProject: (name) => fetchJSON('/projects', { method: 'POST', body: JSON.stringify({ name }) }),
  deleteProject: (id) => fetchJSON(`/projects/${id}`, { method: 'DELETE' }),

  uploadAudio: (projectId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return uploadFile(`/audio/upload?project_id=${projectId}`, fd)
  },
  getWaveform: (fileId, start = 0, end = -1, points = 2000) =>
    fetchJSON(`/audio/${fileId}/waveform?start=${start}&end=${end}&points=${points}`),
  getSpectrum: (fileId, position = 0) =>
    fetchJSON(`/audio/${fileId}/spectrum?position=${position}`),
  getSpectrogram: (fileId, start = 0, end = -1) =>
    fetchJSON(`/audio/${fileId}/spectrogram?start=${start}&end=${end}`),
  downloadAudio: (fileId) => fetchBlob(`/audio/${fileId}/download`),

  getEffectTypes: () => fetchJSON('/effects/types'),

  listChains: (projectId) => fetchJSON(`/projects/${projectId}/chains`),
  createChain: (name, projectId) =>
    fetchJSON('/chains', { method: 'POST', body: JSON.stringify({ name, project_id: projectId }) }),
  getChain: (chainId) => fetchJSON(`/chains/${chainId}`),
  deleteChain: (chainId) => fetchJSON(`/chains/${chainId}`, { method: 'DELETE' }),

  addNode: (chainId, node) =>
    fetchJSON(`/chains/${chainId}/nodes`, { method: 'POST', body: JSON.stringify(node) }),
  updateNode: (nodeId, update) =>
    fetchJSON(`/nodes/${nodeId}`, { method: 'PUT', body: JSON.stringify(update) }),
  deleteNode: (nodeId) => fetchJSON(`/nodes/${nodeId}`, { method: 'DELETE' }),
  reorderNodes: (chainId, nodeIds) =>
    fetchJSON(`/chains/${chainId}/reorder`, { method: 'PUT', body: JSON.stringify(nodeIds) }),

  processAudio: (request) => fetchBlob('/process', { method: 'POST', body: JSON.stringify(request) }),
  previewSpectrum: (request) =>
    fetchJSON('/process/preview-spectrum', { method: 'POST', body: JSON.stringify(request) }),
  realtimeSpectrum: (request) =>
    fetchJSON('/process/realtime-spectrum', { method: 'POST', body: JSON.stringify(request) }),
  realtimeAudition: (request) =>
    fetchBlob('/process/realtime-audition', { method: 'POST', body: JSON.stringify(request) })
}
