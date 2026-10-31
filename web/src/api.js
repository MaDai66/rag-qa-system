const BASE = '/api/v1'

async function request(path, { method = 'GET', body, query, form } = {}) {
  let url = BASE + path
  if (query) {
    const qs = new URLSearchParams(
      Object.entries(query).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString()
    if (qs) url += '?' + qs
  }

  const init = { method, headers: {} }
  if (form) {
    init.body = form
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(url, init)
  } catch {
    throw new Error('连不上后端，先确认 python server.py 已经跑起来')
  }
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)

  const payload = await res.json()
  // 后端的错误也走 HTTP 200，靠 status 字段区分
  if (payload.status !== 'success') throw new Error(payload.message || '请求失败')
  return payload.data
}

export const api = {
  listUsers: () => request('/users/'),

  listCollections: () => request('/collections/'),
  createCollection: (name) => request('/collections/', { method: 'POST', body: { name } }),
  deleteCollection: (uuid) => request(`/collections/${uuid}`, { method: 'DELETE' }),

  listFiles: (collectionId) => request('/files/', { query: { collection_id: collectionId } }),
  uploadFile: (file, collectionId) => {
    const fd = new FormData()
    fd.append('file', file)
    if (collectionId) fd.append('collection_id', collectionId)
    return request('/files/', { method: 'POST', form: fd })
  },
  deleteFile: (fileId) => request('/files/', { method: 'DELETE', query: { file_id: fileId } }),

  listChunks: (fileId) => request(`/chunks/file/${fileId}`),
  getChunk: (chunkId) => request(`/chunks/chunk/${chunkId}`),

  getDict: (key) => request(`/dicts/${key}`),
  // 后端收的是裸数组 [{"key":..., "value":...}]，不是包在对象里
  saveDicts: (items) => request('/dicts/batch-upsert', { method: 'POST', body: items }),

  chat: (userId, message, collectionId) =>
    request('/chat/', {
      method: 'POST',
      body: { user_id: userId, message, collection_id: collectionId || '' },
    }),
  history: (userId) => request('/chat/history', { method: 'POST', query: { user_id: userId } }),
  clearHistory: (userId) =>
    request('/chat/clear-history', { method: 'POST', query: { user_id: userId } }),
}
