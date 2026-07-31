const API_BASE = import.meta.env.VITE_API_URL || ''
const STATIC_DEMO = import.meta.env.MODE === 'hosted'
const STATIC_ROOT = '/demo-data'
const STATIC_PROVIDERS = new Set(['persona_demo', 'tau2'])

async function fetchJSON(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, options)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function fetchStaticJSON(path, options = {}) {
  const res = await fetch(`${STATIC_ROOT}/${path}`, options)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

function staticProvider(provider) {
  const selected = provider || 'persona_demo'
  if (!STATIC_PROVIDERS.has(selected)) throw new Error(`Static demo provider not found: ${selected}`)
  return selected
}

function staticFileKey(value) {
  return encodeURIComponent(String(value)).replaceAll('%', '_')
}

function withProvider(path, provider) {
  if (!provider) return path
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}provider=${encodeURIComponent(provider)}`
}

export function getProviders() {
  return STATIC_DEMO ? fetchStaticJSON('providers.json') : fetchJSON('/api/providers')
}

export function getOverview() {
  return STATIC_DEMO ? fetchStaticJSON('overview.json') : fetchJSON('/api/overview')
}

export function getAssets() {
  return STATIC_DEMO ? fetchStaticJSON('assets.json') : fetchJSON('/api/assets')
}

export function getEmotions() {
  return STATIC_DEMO ? fetchStaticJSON('emotions.json') : fetchJSON('/api/emotions')
}

export function getHighStakesReports() {
  return STATIC_DEMO ? fetchStaticJSON('high-stakes-reports.json') : fetchJSON('/api/high-stakes/reports')
}

export function getAuditReport(provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/report.json`)
    : fetchJSON(withProvider('/api/audit/report', provider))
}

export function getProductAnalytics(provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/product-analytics.json`)
    : fetchJSON(withProvider('/api/audit/product-analytics', provider))
}

export function getAuditSessions(params = {}, provider) {
  if (STATIC_DEMO) {
    return fetchStaticJSON(`${staticProvider(provider)}/sessions.json`).then(rows => rows.filter(row => {
      const risk = row.risk || row.risk_level || row.risk_tier
      return (!params.domain || row.domain === params.domain) && (!params.risk || risk === params.risk)
    }))
  }
  const search = new URLSearchParams()
  if (params.domain) search.set('domain', params.domain)
  if (params.risk) search.set('risk', params.risk)
  if (provider) search.set('provider', provider)
  const suffix = search.toString() ? `?${search.toString()}` : ''
  return fetchJSON(`/api/audit/sessions${suffix}`)
}

export function getAuditSession(traceId, provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/sessions/${staticFileKey(traceId)}.json`)
    : fetchJSON(withProvider(`/api/audit/sessions/${encodeURIComponent(traceId)}`, provider))
}

export function getAuditUsers(provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/users.json`)
    : fetchJSON(withProvider('/api/audit/users', provider))
}

export function getAuditUser(userId, provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/users/${staticFileKey(userId)}.json`)
    : fetchJSON(withProvider(`/api/audit/users/${encodeURIComponent(userId)}`, provider))
}

export function getScoreSpaces(provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/score-spaces.json`)
    : fetchJSON(withProvider('/api/audit/score-spaces', provider))
}

export function getCharacter(provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/character.json`)
    : fetchJSON(withProvider('/api/audit/character', provider))
}

export function getCharacterTrait(coordinate, provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/character/${staticFileKey(coordinate)}.json`)
    : fetchJSON(withProvider(`/api/audit/character/${encodeURIComponent(coordinate)}`, provider))
}

export function getTail(provider) {
  return STATIC_DEMO
    ? fetchStaticJSON(`${staticProvider(provider)}/tail.json`)
    : fetchJSON(withProvider('/api/audit/tail', provider), { cache: 'no-store' })
}
