const API_BASE = import.meta.env.VITE_API_URL || ''

async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

function withProvider(path, provider) {
  if (!provider) return path
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}provider=${encodeURIComponent(provider)}`
}

export function getOverview() {
  return fetchJSON('/api/overview')
}

export function getAssets() {
  return fetchJSON('/api/assets')
}

export function getEmotions() {
  return fetchJSON('/api/emotions')
}

export function getHighStakesReports() {
  return fetchJSON('/api/high-stakes/reports')
}

export function getAuditReport(provider) {
  return fetchJSON(withProvider('/api/audit/report', provider))
}

export function getProductAnalytics(provider) {
  return fetchJSON(withProvider('/api/audit/product-analytics', provider))
}

export function getAuditSessions(params = {}, provider) {
  const search = new URLSearchParams()
  if (params.domain) search.set('domain', params.domain)
  if (params.risk) search.set('risk', params.risk)
  if (provider) search.set('provider', provider)
  const suffix = search.toString() ? `?${search.toString()}` : ''
  return fetchJSON(`/api/audit/sessions${suffix}`)
}

export function getAuditSession(traceId, provider) {
  return fetchJSON(withProvider(`/api/audit/sessions/${encodeURIComponent(traceId)}`, provider))
}

export function getAuditUsers(provider) {
  return fetchJSON(withProvider('/api/audit/users', provider))
}

export function getAuditUser(userId, provider) {
  return fetchJSON(withProvider(`/api/audit/users/${encodeURIComponent(userId)}`, provider))
}

export function getScoreSpaces(provider) {
  return fetchJSON(withProvider('/api/audit/score-spaces', provider))
}

export function getHermesOverview() {
  return fetchJSON('/api/hermes/overview')
}

export function getCharacter(provider) {
  return fetchJSON(withProvider('/api/audit/character', provider))
}

export function getCharacterTrait(coordinate, provider) {
  return fetchJSON(withProvider(`/api/audit/character/${encodeURIComponent(coordinate)}`, provider))
}

export function getTail(provider) {
  return fetchJSON(withProvider('/api/audit/tail', provider))
}
