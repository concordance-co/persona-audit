// Small shared formatting helpers and micro-components (labels, pills, hints).
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { EMOTION_SPECTRUM_CLUSTER_GROUPS, VECTOR_COLORS, titleize } from './helpers'

function RiskPill({ band }) {
  return <span className={`risk-pill risk-${band || 'low'}`}>{band || 'low'}</span>
}

const MODULE_ORDER = ['sycophancy', 'factuality_grounding', 'high_stakes', 'emotion_posture']

function orderModules(modules) {
  const ordered = MODULE_ORDER.filter(module => modules.includes(module))
  const extras = modules.filter(module => !MODULE_ORDER.includes(module)).sort()
  return [...ordered, ...extras]
}

function vectorLabel(value) {
  const labels = {
    assistant_axis: 'Assistant axis',
    sycophantic: 'Sycophantic',
    manipulative: 'Manipulative',
    calm: 'Calm',
    supportive: 'Supportive',
    hostile: 'Hostile',
    assertive: 'Assertive',
    decisive: 'Decisive',
    cautious: 'Cautious',
    conciliatory: 'Conciliatory',
    negative_affect: 'Negative affect',
    empathy: 'Empathy',
    confidence_affect: 'Confident affect',
    exuberant_joy: 'High-arousal positive',
    peaceful_contentment: 'Calm positive',
    compassionate_gratitude: 'Affiliative warmth',
    competitive_pride: 'Pride/status',
    playful_amusement: 'Playful positive',
    depleted_disengagement: 'Disengagement',
    vigilant_suspicion: 'Suspicion',
    hostile_anger: 'Anger/friction',
    fear_and_overwhelm: 'Threat/distress',
    despair_and_shame: 'Shame/despair',
  }
  return labels[value] || titleize(value)
}

function actionLabel(value) {
  const labels = {
    cancel_reservation: 'Cancel reservation',
    update_reservation_flights: 'Update flights',
    update_reservation_baggages: 'Update baggage',
    update_reservation_passengers: 'Update passengers',
    book_reservation: 'Book reservation',
    send_certificate: 'Send certificate',
    transfer_to_human_agents: 'Transfer to human',
    'no final action': 'No final action',
  }
  return labels[value] || titleize(value)
}

function taskGroupLabel(value) {
  return actionLabel(value)
}

function scopeLabel(value) {
  const labels = {
    global: 'All sessions',
    workflow: 'Workflow',
    task_group: 'Task group',
    final_action: 'Final action',
    task_action: 'Task + action',
    repeated_task: 'Repeated task',
    turn_position: 'Turn position bucket',
  }
  return labels[value] || titleize(value)
}

function compactNumber(value) {
  return value == null ? '-' : Number(value).toLocaleString()
}

function compactMetricNumber(value) {
  if (value == null) return '-'
  const number = Number(value)
  if (!Number.isFinite(number)) return '-'
  return new Intl.NumberFormat('en-US', {
    notation: Math.abs(number) >= 100000 ? 'compact' : 'standard',
    maximumFractionDigits: Math.abs(number) >= 1000000 ? 1 : 0,
  }).format(number)
}

function InfoHint({ text }) {
  if (!text) return null
  return (
    <span className="info-hint" tabIndex={0} aria-label={text}>
      i
      <span className="info-hint-popover" role="tooltip">{text}</span>
    </span>
  )
}

function clamp01(value) {
  if (!Number.isFinite(Number(value))) return 0
  return Math.max(0, Math.min(1, Number(value)))
}

function deltaColor(vector) {
  return VECTOR_COLORS[vector] || '#080808'
}

function topDeltasByGroup(rows = [], vectors = []) {
  const vectorSet = new Set(vectors)
  const byGroup = new Map()
  for (const row of rows) {
    if (!vectorSet.has(row.vector)) continue
    const current = byGroup.get(row.group)
    const rowScore = Math.abs(Number(row.standardized_delta ?? row.delta ?? 0))
    const currentScore = current ? Math.abs(Number(current.standardized_delta ?? current.delta ?? 0)) : -1
    if (!current || rowScore > currentScore) byGroup.set(row.group, row)
  }
  return [...byGroup.values()].sort((a, b) => Math.abs(Number(b.standardized_delta ?? b.delta ?? 0)) - Math.abs(Number(a.standardized_delta ?? a.delta ?? 0)))
}

function uniqueTopVectors(...groups) {
  return [...new Set(groups.flat().map(row => row.vector).filter(Boolean))]
}

function zValue(row) {
  const value = Number(row?.standardized_delta ?? row?.z ?? row?.delta ?? 0)
  return Number.isFinite(value) ? value : 0
}

function zColor(value) {
  const z = Math.max(-2.5, Math.min(2.5, Number(value || 0)))
  if (Math.abs(z) < 0.05) return 'rgba(8, 8, 8, 0.04)'
  const alpha = Math.min(0.9, 0.18 + Math.abs(z) / 2.8)
  const rgb = z >= 0 ? '46, 140, 67' : '185, 81, 58'
  return `rgba(${rgb}, ${alpha.toFixed(3)})`
}

function deviationLabel(item = {}) {
  const prefix = Number(item.z ?? 0) < 0 || item.polarity === 'low' ? 'Low' : 'High'
  return `${prefix} ${vectorLabel(item.vector)}`
}

function sessionFocusLink(traceId, context = {}) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(context || {})) {
    if (value != null && value !== '') params.set(key, String(value))
  }
  const query = params.toString()
  return query ? `/sessions/${traceId}?${query}` : `/sessions/${traceId}`
}

function segmentLabel(value, groupKey) {
  return groupKey === 'final_action' ? actionLabel(value) : taskGroupLabel(value)
}

function topVectorsByDelta(rows = [], vectors = [], limit = 5) {
  const vectorSet = new Set(vectors)
  const scores = new Map()
  for (const row of rows) {
    if (!vectorSet.has(row.vector)) continue
    const current = scores.get(row.vector) || 0
    scores.set(row.vector, Math.max(current, Math.abs(zValue(row))))
  }
  return [...scores.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([vector]) => vector)
}

const EMOTION_CLUSTER_GROUP_BY_ID = new Map(EMOTION_SPECTRUM_CLUSTER_GROUPS.map(group => [group.id, group]))

function emotionClusterDetail(row) {
  if (row?.family !== 'emotion_cluster') return null
  const cluster = EMOTION_CLUSTER_GROUP_BY_ID.get(row.vector)
  const members = cluster?.members || []
  return {
    label: cluster?.label || vectorLabel(row.vector),
    members,
    summary: members.length
      ? `${cluster?.label || vectorLabel(row.vector)} uses ${members.length} emotion concepts: ${members.join(', ')}`
      : `${cluster?.label || vectorLabel(row.vector)} is an emotion-cluster baseline.`,
  }
}

function rowsByGroupAndVector(rows = []) {
  const byGroup = new Map()
  for (const row of rows) {
    const group = row.group || 'unknown'
    if (!byGroup.has(group)) byGroup.set(group, new Map())
    byGroup.get(group).set(row.vector, row)
  }
  return byGroup
}

export { EMOTION_CLUSTER_GROUP_BY_ID, InfoHint, MODULE_ORDER, RiskPill, actionLabel, clamp01, compactMetricNumber, compactNumber, deltaColor, deviationLabel, emotionClusterDetail, orderModules, rowsByGroupAndVector, scopeLabel, segmentLabel, sessionFocusLink, taskGroupLabel, topDeltasByGroup, topVectorsByDelta, uniqueTopVectors, vectorLabel, zColor, zValue }
