// frontend/src/utils/api.js
// Central API client. All fetch calls go through here.
// In dev, Vite proxies /api → http://localhost:8000
// In prod, VITE_API_BASE env var points to Render backend URL

const BASE = import.meta.env.VITE_API_BASE || '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post(path) {
  const res = await fetch(`${BASE}${path}`, { method: 'POST' })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  health:       () => get('/health'),
  syncStatus:   () => get('/sync/status'),
  syncLogs:     (limit = 20) => get(`/sync/logs?limit=${limit}`),
  triggerSync:  () => post('/sync/trigger'),
  headcount:    () => get('/analytics/headcount'),
  attrition:    () => get('/analytics/attrition'),
  diversity:    () => get('/analytics/diversity'),
  tenure:       () => get('/analytics/tenure'),
  dataQuality:  () => get('/analytics/data-quality'),
}
