import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Route, BrowserRouter as Router, Routes, useLocation, useParams } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import {
  getAuditReport,
  getAuditSession,
  getAuditSessions,
  getAuditUser,
  getAuditUsers,
  getCharacter,
  getCharacterTrait,
  getTail,
  getEmotions,
  getHighStakesReports,
  getHermesOverview,
  getProductAnalytics,
  getScoreSpaces,
} from '../api'
import { useAsyncResource } from '../hooks/useAsyncResource'
import { Shell, providerPath, useProviderSelection } from './behavior/layout'
import {
  SIGNAL_COLORS,
  FALLBACK_SIGNAL_COLOR,
  CHART_GRID_COLOR,
  CHART_ZERO_COLOR,
  VECTOR_COLORS,
  PERSONA_VECTOR_KEYS,
  EMOTION_VECTOR_KEYS,
  POSITIVE_COLOR,
  NEGATIVE_COLOR,
  HIGHLIGHT_COLOR,
  EMOTION_SPECTRUM_X_AXIS_STEP,
  EMOTION_SPECTRUM_CLUSTER_GROUPS,
  EMOTION_CLUSTER_BY_CONCEPT,
  fmt,
  pct,
  pct1,
  titleize,
  coordinateTitle,
  emotionConceptKey,
  smoothLinePath,
  familyTitle,
  evalLabelTitle,
  axisIdForCoordinate,
  topRows,
  average,
  groupByValue,
  chartRows,
  mean,
  buildTurnAxisRows,
  buildCoordinateTrajectoryRows,
  trajectoryCoordinateOptions,
  defaultTrajectoryCoordinates,
  buildProjectionTailThresholds,
  buildEmotionSpectrumData,
  buildSessionProjectionDistributions,
} from './behavior/helpers'

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

function PersonaMetric({ label, value, detail, compact = false }) {
  return (
    <div className="persona-metric">
      <div className="persona-metric-label">
        <span>{label}</span>
        <InfoHint text={detail} />
      </div>
      <div className={`persona-metric-value${compact ? ' compact-value' : ''}`}>{value}</div>
    </div>
  )
}

function TraceOrderSeriesChart({ rows, vectors }) {
  const defaultVectors = ['assertive', 'decisive', 'cautious', 'conciliatory']
  const availableVectors = vectors?.length ? vectors : defaultVectors
  const [selectedVectors, setSelectedVectors] = useState(defaultVectors.filter(vector => availableVectors.includes(vector)))
  const chartRows = rows.map(row => ({
    ...row,
    displayLabel: `${row.label} ${row.mode}`,
  }))

  function toggleVector(vector) {
    setSelectedVectors(current => (
      current.includes(vector)
        ? current.filter(item => item !== vector)
        : [...current, vector]
    ))
  }

  return (
    <div className="card full-width-card">
      <div className="card-title">Deployment Preview Storyboard</div>
      <p className="muted-copy compact">Example-only blocks sorted by Tau2 task labels. This previews production monitoring grammar; block boundaries are sorting artifacts, not observed drift.</p>
      <div className="vector-toggle-row">
        {availableVectors.map(vector => (
          <label key={vector} className="vector-toggle">
            <input type="checkbox" checked={selectedVectors.includes(vector)} onChange={() => toggleVector(vector)} />
            <span>{vectorLabel(vector)}</span>
          </label>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={chartRows}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="displayLabel" tick={{ fontSize: 10 }} interval={0} angle={-18} textAnchor="end" height={76} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(value, name) => [fmt(value), vectorLabel(name)]} labelFormatter={(label, items) => {
            const row = items?.[0]?.payload
            return row ? `${row.label}: ${row.mode} segment, source n=${row.source_n}` : label
          }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {selectedVectors.map(vector => (
            <Line
              key={`simulated-${vector}`}
              type="monotone"
              dataKey={vector}
              connectNulls
              stroke={deltaColor(vector)}
              strokeWidth={2}
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function OutlierTraceChart({ trace, provider }) {
  const rows = trace.rows || []
  const trackedVectorLabel = deviationLabel({
    vector: trace.tracked_vector,
    z: trace.tracked_trace_z,
    polarity: trace.tracked_polarity,
  })
  const topDeviation = rows
    .map(row => row.top_deviation)
    .filter(Boolean)
    .sort((a, b) => Math.abs(Number(b.z || 0)) - Math.abs(Number(a.z || 0)))[0]
  const traceContext = {
    coordinate: trace.tracked_coordinate,
    vector: trace.tracked_vector,
    family: trace.tracked_coordinate?.startsWith('emotion_cluster__') ? 'emotion_cluster' : undefined,
    polarity: trace.tracked_polarity,
    baseline_scope: trace.baseline_scope || 'workflow',
    source: 'overview_preview',
  }

  return (
    <div className="card outlier-trace-card">
      <div className="card-heading-row">
        <div>
          <div className="card-title"><Link to={providerPath(sessionFocusLink(trace.trace_id, traceContext), provider)}>{trace.trace_id}</Link></div>
          <div className="stat-label">{actionLabel(trace.final_action)} · reward {fmt(trace.reward)} · tracked {trackedVectorLabel}</div>
        </div>
        <div className="outlier-score-pill">{fmt(trace.trace_outlier_score)}</div>
      </div>
      <p className="muted-copy compact">
        Turn-level signed z for the tracked signal. Dotted line is the comparable length/position baseline.
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="turn_index" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            formatter={(value, name) => [fmt(value), name === 'tracked_z' ? trackedVectorLabel : 'Aggregate outlier score']}
            labelFormatter={label => `Turn ${label}`}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={0} name="Comparable baseline" stroke="#080808" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="tracked_z" name={trackedVectorLabel} stroke="#B9513A" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      {topDeviation && (
        <div className="stat-label">Largest turn deviation: {deviationLabel(topDeviation)} z={fmt(topDeviation.z)}</div>
      )}
    </div>
  )
}

function SystemStateCards({ data, reward, scoreRowCount, providerInfo = {} }) {
  const families = data.score_source?.families || []
  const familyCount = families.length
  const persona = data.persona_overview || {}
  const cohortLabel = providerInfo.cohort_plural_label || 'cohorts'
  const actionLabelText = providerInfo.action_label || 'Action'
  return (
    <div className="stats-grid enterprise-stats">
      <PersonaMetric label="Traces" value={compactMetricNumber(reward.trace_count || data.trace_count)} detail={`${compactNumber(data.user_count)} ${cohortLabel.toLowerCase()}`} />
      <PersonaMetric label="Turns" value={compactMetricNumber(reward.assistant_turn_count || 1268)} detail="Assistant turns with turn-level scores." />
      <PersonaMetric label="Score Rows" value={compactMetricNumber(scoreRowCount)} detail={`${familyCount} score families loaded.`} />
      <PersonaMetric label="Traits" value={compactMetricNumber((persona.persona_vectors || PERSONA_VECTOR_KEYS).length)} detail="Persona posture traits, separate from emotion clusters." />
      <PersonaMetric label="Emotions" value={compactMetricNumber((persona.emotion_cluster_vectors || EMOTION_VECTOR_KEYS).length)} detail="Emotion cluster vectors used for the default emotion layer." />
      <PersonaMetric label={`Low-n ${actionLabelText}`} value={compactMetricNumber(persona.low_n_task_action_count || 0)} detail="Segment/action cells below n=10 stay drilldown-only." />
    </div>
  )
}

function BaselineHeatmap({ title, badge, description, legend = [], rows = [], vectors = [], groupKey = 'workflow', groupLabel = value => value, groupHeader = 'Segment', expanded = false, onExpanded }) {
  const visibleVectors = expanded ? vectors : topVectorsByDelta(rows, vectors, 5)
  const vectorSet = new Set(visibleVectors)
  const byGroup = rowsByGroupAndVector(rows.filter(row => vectorSet.has(row.vector)))
  const groups = [...byGroup.keys()].sort((a, b) => {
    const scoreA = Math.max(...[...byGroup.get(a).values()].map(row => Math.abs(zValue(row))), 0)
    const scoreB = Math.max(...[...byGroup.get(b).values()].map(row => Math.abs(zValue(row))), 0)
    return scoreB - scoreA
  })
  if (!visibleVectors.length || !groups.length) return null
  return (
    <div className="card enterprise-panel">
      <div className="card-heading-row">
        <div>
          <div className="card-title-row">
            <div className="card-title">{title}</div>
            {badge && <span className="surface-badge">{badge}</span>}
          </div>
          {description && <p className="muted-copy compact">{description}</p>}
          {legend.length > 0 && (
            <div className="heatmap-legend">
              {legend.map(item => <span key={item}>{item}</span>)}
            </div>
          )}
        </div>
        {onExpanded && vectors.length > visibleVectors.length && (
          <button type="button" className="small-button" onClick={() => onExpanded(!expanded)}>
            {expanded ? 'Top 5' : `Show all ${vectors.length}`}
          </button>
        )}
      </div>
      <div className="baseline-heatmap" style={{ gridTemplateColumns: `minmax(190px, 1.25fr) repeat(${visibleVectors.length}, minmax(92px, 1fr))` }}>
        <div className="heatmap-label row-label">{groupHeader}</div>
        {visibleVectors.map(vector => <div key={vector} className="heatmap-label">{vectorLabel(vector)}</div>)}
        {groups.map(group => (
          <Fragment key={group}>
            <div className="heatmap-label row-label">
              {groupLabel(group)}
              <small>n={byGroup.get(group).values().next().value?.n ?? '-'}</small>
            </div>
            {visibleVectors.map(vector => {
              const row = byGroup.get(group).get(vector)
              const z = zValue(row)
              return (
                <div
                  key={`${group}-${vector}`}
                  className="baseline-cell"
                  style={{ background: zColor(z), color: Math.abs(z) > 1.25 ? '#fff8f4' : 'var(--corpus-text)' }}
                  title={row ? `${vectorLabel(vector)} ${groupLabel(group)}: z=${fmt(z)}, mean=${fmt(row.mean)}, raw=${fmt(row.raw_mean)}, n=${row.n}` : ''}
                >
                  {row ? fmt(z) : '-'}
                </div>
              )
            })}
          </Fragment>
        ))}
      </div>
    </div>
  )
}

function GlobalBaselineStrip({ title, description, rows = [], vectors = [] }) {
  const vectorSet = new Set(vectors)
  const visibleRows = rows
    .filter(row => vectorSet.has(row.vector))
    .sort((a, b) => vectors.indexOf(a.vector) - vectors.indexOf(b.vector))
  if (!visibleRows.length) return null
  return (
    <div className="card global-baseline-strip">
      <div className="card-heading-row compact-heading">
        <div className="card-title">{title}</div>
        <InfoHint text={description || 'Raw/oriented global means. Heatmap cells below are z-deltas from these baselines.'} />
      </div>
      {description && <p className="muted-copy compact">{description}</p>}
      <div className="baseline-strip-grid">
        {visibleRows.map(row => {
          const clusterDetail = emotionClusterDetail(row)
          return (
            <div
              key={row.vector}
              className={`baseline-strip-item${clusterDetail ? ' has-popover' : ''}`}
              data-vector={row.vector}
              aria-label={clusterDetail?.summary}
              tabIndex={clusterDetail ? 0 : undefined}
            >
              <span>{vectorLabel(row.vector)}</span>
              <strong>{fmt(row.basis_mean)}</strong>
              <small>sd {fmt(row.basis_sd)} · n={compactNumber(row.n)}</small>
              {clusterDetail && (
                <div className="baseline-popover" role="tooltip">
                  <div className="baseline-popover-title">{clusterDetail.label}</div>
                  <div className="baseline-popover-subtitle">{clusterDetail.members.length} scored emotion concepts</div>
                  <div className="baseline-popover-list">
                    {clusterDetail.members.map(member => <span key={member}>{member}</span>)}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function TraitDetailChart({ title, readGuide, rows = [], vector, groupLabel = value => value }) {
  const vectorRows = rows
    .filter(row => row.vector === vector)
    .sort((a, b) => Math.abs(zValue(b)) - Math.abs(zValue(a)))
    .map(row => ({
      ...row,
      displayGroup: groupLabel(row.group),
      z_delta: zValue(row),
    }))
  const chartRows = vectorRows
  if (!chartRows.length) return null
  return (
    <div className="trait-detail-chart">
      <div className="card-title">{title}</div>
      <div className="chart-read-guide">
        {readGuide || 'Bars show z-score vs global baseline. 0 is typical; positive is higher than baseline; negative is lower.'}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartRows} margin={{ top: 8, right: 12, left: 0, bottom: 68 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="displayGroup" tick={{ fontSize: 10 }} interval={0} angle={-26} textAnchor="end" height={82} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            formatter={(value, name) => [fmt(value), name === 'z_delta' ? 'z-delta' : name]}
            labelFormatter={(label, items) => {
              const row = items?.[0]?.payload
              return row ? `${label}: n=${row.n}, mean=${fmt(row.mean)}, global=${fmt(row.global_mean)}, raw=${fmt(row.raw_mean)}` : label
            }}
          />
          <ReferenceLine y={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
          <Bar dataKey="z_delta" name="z-delta" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {chartRows.map(row => (
              <Cell key={`${row.displayGroup}-${vector}`} fill={zValue(row) >= 0 ? POSITIVE_COLOR : HIGHLIGHT_COLOR} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function InvestigationQueue({ outliers = [], family = 'all', onFamily, provider }) {
  const counts = {
    all: outliers.length,
    persona: outliers.filter(row => row.family === 'persona').length,
    emotion_cluster: outliers.filter(row => row.family === 'emotion_cluster').length,
  }
  const filtered = outliers.filter(row => {
    if (family === 'all') return true
    return row.family === family
  })
  return (
    <div className="card enterprise-panel">
      <div className="card-heading-row">
        <div>
          <div className="card-title">Investigation Queue</div>
          <p className="muted-copy compact">Primary z is the signed deviation for the named signal; Aggregate is RMS deviation across overview signals within that workflow. Default rank is absolute aggregate z.</p>
        </div>
        <div className="compact-toggle">
          {[
            ['persona', `Persona ${counts.persona}`],
            ['emotion_cluster', `Emotion ${counts.emotion_cluster}`],
            ['all', `All ${counts.all}`],
          ].map(([id, label]) => (
            <button key={id} type="button" className={family === id ? 'active' : ''} onClick={() => onFamily(id)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Trace</th>
            <th>Segment</th>
            <th>Family</th>
            <th>Primary signal</th>
            <th className="num">Primary z</th>
            <th className="num">Aggregate</th>
            <th>Next step</th>
          </tr>
        </thead>
        <tbody>
          {filtered.slice(0, 10).map(row => {
            const top = row.top_z?.[0] || {}
            const context = {
              coordinate: top.coordinate,
              vector: top.vector || row.selected_vector,
              family: row.family,
              polarity: top.polarity,
              baseline_scope: row.baseline_scope || 'workflow',
              source: 'overview_queue',
            }
            return (
              <tr key={row.trace_id}>
                <td><Link to={providerPath(sessionFocusLink(row.trace_id, context), provider)}>{row.trace_id}</Link></td>
                <td>{taskGroupLabel(row.workflow)} / {actionLabel(row.final_action)}</td>
                <td>{row.family === 'emotion_cluster' ? 'Emotion' : 'Persona'}</td>
                <td>{deviationLabel(top)}</td>
                <td className="num">{fmt(top.z)}</td>
                <td className="num">{fmt(row.outlier_score)}</td>
                <td><Link to={providerPath(sessionFocusLink(row.trace_id, context), provider)}>Inspect signal</Link></td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function cohortSummaryRows(cohorts = [], sessions = []) {
  const sessionsByCohort = groupByValue(sessions, 'user_id')
  return cohorts.map(cohort => {
    const cohortSessions = sessionsByCohort.get(cohort.user_id) || []
    const passRate = average(cohortSessions.map(session => Number(session.reward || 0)))
    const avgTurns = average(cohortSessions.map(session => session.turn_count))
    return {
      ...cohort,
      pass_rate: passRate,
      avg_turns: avgTurns,
      session_count: cohort.session_count ?? cohortSessions.length,
      high_risk_rate: cohort.session_count ? Number(cohort.high_risk_sessions || 0) / Number(cohort.session_count) : null,
    }
  }).sort((a, b) => Number(b.high_risk_rate || 0) - Number(a.high_risk_rate || 0) || Number(a.pass_rate || 0) - Number(b.pass_rate || 0))
}

function sessionSetStats(sessions = []) {
  return {
    n: sessions.length,
    passRate: average(sessions.map(session => Number(session.reward || 0))),
    avgTurns: average(sessions.map(session => session.turn_count)),
    highRisk: sessions.filter(session => session.risk_band === 'high').length,
    flags: sessions.reduce((sum, session) => sum + Number(session.flag_count || 0), 0),
  }
}

function CohortExplorerPanel({ cohorts = [], sessions = [], selected, onSelected, providerInfo = {} }) {
  const rows = cohortSummaryRows(cohorts, sessions)
  const features = providerInfo.features || {}
  const cohortLabel = providerInfo.cohort_label || 'Cohort'
  const provider = providerInfo.id || 'tau2'
  const selectedSessions = selected === 'all' ? sessions : sessions.filter(session => session.user_id === selected)
  const selectedStats = sessionSetStats(selectedSessions)
  const allStats = sessionSetStats(sessions)
  return (
    <div className="card enterprise-panel">
      <div className="card-heading-row">
        <div>
          <div className="card-title">Cohort Explorer</div>
          <p className="muted-copy compact">Pick one {cohortLabel.toLowerCase()} to compare interaction shape against the full corpus.</p>
        </div>
        <select value={selected} onChange={event => onSelected(event.target.value)}>
          <option value="all">All {cohortLabel.toLowerCase()}s</option>
          {rows.map(row => <option key={row.user_id} value={row.user_id}>{row.user_id}</option>)}
        </select>
      </div>
      <div className="cohort-metric-grid">
        <PersonaMetric label="Sessions" value={compactNumber(selectedStats.n)} detail={`all ${compactNumber(allStats.n)}`} compact />
        {features.show_pass_rate === false ? (
          <PersonaMetric label="Flags" value={compactNumber(selectedStats.flags)} detail={`all ${compactNumber(allStats.flags)}`} compact />
        ) : (
          <PersonaMetric label="Pass Rate" value={pct(selectedStats.passRate)} detail={`all ${pct(allStats.passRate)}`} compact />
        )}
        <PersonaMetric label="Avg Turns" value={fmt(selectedStats.avgTurns)} detail={`all ${fmt(allStats.avgTurns)}`} compact />
        <PersonaMetric label="High Risk" value={compactNumber(selectedStats.highRisk)} detail={`${compactNumber(selectedStats.flags)} flags`} compact />
      </div>
      <table>
        <thead>
          <tr>
            <th>{cohortLabel}</th>
            <th className="num">Sessions</th>
            {features.show_pass_rate !== false && <th className="num">Pass</th>}
            <th className="num">Avg turns</th>
            <th className="num">High risk</th>
            <th className="num">Flags</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.user_id} className={selected === row.user_id ? 'selected-row' : ''}>
              <td><Link to={providerPath(`/cohorts/${row.user_id}`, provider)}>{row.user_id}</Link></td>
              <td className="num">{compactNumber(row.session_count)}</td>
              {features.show_pass_rate !== false && <td className="num">{pct(row.pass_rate)}</td>}
              <td className="num">{fmt(row.avg_turns)}</td>
              <td className="num">{compactNumber(row.high_risk_sessions)}</td>
              <td className="num">{compactNumber(row.flag_count)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TurnLengthPanel({ rows = [], providerInfo = {} }) {
  if (!rows.length) return null
  const features = providerInfo.features || {}
  const showPassRate = features.show_pass_rate !== false
  const chartRows = rows.map(row => ({
    ...row,
    bucket: `${row.quartile} (${row.turn_count_min}-${row.turn_count_max})`,
    pass_pct: Number(row.pass_rate || 0) * 100,
    fail_pct: Number(row.fail_count || 0) / Number(row.n || 1) * 100,
  }))
  return (
    <div className="card enterprise-panel">
      <div className="card-title">Interaction Length Burden</div>
      <p className="muted-copy compact">{showPassRate ? 'Longer traces are the clearest product signal in this benchmark: pass rate falls as sessions stretch.' : 'Conversation-length buckets show where longer sessions concentrate in the corpus.'}</p>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={chartRows} margin={{ top: 8, right: 12, left: 0, bottom: 52 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="bucket" tick={{ fontSize: 10 }} interval={0} angle={-18} textAnchor="end" height={66} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={value => showPassRate ? `${value}%` : compactNumber(value)} />
          <Tooltip formatter={(value, name) => [showPassRate ? `${Number(value).toFixed(0)}%` : compactNumber(value), name === 'pass_pct' ? 'Pass rate' : showPassRate ? 'Fail rate' : 'Sessions']} labelFormatter={(label, items) => {
            const row = items?.[0]?.payload
            return row ? `${label}: n=${row.n}, avg ${fmt(row.turn_count_mean)} turns` : label
          }} />
          <Bar dataKey={showPassRate ? 'pass_pct' : 'n'} name={showPassRate ? 'Pass rate' : 'Sessions'} fill={POSITIVE_COLOR} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <div className="length-bucket-grid">
        {chartRows.map(row => (
          <div key={row.quartile} className="length-bucket">
            <strong>{row.quartile}</strong>
            <span>{row.turn_count_min}-{row.turn_count_max} turns</span>
            <small>{showPassRate ? `${pct(row.pass_rate)} pass · ` : ''}n={row.n}</small>
          </div>
        ))}
      </div>
    </div>
  )
}

function ProductStateCards({ sessions = [], cohorts = [], reward = {}, viableSegments = [], hiddenSegments = 0, providerInfo = {} }) {
  const stats = sessionSetStats(sessions)
  const features = providerInfo.features || {}
  const cohortLabel = providerInfo.cohort_plural_label || 'cohorts'
  const actionLabelText = providerInfo.action_label || 'Action'
  return (
    <div className="stats-grid enterprise-stats">
      <PersonaMetric label="Sessions" value={compactNumber(stats.n || reward.trace_count)} detail={`${compactNumber(cohorts.length)} ${cohortLabel.toLowerCase()}`} />
      {features.show_pass_rate === false ? (
        <PersonaMetric label="Assistant Turns" value={compactNumber(reward.assistant_turn_count)} detail="turn-level activation basis" />
      ) : (
        <PersonaMetric label="Pass Rate" value={pct(stats.passRate ?? reward.pass_rate)} detail={`${compactNumber(reward.fail_count)} failures`} />
      )}
      <PersonaMetric label="Avg Turns" value={fmt(stats.avgTurns)} detail="interaction burden" />
      <PersonaMetric label="High Risk" value={compactNumber(stats.highRisk)} detail={`${compactNumber(stats.flags)} total flags`} />
      <PersonaMetric label={`Segment x ${actionLabelText}`} value={compactNumber(viableSegments.length)} detail={`${compactNumber(hiddenSegments)} low-n hidden`} />
      {features.show_reward === false ? (
        <PersonaMetric label="Flags" value={compactNumber(stats.flags)} detail="heuristic triage signals" />
      ) : (
        <PersonaMetric label="Failure Split" value={compactNumber(reward.db_failure_count)} detail={`${compactNumber(reward.communication_failure_count)} communication`} />
      )}
    </div>
  )
}

function topSegmentEvidence(row, workflowRows = [], actionRows = []) {
  const candidates = [
    ...workflowRows.filter(item => item.group === row.workflow),
    ...actionRows.filter(item => item.group === row.final_action),
  ].filter(item => item.vector && item.standardized_delta != null)
  const strongest = candidates.sort((a, b) => Math.abs(zValue(b)) - Math.abs(zValue(a)))[0]
  if (!strongest) return null
  return {
    ...strongest,
    label: `${zValue(strongest) >= 0 ? 'High' : 'Low'} ${vectorLabel(strongest.vector)}`,
    source: strongest.group_key === 'final_action' ? 'action' : 'task',
  }
}

function SegmentQueuePanel({ rows = [], workflowRows = [], actionRows = [] }) {
  const ranked = rows
    .filter(row => Number(row.n || 0) >= 7)
    .map(row => ({
      ...row,
      evidence: topSegmentEvidence(row, workflowRows, actionRows),
      opportunity: Number(row.n || 0) * (1 - Number(row.pass_rate || 0)),
    }))
    .sort((a, b) => b.opportunity - a.opportunity || Number(b.n || 0) - Number(a.n || 0))
    .slice(0, 10)
  if (!ranked.length) return null
  return (
    <div className="card enterprise-panel">
      <div className="card-title">Operational Segment Queue</div>
      <p className="muted-copy compact">Ranked by volume-weighted failures. Behavior evidence is the strongest task/action z-delta attached to the segment.</p>
      <table>
        <thead>
          <tr>
            <th>Segment</th>
            <th>Final action</th>
            <th className="num">n</th>
            <th className="num">Pass</th>
            <th className="num">Failures</th>
            <th>Behavior evidence</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map(row => (
            <tr key={`${row.workflow}-${row.final_action}`}>
              <td>{taskGroupLabel(row.workflow)}</td>
              <td>{actionLabel(row.final_action)}</td>
              <td className="num">{compactNumber(row.n)}</td>
              <td className="num">{pct(row.pass_rate)}</td>
              <td className="num">{compactNumber(row.fail_count)}</td>
              <td>{row.evidence ? `${row.evidence.label} (${row.evidence.source} z=${fmt(zValue(row.evidence))})` : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function selectedSessionSignal(analytics = {}, searchParams = new URLSearchParams()) {
  const rows = analytics.vector_deviations || []
  if (!rows.length) return null
  const coordinate = searchParams.get('coordinate') || ''
  const vectorParam = searchParams.get('vector') || ''
  const defaultVector = analytics.investigation?.vector
  const row = rows.find(item => (
    (vectorParam && item.vector === vectorParam) ||
    (coordinate && item.coordinate === coordinate)
  )) || rows.find(item => item.vector === defaultVector) || rows[0]
  const requestedScope = searchParams.get('baseline_scope') || analytics.investigation?.baseline_scope || row.expected_scope || 'global'
  const scope = resolveSessionScope(row, requestedScope)
  const scopeStats = row.scopes?.[scope] || row[scope] || row
  const z = Number(scopeStats.z ?? row.z ?? 0)
  const delta = Number(scopeStats.delta ?? row.delta ?? 0)
  return {
    row,
    vector: row.vector,
    coordinate: row.coordinate || coordinate,
    family: row.family || searchParams.get('family') || 'persona',
    baselineScope: scope,
    requestedScope,
    baseline: scopeStats,
    z,
    delta,
    polarity: z < 0 || (z === 0 && delta < 0) ? 'low' : 'high',
    source: searchParams.get('source') || 'session',
    focusedTurn: searchParams.get('turn') || '',
    fallbackReason: scope !== requestedScope ? `Requested ${scopeLabel(requestedScope)} baseline below n=10; using ${scopeLabel(scope)}.` : row.fallback_reason,
  }
}

function resolveSessionScope(row, requestedScope) {
  const scopes = row.scopes || {}
  const requested = requestedScope || row.expected_scope || 'global'
  const requestedStats = scopes[requested] || row[requested]
  if (requested === 'global' || Number(requestedStats?.n || 0) >= 10) return requested
  const expected = row.expected_scope || 'global'
  const expectedStats = scopes[expected] || row[expected]
  if (expected === 'global' || Number(expectedStats?.n || 0) >= 10) return expected
  if (Number(scopes.workflow?.n || 0) >= 10) return 'workflow'
  if (Number(scopes.final_action?.n || 0) >= 10) return 'final_action'
  return 'global'
}

function selectedTurnEvidence(turnDeviations = [], vector) {
  const rows = turnDeviations
    .map(row => ({
      ...row,
      signal: row.vectors?.[vector],
    }))
    .filter(row => row.signal?.z != null)
    .sort((a, b) => Math.abs(Number(b.signal.z || 0)) - Math.abs(Number(a.signal.z || 0)))
  return rows
}

function SessionInvestigationHeader({ trace, selected }) {
  if (!selected) return null
  const baseline = selected.baseline || {}
  return (
    <div className="overview-hero session-investigation-hero">
      <div>
        <div className="use-case-label">Investigation</div>
        <h2>{deviationLabel({ vector: selected.vector, z: selected.z, polarity: selected.polarity })}</h2>
        <p>
          Routed against {baseline.label || scopeLabel(selected.baselineScope)}. Primary z {fmt(selected.z)} compares this trace to that baseline; aggregate queue scores stay on the routing surface.
        </p>
      </div>
      <div className="hero-callout">
        <div className="card-title">Trace Context</div>
        <div className="asset-title">{trace.trace_id}</div>
        <p className="muted-copy compact">
          {taskGroupLabel(trace.metadata?.workflow || trace.metadata?.task_group || trace.metadata?.task?.workflow || '') || trace.domain} · reward {fmt(trace.reward)} · {trace.turns?.length || 0} turns
        </p>
      </div>
    </div>
  )
}

function SignalEvidencePanel({ selected }) {
  if (!selected) return null
  const baseline = selected.baseline || {}
  return (
    <div className="card session-evidence-card">
      <div className="card-title">Signal Evidence</div>
      <div className="evidence-metric-grid">
        <PersonaMetric label="Signal" value={deviationLabel({ vector: selected.vector, z: selected.z, polarity: selected.polarity })} detail={selected.family === 'emotion_cluster' ? 'Emotion cluster' : 'Persona'} compact />
        <PersonaMetric label="Primary z" value={fmt(selected.z)} detail={`${scopeLabel(selected.baselineScope)} baseline`} />
        <PersonaMetric label="Observed" value={fmt(selected.row.session)} detail={`raw ${fmt(selected.row.raw_session)}`} />
        <PersonaMetric label="Baseline" value={fmt(baseline.mean)} detail={`n=${compactNumber(baseline.n)} sd=${fmt(baseline.sd)}`} />
      </div>
      {selected.fallbackReason && <p className="muted-copy compact">{selected.fallbackReason}</p>}
    </div>
  )
}

function ComparableBaselinePanel({ selected }) {
  if (!selected?.row?.scopes) return null
  const scopes = ['workflow', 'final_action', 'task_action', 'global']
  return (
    <div className="card session-evidence-card">
      <div className="card-title">Comparable Baselines</div>
      <table>
        <thead>
          <tr>
            <th>Scope</th>
            <th className="num">n</th>
            <th className="num">Mean</th>
            <th className="num">sd</th>
            <th className="num">z</th>
          </tr>
        </thead>
        <tbody>
          {scopes.map(scope => {
            const row = selected.row.scopes?.[scope]
            if (!row) return null
            return (
              <tr key={scope} className={scope === selected.baselineScope ? 'selected-row' : ''}>
                <td>{row.label || scopeLabel(scope)}</td>
                <td className="num">{compactNumber(row.n)}</td>
                <td className="num">{fmt(row.mean)}</td>
                <td className="num">{fmt(row.sd)}</td>
                <td className="num">{fmt(row.z)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ProductContextPanel({ trace }) {
  const task = trace.metadata?.task || {}
  const rewardBreakdown = trace.metadata?.reward_breakdown || {}
  return (
    <div className="card session-evidence-card">
      <div className="card-title">Product Context</div>
      <table>
        <tbody>
          <tr><th>Final action</th><td>{actionLabel(trace.metadata?.final_action || 'no final action')}</td></tr>
          <tr><th>Expected actions</th><td>{(task.expected_actions || []).map(actionLabel).join(', ') || '-'}</td></tr>
          <tr><th>Outcome</th><td>{trace.outcome || '-'} · reward {fmt(trace.reward)}</td></tr>
          <tr><th>DB / Comm</th><td>{fmt(rewardBreakdown.DB)} / {fmt(rewardBreakdown.COMMUNICATE)}</td></tr>
          <tr><th>Reason</th><td>{task.reason_for_call || task.description || '-'}</td></tr>
        </tbody>
      </table>
    </div>
  )
}

function SelectedSignalTimeline({ selected, turnRows = [] }) {
  if (!selected || !turnRows.length) return null
  const chartRows = turnRows
    .map(row => ({
      ...row,
      signal: row.signal || row.vectors?.[selected.vector],
    }))
    .filter(row => row.signal?.z != null)
    .sort((a, b) => Number(a.turn_index) - Number(b.turn_index))
    .map(row => ({
      turn: row.turn_index,
      z: Number(row.signal.z),
      value: row.signal.value,
      baseline: 0,
    }))
  if (!chartRows.length) return null
  return (
    <div className="card">
      <div className="card-title">Selected Signal Timeline</div>
      <p className="muted-copy compact">Turn-position z for {vectorLabel(selected.vector)}. Zero is the comparable length/position baseline.</p>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartRows}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="turn" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(value, name) => [fmt(value), name === 'z' ? 'turn-position z' : name]} labelFormatter={label => `Turn ${label}`} />
          <ReferenceLine y={0} stroke="#080808" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="z" name={deviationLabel({ vector: selected.vector, z: selected.z })} stroke="#B9513A" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function Tau2Badge({ label }) {
  const baseLabel = String(label.label || label.text || '').replace(/^Tau2\s+/i, '')
  const displayLabel = label.kind === 'action_unchecked' && label.detail
    ? `${baseLabel}: ${evalLabelTitle(label.detail)}`
    : baseLabel
  return (
    <span className={`tau2-badge tau2-${label.kind || (label.met ? 'pass' : 'fail')}`}>
      <span>{displayLabel}</span>
      {label.reward != null && <strong>{fmt(label.reward)}</strong>}
    </span>
  )
}

function SessionTrajectoryChart({ turns, details, focusedCoordinate, emotionClusters = [] }) {
  const options = useMemo(() => trajectoryCoordinateOptions(details, emotionClusters), [details, emotionClusters])
  const optionKey = options.map(option => option.coordinate).join('|')
  const [coordinates, setCoordinates] = useState([])
  useEffect(() => {
    setCoordinates(defaultTrajectoryCoordinates(options, focusedCoordinate))
  }, [focusedCoordinate, optionKey])
  const rows = buildCoordinateTrajectoryRows(turns, details, coordinates, emotionClusters)
  const palette = [HIGHLIGHT_COLOR, '#080808', '#4A6FE0', '#2E8C43', '#F5CD2F', '#7A4CE0', '#D36B00']
  const selected = new Set(coordinates)
  const groupedOptions = options.reduce((acc, option) => {
    if (!selected.has(option.coordinate)) acc[option.family] = [...(acc[option.family] || []), option]
    return acc
  }, {})
  const resetDefaults = () => setCoordinates(defaultTrajectoryCoordinates(options, focusedCoordinate))
  const addCoordinate = value => {
    if (!value || selected.has(value)) return
    setCoordinates([...coordinates, value].slice(0, 8))
  }
  const removeCoordinate = value => setCoordinates(coordinates.filter(coordinate => coordinate !== value))

  return (
    <div className="card">
      <div className="card-heading-row trajectory-heading">
        <div>
          <div className="card-title">Conversation Trajectory</div>
          <div className="axis-chip-row">
            {coordinates.map((coordinate, index) => (
              <button
                key={coordinate}
                className="axis-chip"
                type="button"
                onClick={() => removeCoordinate(coordinate)}
                aria-label={`Remove ${coordinateTitle(coordinate)}`}
              >
                <span style={{ backgroundColor: palette[index % palette.length] }} />
                {coordinateTitle(coordinate)}
              </button>
            ))}
          </div>
        </div>
        <div className="toolbar">
          <select value="" onChange={event => addCoordinate(event.target.value)}>
            <option value="">Add projection</option>
            {Object.entries(groupedOptions).map(([family, group]) => (
              <optgroup key={family} label={familyTitle(family)}>
                {group.map(option => <option key={option.coordinate} value={option.coordinate}>{option.label}</option>)}
              </optgroup>
            ))}
          </select>
          <button className="compact-command" type="button" onClick={resetDefaults}>Defaults</button>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={330}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="turn" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} allowDecimals />
          <Tooltip formatter={value => value == null ? '-' : Number(value).toFixed(4)} labelFormatter={label => `turn ${label}`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={0} stroke={CHART_ZERO_COLOR} strokeDasharray="1 3" />
          {coordinates.map((coordinate, index) => (
            <Line
              key={coordinate}
              type="monotone"
              dataKey={axisIdForCoordinate(coordinate)}
              name={coordinateTitle(coordinate)}
              stroke={palette[index % palette.length]}
              strokeWidth={coordinate === focusedCoordinate ? 3 : 2}
              dot={{ r: coordinate === focusedCoordinate ? 4 : 3 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function EmotionSpectrumVisualizer({ turns = [], details = [] }) {
  const [sortMode, setSortMode] = useState('pca')
  const spectrum = useMemo(() => buildEmotionSpectrumData(turns, details, sortMode), [turns, details, sortMode])
  const [frameIndex, setFrameIndex] = useState(0)
  const [hoverPoint, setHoverPoint] = useState(null)
  useEffect(() => {
    setFrameIndex(0)
    setHoverPoint(null)
  }, [spectrum?.key])
  useEffect(() => {
    setHoverPoint(null)
  }, [sortMode])

  if (!spectrum?.frames?.length) return null

  const safeFrameIndex = Math.min(frameIndex, spectrum.frames.length - 1)
  const frame = spectrum.frames[safeFrameIndex]
  const handleFrameChange = event => {
    setFrameIndex(Number(event.currentTarget.value))
    setHoverPoint(null)
  }
  const width = 920
  const height = 390
  const plot = { left: 74, right: 52, top: 56, bottom: 132 }
  const plotWidth = width - plot.left - plot.right
  const plotHeight = height - plot.top - plot.bottom
  const baseline = plot.top + plotHeight / 2
  const amplitude = plotHeight / 2 - 12
  const positiveStartX = plot.left + (
    spectrum.coordinates.length <= 1
      ? 0
      : (spectrum.positiveStartIndex / (spectrum.coordinates.length - 1)) * plotWidth
  )
  const points = frame.points.map((point, index) => {
    const x = plot.left + (spectrum.coordinates.length <= 1 ? 0 : (index / (spectrum.coordinates.length - 1)) * plotWidth)
    const y = baseline - (Number(point.value || 0) / spectrum.scale) * amplitude
    const cluster = EMOTION_CLUSTER_BY_CONCEPT.get(emotionConceptKey(point.coordinate))
    return {
      ...point,
      cluster,
      x,
      y: Math.max(plot.top, Math.min(height - plot.bottom, y)),
      color: Number(point.value) >= 0 ? POSITIVE_COLOR : NEGATIVE_COLOR,
    }
  })
  const linePath = smoothLinePath(points)
  const areaPath = points.length ? `${linePath} L${points[points.length - 1].x.toFixed(2)},${baseline.toFixed(2)} L${points[0].x.toFixed(2)},${baseline.toFixed(2)} Z` : ''
  const xAxisTicks = points.filter((point, index) => (
    index % EMOTION_SPECTRUM_X_AXIS_STEP === 0 || index === points.length - 1
  ))
  const pointStep = spectrum.coordinates.length <= 1 ? plotWidth : plotWidth / (spectrum.coordinates.length - 1)
  const clusterRuns = points.reduce((runs, point, index) => {
    const cluster = point.cluster || { id: 'unknown', label: 'Unclustered', color: '#B8B1AA' }
    const previous = runs[runs.length - 1]
    if (previous?.cluster.id === cluster.id) {
      previous.end = index
    } else {
      runs.push({ cluster, start: index, end: index })
    }
    return runs
  }, []).map(run => {
    const startX = Math.max(plot.left, points[run.start].x - pointStep / 2)
    const endX = Math.min(width - plot.right, points[run.end].x + pointStep / 2)
    return { ...run, x: startX, width: Math.max(1, endX - startX) }
  })
  const handleSpectrumPointerMove = event => {
    if (!points.length) return
    const rect = event.currentTarget.getBoundingClientRect()
    const panelX = event.clientX - rect.left
    const panelY = event.clientY - rect.top
    const viewX = (panelX / rect.width) * width
    const nearest = points.reduce((best, point) => (
      Math.abs(point.x - viewX) < Math.abs(best.x - viewX) ? point : best
    ), points[0])
    setHoverPoint({
      ...nearest,
      panelX: Math.max(16, Math.min(rect.width - 16, panelX)),
      panelY: Math.max(16, Math.min(rect.height - 16, panelY)),
      placement: panelX > rect.width * 0.68 ? 'left' : 'right',
      side: nearest.index >= spectrum.positiveStartIndex ? 'right arc' : 'left arc',
    })
  }
  const handleSpectrumPointerLeave = () => setHoverPoint(null)

  return (
    <div className="card emotion-spectrum-card">
      <div className="card-heading-row spectrum-heading">
        <div>
          <div className="card-title">Emotion Concept Spectrum</div>
        </div>
        <div className="spectrum-heading-actions">
          <div className="compact-toggle">
            {[
              ['pca', 'PCA arc'],
              ['cluster', 'Clusters'],
              ['logical', 'Logical'],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={sortMode === id ? 'active wide' : 'wide'}
                onClick={() => setSortMode(id)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="spectrum-turn-readout">
            <span>Turn {frame.turnIndex}</span>
            <strong>{safeFrameIndex + 1} / {spectrum.frames.length}</strong>
          </div>
        </div>
      </div>
      <div className="emotion-spectrum-panel">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Emotion concept spectrum for turn ${frame.turnIndex}`}
          onPointerMove={handleSpectrumPointerMove}
          onPointerLeave={handleSpectrumPointerLeave}
        >
          <rect x={plot.left} y={plot.top} width={Math.max(0, positiveStartX - plot.left)} height={plotHeight} className="spectrum-negative-zone" />
          <rect x={positiveStartX} y={plot.top} width={Math.max(0, width - plot.right - positiveStartX)} height={plotHeight} className="spectrum-positive-zone" />
          {[-1, -0.5, 0, 0.5, 1].map(tick => {
            const y = baseline - tick * amplitude
            return (
              <g key={`h-${tick}`}>
                <line x1={plot.left} x2={width - plot.right} y1={y} y2={y} className={tick === 0 ? 'spectrum-zero-line' : 'spectrum-grid-line'} />
              </g>
            )
          })}
          {Array.from({ length: 12 }).map((_, index) => {
            const x = plot.left + (index / 11) * plotWidth
            return <line key={`v-${index}`} x1={x} x2={x} y1={plot.top} y2={height - plot.bottom} className="spectrum-grid-line vertical" />
          })}
          <text
            x={22}
            y={baseline}
            textAnchor="middle"
            className="spectrum-y-title"
            transform={`rotate(-90 22 ${baseline})`}
          >
            activation strength
          </text>
          <line x1={positiveStartX} x2={positiveStartX} y1={plot.top} y2={height - plot.bottom} className="spectrum-boundary-line" />
          <path d={areaPath} className="spectrum-area" />
          <path d={linePath} className="spectrum-line" />
          {clusterRuns.map((run, index) => (
            <g key={`${run.cluster.id}-${run.start}-${run.end}`}>
              <rect
                x={run.x}
                y={height - plot.bottom + 10}
                width={run.width}
                height="6"
                fill={run.cluster.color}
                className="spectrum-cluster-band"
              >
                <title>{run.cluster.label}</title>
              </rect>
            </g>
          ))}
          {xAxisTicks.map((tick, index) => (
            <g key={tick.coordinate}>
              <line x1={tick.x} x2={tick.x} y1={height - plot.bottom} y2={height - plot.bottom + 6} className="spectrum-x-tick" />
              <text
                x={tick.x}
                y={height - plot.bottom + 42}
                textAnchor={index === 0 ? 'start' : 'end'}
                className="spectrum-x-label"
                transform={`rotate(-36 ${tick.x} ${height - plot.bottom + 42})`}
              >
                {tick.label}
              </text>
            </g>
          ))}
          <rect x={plot.left} y={plot.top} width={plotWidth} height={plotHeight} className="spectrum-hover-target" />
          {hoverPoint && (
            <g className="spectrum-hover-marker">
              <line x1={hoverPoint.x} x2={hoverPoint.x} y1={plot.top} y2={height - plot.bottom} />
              <circle cx={hoverPoint.x} cy={hoverPoint.y} r="4.2" />
            </g>
          )}
        </svg>
        {hoverPoint && (
          <div
            className={`spectrum-tooltip ${hoverPoint.placement === 'left' ? 'left' : ''}`}
            style={{ left: hoverPoint.panelX, top: hoverPoint.panelY }}
          >
            <div className="spectrum-tooltip-title">{hoverPoint.label}</div>
            <div><span>activation</span><strong>{fmt(hoverPoint.value)}</strong></div>
            {hoverPoint.cluster && <div><span>cluster</span><strong>{hoverPoint.cluster.label}</strong></div>}
            <div><span>turn</span><strong>{frame.turnIndex}</strong></div>
            <div><span>position</span><strong>{hoverPoint.side}</strong></div>
          </div>
        )}
      </div>
      <div className="spectrum-controls">
          <input
            type="range"
            min="0"
            max={Math.max(0, spectrum.frames.length - 1)}
            step="1"
            value={safeFrameIndex}
            onInput={handleFrameChange}
            onChange={handleFrameChange}
            onMouseUp={handleFrameChange}
            onTouchEnd={handleFrameChange}
            onKeyUp={handleFrameChange}
            aria-label="Emotion spectrum turn"
          />
        <div className="spectrum-preview">{frame.preview || 'No assistant text preview for this turn.'}</div>
      </div>
    </div>
  )
}

function SessionEmotionClusterCard({ rows = [] }) {
  const chartRows = rows.slice(0, 8).map(row => ({
    ...row,
    label: coordinateTitle(row.coordinate),
    session: Number(row.session_mean),
    global: row.global_mean,
  })).reverse()
  if (!chartRows.length) return null
  return (
    <div className="card session-insight-card">
      <div className="card-heading-row">
        <div className="card-title">Emotion Cluster Profile</div>
        <div className="chart-legend">
          <span><i className="legend-swatch session-swatch" /> Session mean</span>
          <span><i className="legend-swatch global-swatch" /> Global mean</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartRows} layout="vertical" margin={{ top: 4, right: 18, left: 124, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="label" tick={{ fontSize: 11 }} width={124} />
          <Tooltip formatter={(value, name) => [fmt(value), name === 'session' ? 'session mean' : 'global mean']} />
          <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} strokeDasharray="1 3" />
          <Bar dataKey="global" fill="#B8B1AA" radius={[0, 3, 3, 0]} isAnimationActive={false} />
          <Bar dataKey="session" fill={HIGHLIGHT_COLOR} radius={[0, 3, 3, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <div className="cluster-band-grid">
        {rows.slice(0, 5).map(row => (
          <span key={row.coordinate} className="cluster-band-chip">
            {coordinateTitle(row.coordinate)} <strong>{row.percentile_band || '-'}</strong>
          </span>
        ))}
      </div>
    </div>
  )
}

function SessionProjectionDistributionCard({ rows = [] }) {
  if (!rows.length) return null
  return (
    <div className="card session-insight-card">
      <div className="card-heading-row">
        <div className="card-title">Projection Distribution In Conversation</div>
        <div className="chart-legend">
          <span><i className="legend-dot ordinary-dot" /> Turn</span>
          <span><i className="legend-dot tail-dot-swatch" /> Corpus tail</span>
          <span><i className="legend-line mean-line-swatch" /> Mean</span>
        </div>
      </div>
      <div className="projection-distribution-list">
        {rows.map(row => {
          const span = row.max - row.min || 1
          const meanLeft = `${clamp01((row.mean - row.min) / span) * 100}%`
          return (
            <div key={row.coordinate} className="projection-distribution-row">
              <div className="distribution-label">
                <span>{row.label}</span>
                <small>{row.values.length} turns · {row.tailCount} tails</small>
              </div>
              <div className="distribution-track">
                <span className="distribution-mean" style={{ left: meanLeft }} />
                {row.values.map(point => {
                  const left = `${clamp01((point.value - row.min) / span) * 100}%`
                  const isHighTail = row.q80 != null && point.value >= Number(row.q80)
                  const isLowTail = row.q20 != null && point.value <= Number(row.q20)
                  return (
                    <a
                      key={`${row.coordinate}-${point.turn}-${point.value}`}
                      className={`distribution-dot${isHighTail || isLowTail ? ' tail-dot' : ''}`}
                      href={`#turn-${point.turn}`}
                      title={`turn ${point.turn}: ${fmt(point.value)}`}
                      style={{ left }}
                    />
                  )
                })}
              </div>
              <div className="distribution-values">
                <span>{fmt(row.min)}</span>
                <strong>{fmt(row.mean)}</strong>
                <span>{fmt(row.max)}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SessionGlobalFitCard({ rows = [] }) {
  const topRows = rows.slice(0, 7)
  if (!topRows.length) return null
  return (
    <div className="card session-insight-card">
      <div className="card-heading-row">
        <div className="card-title">Where This Session Fits</div>
        <div className="chart-legend">
          <span><i className="legend-line session-line-swatch" /> Session</span>
          <span><i className="legend-line expected-line-swatch" /> Expected</span>
        </div>
      </div>
      <div className="fit-list">
        {topRows.map(row => {
          const percentile = clamp01(row.global_percentile)
          const expected = row.global?.p05 != null && row.global?.p95 != null
            ? clamp01((row.expected_mean - row.global.p05) / ((row.global.p95 - row.global.p05) || 1))
            : null
          return (
            <div key={row.vector} className="fit-row">
              <div className="fit-label">
                <span>{vectorLabel(row.vector)}</span>
                <small>{pct1(percentile)} global percentile</small>
              </div>
              <div className="fit-track">
                <span className="fit-marker session-marker" style={{ left: `${percentile * 100}%` }} />
                {expected != null && <span className="fit-marker expected-marker" style={{ left: `${expected * 100}%` }} />}
              </div>
              <div className="fit-values">
                <span>{fmt(row.global?.p05)}</span>
                <strong>{fmt(row.session)}</strong>
                <span>{fmt(row.global?.p95)}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SessionExpectedDeviationCard({ rows = [], groups = {} }) {
  const topRows = rows.slice(0, 7)
  if (!topRows.length) return null
  return (
    <div className="card session-insight-card">
      <div className="card-heading-row">
        <div>
          <div className="card-title">Deviation From Expected</div>
          <div className="stat-label">
            {taskGroupLabel(groups.task_group)} · {actionLabel(groups.final_action)} · task {groups.task_id}
          </div>
        </div>
      </div>
      <div className="deviation-table">
        <div className="deviation-header">
          <span>Vector</span>
          <span className="num">Session</span>
          <span className="num">Expected</span>
          <span className="num">Delta</span>
          <span className="num">z</span>
        </div>
        {topRows.map(row => (
          <div key={row.vector} className="deviation-row">
            <span>
              {vectorLabel(row.vector)}
              <small>{scopeLabel(row.expected_scope)} · n={row[row.expected_scope]?.n ?? '-'}</small>
            </span>
            <span className="num">{fmt(row.session)}</span>
            <span className="num">{fmt(row.expected_mean)}</span>
            <span className={`num ${Number(row.delta) >= 0 ? 'delta-positive' : 'delta-negative'}`}>{fmt(row.delta)}</span>
            <span className="num">{fmt(row.z)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function SessionAnalyticsGrid({ analytics, scoreDetails, projectionThresholds }) {
  if (!analytics?.available) return null
  const vectorRows = analytics.vector_deviations || []
  const projectionRows = buildSessionProjectionDistributions(scoreDetails, vectorRows, projectionThresholds)
  return (
    <div className="session-analytics-grid">
      <SessionEmotionClusterCard rows={analytics.emotion_clusters || []} />
      <SessionProjectionDistributionCard rows={projectionRows} />
      <SessionGlobalFitCard rows={vectorRows} />
      <SessionExpectedDeviationCard rows={vectorRows} groups={analytics.product_groups || {}} />
    </div>
  )
}


function Overview() {
  const [provider] = useProviderSelection()
  const [segmentMode, setSegmentMode] = useState('workflow')
  const [selectedPersona, setSelectedPersona] = useState('sycophantic')
  const [selectedEmotion, setSelectedEmotion] = useState('fear_and_overwhelm')
  const [showAllEmotions, setShowAllEmotions] = useState(false)
  const [queueFamily, setQueueFamily] = useState('persona')
  const { data, error } = useAsyncResource(() => getProductAnalytics(provider), [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Overview</h1>
      <p className="muted-copy">Could not load overview data: {error}</p>
    </div>
  )

  if (!data) return <h1 className="page-title">Loading...</h1>

  const providerInfo = data.provider || {}
  const providerCopy = providerInfo.copy || {}
  const providerFeatures = providerInfo.features || {}
  const persona = data.persona_overview || {}
  const reward = persona.reward_math || {}
  const scoreRowCount = data.score_source?.available
    ? (data.score_source.families || []).reduce((sum, row) => sum + Number(row.row_count || 0), 0)
    : null
  const personaVectors = (persona.persona_vectors || PERSONA_VECTOR_KEYS).filter(vector => PERSONA_VECTOR_KEYS.includes(vector))
  const emotionVectors = (persona.emotion_cluster_vectors || EMOTION_VECTOR_KEYS).filter(vector => EMOTION_VECTOR_KEYS.includes(vector))
  const baselineInventory = persona.vector_inventory || []
  const segmentRows = segmentMode === 'final_action'
    ? (persona.action_vector_deltas || [])
    : (persona.workflow_vector_deltas || [])
  const groupKey = segmentMode === 'final_action' ? 'final_action' : 'workflow'
  const groupLabel = value => segmentLabel(value, groupKey)
  const segmentLabelText = providerInfo.segment_label || 'Task'
  const actionLabelText = providerInfo.action_label || 'Final Action'
  const personaRows = segmentRows.filter(row => personaVectors.includes(row.vector))
  const emotionRows = segmentRows.filter(row => emotionVectors.includes(row.vector))
  const emotionBaselineVectors = emotionVectors.slice(0, 7)
  const selectedPersonaVector = personaVectors.includes(selectedPersona) ? selectedPersona : personaVectors[0]
  const selectedEmotionVector = emotionVectors.includes(selectedEmotion) ? selectedEmotion : emotionVectors[0]
  const simulatedSeries = persona.simulated_trace_series || {}
  const outlierSeries = persona.outlier_turn_series || []

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="subtle-line">{providerCopy.overview_subtitle || 'Enterprise behavior analytics.'}</p>
        </div>
        <div className="compact-toggle">
          {[
            ['workflow', segmentLabelText],
            ['final_action', actionLabelText],
          ].map(([id, label]) => (
            <button key={id} type="button" className={segmentMode === id ? 'active' : ''} onClick={() => setSegmentMode(id)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="overview-hero enterprise-hero">
        <div>
          <h2>Behavior Baselines</h2>
          <p>
            Compare where segments differ from global persona and emotion baselines.
          </p>
        </div>
        <div className="overview-chip-row" aria-label="Dataset scope">
          <span>{compactMetricNumber(reward.trace_count || data.trace_count)} traces</span>
          {providerInfo.dataset_label && <span>{providerInfo.dataset_label}</span>}
          <span>{data.score_source?.available ? 'Scores loaded' : 'Cached data'}</span>
        </div>
      </div>

      <SystemStateCards data={data} reward={reward} scoreRowCount={scoreRowCount} providerInfo={providerInfo} />

      {!persona.available && (
        <div className="card">
          <div className="card-title">Behavior analytics unavailable</div>
          <p className="muted-copy compact">Scored session rows are required for persona and emotion-cluster baselines.</p>
        </div>
      )}

      {persona.available && (
        <>
          <div className="overview-note">
            {persona.normalization_note || 'Segment z-deltas use raw direction-oriented values. Normalized values are presentation-only.'}
          </div>

          <div className="chart-row baseline-overview-row">
            <GlobalBaselineStrip
              title="Persona Baselines"
              rows={baselineInventory}
              vectors={personaVectors}
            />
            <GlobalBaselineStrip
              title="Emotion Baselines"
              description="Emotion clusters group related scored emotion concepts into readable families, such as joy, contentment, gratitude, suspicion, anger, fear, and shame."
              rows={baselineInventory}
              vectors={emotionBaselineVectors}
            />
          </div>

          <div className="overview-section">
            <div className="section-heading-row">
              <div className="card-title">Segment Baselines</div>
              <p className="muted-copy compact">Compare the same segments through two lenses: assistant persona traits and emotion clusters.</p>
            </div>
            <div className="chart-row segment-baseline-stack">
              <BaselineHeatmap
                title={`${segmentMode === 'workflow' ? segmentLabelText : actionLabelText} by Persona`}
                badge="Persona traits"
                legend={[
                  `Rows: ${(segmentMode === 'workflow' ? segmentLabelText : actionLabelText).toLowerCase()}`,
                  'Columns: traits',
                  'Cells: z vs global',
                ]}
                rows={personaRows}
                vectors={personaVectors}
                groupKey={groupKey}
                groupLabel={groupLabel}
                groupHeader={segmentMode === 'workflow' ? segmentLabelText : actionLabelText}
                expanded
              />
              <BaselineHeatmap
                title={`${segmentMode === 'workflow' ? segmentLabelText : actionLabelText} by Emotion`}
                badge="Emotion clusters"
                description="Default view shows the five emotion clusters with the largest segment differences. Expand for all ten."
                legend={[
                  `Rows: ${(segmentMode === 'workflow' ? segmentLabelText : actionLabelText).toLowerCase()}`,
                  'Columns: emotion clusters',
                  'Cells: z vs global',
                ]}
                rows={emotionRows}
                vectors={emotionVectors}
                groupKey={groupKey}
                groupLabel={groupLabel}
                groupHeader={segmentMode === 'workflow' ? segmentLabelText : actionLabelText}
                expanded={showAllEmotions}
                onExpanded={setShowAllEmotions}
              />
            </div>
          </div>

          <div className="chart-row two-col">
            <div className="card enterprise-panel trait-detail-panel">
              <div className="card-heading-row">
                <div>
                  <div className="card-title">Persona Trait Detail</div>
                  <p className="muted-copy compact">Select a trait to see which segments move above or below its global baseline.</p>
                </div>
                <label className="select-control-label">
                  <span>Trait</span>
                  <select value={selectedPersonaVector} onChange={event => setSelectedPersona(event.target.value)}>
                    {personaVectors.map(vector => <option key={vector} value={vector}>{vectorLabel(vector)}</option>)}
                  </select>
                </label>
              </div>
              <TraitDetailChart
                title={`${vectorLabel(selectedPersonaVector)} Across ${segmentMode === 'workflow' ? segmentLabelText : actionLabelText}`}
                readGuide="Bars show z-score vs the global trait baseline. 0 is typical; positive is more of this trait; negative is less."
                rows={personaRows}
                vector={selectedPersonaVector}
                groupLabel={groupLabel}
              />
            </div>

            <div className="card enterprise-panel trait-detail-panel">
              <div className="card-heading-row">
                <div>
                  <div className="card-title">Emotion Cluster Detail</div>
                  <p className="muted-copy compact">Select a cluster to see where related emotion signals rise or fall by segment.</p>
                </div>
                <label className="select-control-label">
                  <span>Emotion cluster</span>
                  <select value={selectedEmotionVector} onChange={event => setSelectedEmotion(event.target.value)}>
                    {emotionVectors.map(vector => <option key={vector} value={vector}>{vectorLabel(vector)}</option>)}
                  </select>
                </label>
              </div>
              <TraitDetailChart
                title={`${vectorLabel(selectedEmotionVector)} Across ${segmentMode === 'workflow' ? segmentLabelText : actionLabelText}`}
                readGuide="Bars show z-score vs the global emotion-cluster baseline. 0 is typical; positive is more of this emotion family; negative is less."
                rows={emotionRows}
                vector={selectedEmotionVector}
                groupLabel={groupLabel}
              />
            </div>
          </div>

          <div className="chart-row">
            <InvestigationQueue outliers={persona.outliers || []} family={queueFamily} onFamily={setQueueFamily} provider={provider} />
          </div>

          {outlierSeries.length > 0 && (
            <div className="overview-section">
              <div className="section-heading-row">
                <div>
                  <div className="card-title">Outlier Trace Previews</div>
                  <p className="muted-copy compact">Compact turn-level preview only; session pages own full trace inspection.</p>
                </div>
              </div>
              <div className="chart-row two-col">
                {outlierSeries.slice(0, 3).map(trace => (
                  <OutlierTraceChart key={trace.trace_id} trace={trace} provider={provider} />
                ))}
              </div>
            </div>
          )}

          {providerFeatures.show_product_storyboard !== false && simulatedSeries.available && (
            <div className="overview-section">
              <div className="section-heading-row">
                <div>
                  <div className="card-title">Deployment Preview Storyboard</div>
                  <p className="muted-copy compact">
                    {providerCopy.storyboard_note || `Example-only: each ${simulatedSeries.window_size}-trace block is sorted by segment labels.`}
                  </p>
                </div>
              </div>
              <TraceOrderSeriesChart rows={simulatedSeries.rows || []} vectors={simulatedSeries.vectors || []} />
            </div>
          )}

        </>
      )}
    </div>
  )
}

function ProductAnalytics() {
  const [provider] = useProviderSelection()
  const [segmentMode, setSegmentMode] = useState('workflow')
  const [signalFamily, setSignalFamily] = useState('persona')
  const [selectedVector, setSelectedVector] = useState('conciliatory')
  const [queueFamily, setQueueFamily] = useState('persona')
  const [showAllSignals, setShowAllSignals] = useState(false)
  const [selectedCohort, setSelectedCohort] = useState('all')
  const { data: payload, error } = useAsyncResource(
    () => Promise.all([getProductAnalytics(provider), getAuditSessions({}, provider), getAuditUsers(provider)])
      .then(([data, sessions, cohorts]) => ({ data, sessions, cohorts })),
    [provider],
  )

  if (error) return (
    <div>
      <h1 className="page-title">Product Analytics</h1>
      <p className="muted-copy">Could not load product analytics: {error}</p>
    </div>
  )

  if (!payload) return <h1 className="page-title">Loading...</h1>

  const { data, sessions = [], cohorts = [] } = payload
  const providerInfo = data.provider || {}
  const providerCopy = providerInfo.copy || {}
  const providerFeatures = providerInfo.features || {}
  const persona = data.persona_overview || {}
  const reward = persona.reward_math || {}
  const personaVectors = (persona.persona_vectors || PERSONA_VECTOR_KEYS).filter(vector => PERSONA_VECTOR_KEYS.includes(vector))
  const emotionVectors = (persona.emotion_cluster_vectors || EMOTION_VECTOR_KEYS).filter(vector => EMOTION_VECTOR_KEYS.includes(vector))
  const baselineInventory = persona.vector_inventory || []
  const segmentRows = segmentMode === 'final_action'
    ? (persona.action_vector_deltas || [])
    : (persona.workflow_vector_deltas || [])
  const groupKey = segmentMode === 'final_action' ? 'final_action' : 'workflow'
  const groupLabel = value => segmentLabel(value, groupKey)
  const segmentLabelText = providerInfo.segment_label || 'Task'
  const actionLabelText = providerInfo.action_label || 'Final Action'
  const familyVectors = signalFamily === 'emotion_cluster' ? emotionVectors : personaVectors
  const familyRows = segmentRows.filter(row => familyVectors.includes(row.vector))
  const selectedSignalVector = familyVectors.includes(selectedVector) ? selectedVector : familyVectors[0]
  const matrixRows = persona.workflow_action_matrix || []
  const viableMatrixRows = matrixRows.filter(row => row.n >= 10)
  const hiddenMatrixRows = Number(persona.low_n_task_action_count ?? Math.max(0, matrixRows.length - viableMatrixRows.length))
  const outliers = persona.outliers || []
  const taskInstability = persona.task_instability || []
  const baselineRows = (persona.vector_inventory || []).filter(row => row.overview)
  const turnRows = persona.turn_count_quartiles || []
  const longestBucket = [...turnRows].sort((a, b) => Number(b.turn_count_mean || 0) - Number(a.turn_count_mean || 0))[0]
  const shortestBucket = [...turnRows].sort((a, b) => Number(a.turn_count_mean || 0) - Number(b.turn_count_mean || 0))[0]
  const passDrop = shortestBucket && longestBucket ? Number(shortestBucket.pass_rate || 0) - Number(longestBucket.pass_rate || 0) : null

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Product Analytics</h1>
          <p className="subtle-line">{providerCopy.analytics_subtitle || 'Cohorts, interaction length, and segment operations.'}</p>
        </div>
      </div>

      <div className="overview-hero enterprise-hero">
        <div>
          <div className="use-case-label">Product analytics</div>
          <h2>Where interactions get long, fail, or need inspection.</h2>
          <p>
            {providerCopy.analytics_hero || 'This page starts from product structure and uses behavior vectors as investigation evidence.'}
          </p>
        </div>
        <div className="hero-callout">
          <div className="card-title">Interaction burden</div>
          <div className="asset-title">{providerFeatures.show_pass_rate === false ? compactNumber(reward.assistant_turn_count || 0) : (passDrop == null ? '-' : `${Math.round(passDrop * 100)}pt pass drop`)}</div>
          <p className="muted-copy compact">
            {providerFeatures.show_pass_rate === false
              ? 'Assistant turns scored across the active provider corpus.'
              : `Shortest quartile pass rate ${pct(shortestBucket?.pass_rate)} vs longest quartile ${pct(longestBucket?.pass_rate)}.`}
          </p>
        </div>
      </div>

      <ProductStateCards
        sessions={sessions}
        cohorts={cohorts}
        reward={reward}
        viableSegments={viableMatrixRows}
        hiddenSegments={hiddenMatrixRows}
        providerInfo={providerInfo}
      />

      {!persona.available && (
        <div className="card">
          <div className="card-title">Product analytics unavailable</div>
          <p className="muted-copy compact">
            This view needs scored session rows for assistant and emotion coordinates. The Overview still loads from the cached summary.
          </p>
        </div>
      )}

      {persona.available && (
        <>
          <div className="chart-row two-col">
            <CohortExplorerPanel cohorts={cohorts} sessions={sessions} selected={selectedCohort} onSelected={setSelectedCohort} providerInfo={providerInfo} />
            <TurnLengthPanel rows={turnRows} providerInfo={providerInfo} />
          </div>

          <div className="chart-row two-col">
            <SegmentQueuePanel
              rows={matrixRows}
              workflowRows={persona.workflow_vector_deltas || []}
              actionRows={persona.action_vector_deltas || []}
            />
            {providerFeatures.show_repeated_task_rewards !== false && (
            <div className="card enterprise-panel">
              <div className="card-title">Repeated Task Instability</div>
              <p className="muted-copy compact">{providerCopy.repeated_task_note || 'Repeated segment variation within the active provider corpus.'}</p>
              <table>
                <thead>
                  <tr>
                    <th>Task</th>
                    <th>Task group</th>
                    <th className="num">Pass</th>
                    <th className="num">Posture SD</th>
                    <th>Rewards</th>
                  </tr>
                </thead>
                <tbody>
                  {topRows(taskInstability, 8).map(row => (
                    <tr key={row.task_id}>
                      <td>{row.task_id}</td>
                      <td>{taskGroupLabel(row.workflow)}</td>
                      <td className="num">{pct(row.pass_rate)}</td>
                      <td className="num">{fmt(row.posture_sd)}</td>
                      <td>{row.rewards.map(value => Number(value).toFixed(0)).join(', ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            )}
          </div>

          <details className="session-collapsible" open>
            <summary>
              <span className="card-title">Behavior Signal Drilldown</span>
              <span className="stat-label">Persona/emotion deltas by task or action.</span>
            </summary>
            <div className="toolbar signal-drilldown-toolbar">
              <div className="compact-toggle">
                {[
                  ['workflow', segmentLabelText],
                  ['final_action', actionLabelText],
                ].map(([id, label]) => (
                  <button key={id} type="button" className={segmentMode === id ? 'active' : ''} onClick={() => setSegmentMode(id)}>
                    {label}
                  </button>
                ))}
              </div>
              <div className="compact-toggle">
                {[
                  ['persona', 'Persona'],
                  ['emotion_cluster', 'Emotion'],
                ].map(([id, label]) => (
                  <button key={id} type="button" className={signalFamily === id ? 'active' : ''} onClick={() => setSignalFamily(id)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <GlobalBaselineStrip
              title={`${signalFamily === 'emotion_cluster' ? 'Emotion Cluster' : 'Persona'} Global Baselines`}
              rows={baselineInventory}
              vectors={familyVectors}
            />
            <BaselineHeatmap
              title={`${signalFamily === 'emotion_cluster' ? 'Emotion Cluster' : 'Persona'} Baselines By ${segmentMode === 'workflow' ? segmentLabelText : actionLabelText}`}
              description={`${signalFamily === 'emotion_cluster' ? 'Emotion cluster' : 'Persona'} segment rows show z-deltas from the global run basis above.`}
              rows={familyRows}
              vectors={familyVectors}
              groupKey={groupKey}
              groupLabel={groupLabel}
              expanded={signalFamily === 'persona' || showAllSignals}
              onExpanded={signalFamily === 'emotion_cluster' ? setShowAllSignals : undefined}
            />
            <div className="card enterprise-panel">
              <div className="card-heading-row">
                <div>
                  <div className="card-title">Signal Detail</div>
                  <p className="muted-copy compact">Select one {signalFamily === 'emotion_cluster' ? 'emotion cluster' : 'persona trait'} and compare it across every visible segment.</p>
                </div>
                <select value={selectedSignalVector || ''} onChange={event => setSelectedVector(event.target.value)}>
                  {familyVectors.map(vector => <option key={vector} value={vector}>{vectorLabel(vector)}</option>)}
                </select>
              </div>
              <TraitDetailChart
                title={`${vectorLabel(selectedSignalVector)} Across ${segmentMode === 'workflow' ? segmentLabelText : actionLabelText}`}
                rows={familyRows}
                vector={selectedSignalVector}
                groupLabel={groupLabel}
              />
            </div>
          </details>

          <details className="session-collapsible">
            <summary>
              <span className="card-title">Trace Investigation Queue</span>
              <span className="stat-label">Workflow-relative behavioral outliers.</span>
            </summary>
            <InvestigationQueue outliers={outliers} family={queueFamily} onFamily={setQueueFamily} provider={provider} />
          </details>

          <details className="session-collapsible">
            <summary>
              <span className="card-title">Task x Action Drilldown</span>
              <span className="stat-label">n&gt;=10 cells only; {compactNumber(hiddenMatrixRows)} low-n cells hidden from first read.</span>
            </summary>
            <table>
              <thead>
                <tr>
                  <th>Task group</th>
                  <th>Final action</th>
                  <th className="num">n</th>
                  <th className="num">Pass</th>
                  <th className="num">Assistant</th>
                  <th className="num">Syc</th>
                  <th className="num">Assert</th>
                  <th className="num">Decisive</th>
                  <th className="num">Concil</th>
                </tr>
              </thead>
              <tbody>
                {viableMatrixRows.map(row => (
                  <tr key={`${row.workflow}-${row.final_action}`}>
                    <td>{taskGroupLabel(row.workflow)}</td>
                    <td>{actionLabel(row.final_action)}</td>
                    <td className="num">{row.n}</td>
                    <td className="num">{pct(row.pass_rate)}</td>
                    <td className="num">{fmt(row.assistant_axis)}</td>
                    <td className="num">{fmt(row.sycophantic)}</td>
                    <td className="num">{fmt(row.assertive)}</td>
                    <td className="num">{fmt(row.decisive)}</td>
                    <td className="num">{fmt(row.conciliatory)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <details className="session-collapsible">
            <summary>
              <span className="card-title">Outcome Gap Drilldown</span>
              <span className="stat-label">Directional only; small benchmark cells are not model-quality claims.</span>
            </summary>
            <table>
              <thead>
                <tr>
                  <th>Task group</th>
                  <th>Signal</th>
                  <th className="num">Fail n</th>
                  <th className="num">Pass n</th>
                  <th className="num">Fail mean</th>
                  <th className="num">Pass mean</th>
                  <th className="num">d</th>
                </tr>
              </thead>
              <tbody>
                {topRows(persona.workflow_outcome_deltas, 10).map(row => (
                  <tr key={`${row.workflow}-${row.vector}`}>
                    <td>{taskGroupLabel(row.workflow)}</td>
                    <td>{vectorLabel(row.vector)}</td>
                    <td className="num">{row.n_fail}</td>
                    <td className="num">{row.n_pass}</td>
                    <td className="num">{fmt(row.mean_fail)}</td>
                    <td className="num">{fmt(row.mean_pass)}</td>
                    <td className="num">{fmt(row.cohen_d_fail_vs_pass)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>

          <details className="session-collapsible">
            <summary>
              <span className="card-title">Methodology and baselines</span>
              <span className="stat-label">Raw basis, score families, and presentation scale.</span>
            </summary>
            <div className="chart-row two-col methodology-grid">
              <div>
                <table>
                  <thead>
                    <tr>
                      <th>Vector</th>
                      <th>Family</th>
                      <th className="num">Mean</th>
                      <th className="num">sd</th>
                      <th className="num">n</th>
                    </tr>
                  </thead>
                  <tbody>
                    {baselineRows.map(row => (
                      <tr key={row.vector}>
                        <td>{vectorLabel(row.vector)}</td>
                        <td>{row.family === 'emotion_cluster' ? 'Emotion' : 'Persona'}</td>
                        <td className="num">{fmt(row.basis_mean)}</td>
                        <td className="num">{fmt(row.basis_sd)}</td>
                        <td className="num">{compactNumber(row.n)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div>
                <table>
                  <thead>
                    <tr>
                      <th>Score family</th>
                      <th className="num">Coordinates</th>
                      <th className="num">Rows</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.score_source?.families || []).map(family => (
                      <tr key={family.score_family}>
                        <td>{familyTitle(family.score_family)}</td>
                        <td className="num">{family.coordinate_count}</td>
                        <td className="num">{compactNumber(family.row_count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </details>
        </>
      )}
    </div>
  )
}

function Sessions() {
  const [provider] = useProviderSelection()
  const [filters, setFilters] = useState({ domain: '', risk: '' })
  const isCorpusMode = !showReward
  const { data: sessionPayload, error } = useAsyncResource(
    () => getAuditSessions({
      domain: filters.domain || undefined,
      risk: filters.risk || undefined,
    }, provider),
    [filters.domain, filters.risk, provider],
  )
  const sessions = sessionPayload || []

  if (error) return (
    <div>
      <h1 className="page-title">Sessions</h1>
      <p className="muted-copy">Could not load sessions: {error}</p>
    </div>
  )

  const domains = [...new Set(sessions.map(session => session.domain))].sort()

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Sessions</h1>
        <div className="toolbar">
          <select value={filters.domain} onChange={event => setFilters({ ...filters, domain: event.target.value })}>
            <option value="">{isCorpusMode ? 'All topics' : 'All domains'}</option>
            {domains.map(domain => <option key={domain} value={domain}>{domain}</option>)}
          </select>
          <select value={filters.risk} onChange={event => setFilters({ ...filters, risk: event.target.value })}>
            <option value="">All risk</option>
            <option value="high">High</option>
            <option value="mid">Mid</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Session Audit</div>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>{isCorpusMode ? 'User' : 'Cohort'}</th>
              <th>{isCorpusMode ? 'Topic' : 'Domain'}</th>
              <th>Risk</th>
              {!isCorpusMode && <th className="num">Reward</th>}
              <th className="num">Flags</th>
              <th className="num">Turns</th>
              <th>{isCorpusMode ? 'Session' : 'Task'}</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map(session => (
              <tr key={session.trace_id}>
                <td><Link to={providerPath(`/sessions/${session.trace_id}`, provider)}>{session.trace_id}</Link></td>
                <td>{session.user_id}</td>
                <td>{session.domain}</td>
                <td><RiskPill band={session.risk_band} /></td>
                {!isCorpusMode && <td className="num">{fmt(session.reward)}</td>}
                <td className="num">{session.flag_count}</td>
                <td className="num">{session.turn_count}</td>
                <td><code>{session.task_id}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function SessionDetail() {
  const [provider] = useProviderSelection()
  const { traceId } = useParams()
  const location = useLocation()
  const { data: payload, error } = useAsyncResource(() => getAuditSession(traceId, provider), [traceId, provider])

  const scoreDetails = payload?.score_details || []
  const turnAxisRows = useMemo(() => buildTurnAxisRows(payload?.trace?.turns || [], scoreDetails), [payload, scoreDetails])
  const turnAxisByIndex = useMemo(() => {
    const byIndex = new Map()
    for (const row of turnAxisRows) byIndex.set(row.turn_index, row)
    return byIndex
  }, [turnAxisRows])
  const projectionTailThresholds = useMemo(
    () => buildProjectionTailThresholds(payload?.projection_thresholds || []),
    [payload],
  )

  if (error) return (
    <div>
      <h1 className="page-title">Session</h1>
      <p className="muted-copy">Could not load session: {error}</p>
    </div>
  )
  if (!payload) return <h1 className="page-title">Loading...</h1>

  const { trace, score_summary: scoreSummary = {} } = payload
  const providerInfo = payload.provider || {}
  const providerFeatures = providerInfo.features || {}
  const searchParams = new URLSearchParams(location.search)
  const focusedCoordinate = searchParams.get('coordinate') || ''
  const focusedTurn = searchParams.get('turn')
  const analytics = payload.session_analytics || {}
  const selectedSignal = selectedSessionSignal(analytics, searchParams)
  const selectedCoordinate = selectedSignal?.coordinate || focusedCoordinate
  const turnEvidenceRows = selectedTurnEvidence(analytics.turn_deviations || [], selectedSignal?.vector)
  const turnEvidenceByIndex = new Map(turnEvidenceRows.map(row => [Number(row.turn_index), row]))
  const tau2Eval = providerFeatures.show_tau2_eval === false ? null : trace.metadata?.tau2_eval
  const tau2TurnLabels = (tau2Eval?.turn_labels || []).reduce((acc, label) => {
    acc[label.turn_index] = [...(acc[label.turn_index] || []), label]
    return acc
  }, {})

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{trace.trace_id}</h1>
          <div className="subtle-line">{trace.domain} · {(providerInfo.task_label || 'task').toLowerCase()} {trace.task_id}</div>
        </div>
      </div>

      <SessionInvestigationHeader trace={trace} selected={selectedSignal} />

      <div className="chart-row three-col session-evidence-grid">
        <SignalEvidencePanel selected={selectedSignal} />
        <ComparableBaselinePanel selected={selectedSignal} />
        <ProductContextPanel trace={trace} />
      </div>

      <div className="chart-row">
        <SelectedSignalTimeline selected={selectedSignal} turnRows={turnEvidenceRows} />
      </div>

      {scoreDetails.length > 0 && (
        <details className="session-collapsible">
          <summary>
            <span className="card-title">Additional Trajectory Signals</span>
            <span className="stat-label">Opt-in multi-signal projection view.</span>
          </summary>
          <SessionTrajectoryChart
            turns={trace.turns}
            details={scoreDetails}
            focusedCoordinate={selectedCoordinate}
            emotionClusters={scoreSummary.emotion_clusters || []}
          />
        </details>
      )}

      {scoreDetails.length > 0 && (
        <details className="session-collapsible">
          <summary>
            <span className="card-title">Emotion Concept Spectrum</span>
            <span className="stat-label">Research drilldown; collapsed by default.</span>
          </summary>
          <EmotionSpectrumVisualizer turns={trace.turns} details={scoreDetails} />
        </details>
      )}

      <details className="session-collapsible">
        <summary>
          <span className="card-title">Legacy Session Analytics</span>
          <span className="stat-label">Global fit and distribution diagnostics.</span>
        </summary>
        <SessionAnalyticsGrid
          analytics={payload.session_analytics}
          scoreDetails={scoreDetails}
          projectionThresholds={payload.projection_thresholds || []}
        />
      </details>

      <div className="card">
        <div className="card-title">Trace</div>
        <div className="trace-table">
          <div className="trace-header">
            <span>Turn</span>
            <span>Conversation</span>
              <span>Evidence</span>
              <span>{providerFeatures.show_tau2_eval === false ? 'Provider labels' : 'Labels'}</span>
            </div>
            {trace.turns.map(turn => {
              const axisRow = turnAxisByIndex.get(turn.index)
              const labels = tau2TurnLabels[turn.index] || []
              const selectedTurn = turnEvidenceByIndex.get(Number(turn.index))
              const selectedChip = selectedTurn?.signal
              const projectionChips = selectedChip
                ? [{
                    id: `${turn.index}-${selectedSignal?.vector}`,
                    tone: Number(selectedChip.z || 0) < 0 ? 'low' : 'high',
                    label: deviationLabel({ vector: selectedSignal?.vector, z: selectedChip.z, polarity: selectedChip.polarity }),
                    value: selectedChip.z,
                  }]
                : []
              return (
              <div id={`turn-${turn.index}`} key={turn.turn_id} className={`turn-row role-${turn.role} ${focusedTurn && String(turn.index) === String(focusedTurn) ? 'focused-turn' : ''}`}>
                <div className="turn-meta">
                  <span>{turn.index}</span>
                  <span className="turn-role-tag">{turn.role}</span>
                  {turn.tool_name && <code>{turn.tool_name}</code>}
                </div>
                <p>{turn.content}</p>
                <div className="turn-score-strip">
                  {projectionChips.length > 0 ? (
                    projectionChips.map(chip => (
                      <span key={chip.id} className={`score-chip score-${chip.tone}`}>
                        {chip.label} <strong>{fmt(chip.value)}</strong>
                      </span>
                    ))
                  ) : (
                    <span className="empty-chip">None</span>
                  )}
                </div>
                <div className="tau2-badge-strip turn-eval-strip">
                  {providerFeatures.show_tau2_eval !== false && labels.length > 0 ? (
                    labels.map((label, index) => <Tau2Badge key={`${label.kind}-${label.label}-${index}`} label={label} />)
                  ) : (
                    <span className="empty-chip">{providerFeatures.show_tau2_eval === false && turn.role === 'assistant' ? 'Scored turn' : 'None'}</span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Cohorts() {
  const [provider] = useProviderSelection()
  const [users, setUsers] = useState([])

  useEffect(() => {
    getAuditUsers(provider).then(setUsers)
  }, [provider])

  const isCorpusMode = !showReward

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Cohorts</h1>
          <p className="subtle-line">
            {isCorpusMode ? 'Conversation users grouped for corpus analytics.' : 'Synthetic Tau2 trace buckets used to demonstrate cohort analytics.'}
          </p>
        </div>
      </div>
      <div className="card">
        <div className="card-title">{isCorpusMode ? 'Users' : 'Benchmark Cohorts'}</div>
        <table>
          <thead>
            <tr>
              <th>{isCorpusMode ? 'User' : 'Cohort'}</th>
              <th>{isCorpusMode ? 'Topics' : 'Domains'}</th>
              <th className="num">Sessions</th>
              <th className="num">High Risk</th>
              <th className="num">Flags</th>
              {!isCorpusMode && <th className="num">Avg Reward</th>}
              <th>Last Outcome</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.user_id}>
                <td><Link to={providerPath(`/cohorts/${user.user_id}`, provider)}>{user.user_id}</Link></td>
                <td>{user.domains.join(', ')}</td>
                <td className="num">{user.session_count}</td>
                <td className="num">{user.high_risk_sessions}</td>
                <td className="num">{user.flag_count}</td>
                {!isCorpusMode && <td className="num">{fmt(user.avg_reward)}</td>}
                <td>{user.last_outcome}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CohortDetail() {
  const [provider] = useProviderSelection()
  const { cohortId, userId } = useParams()
  const resolvedCohortId = cohortId || userId
  const [payload, setPayload] = useState(null)

  useEffect(() => {
    setPayload(null)
    getAuditUser(resolvedCohortId, provider).then(setPayload)
  }, [resolvedCohortId, provider])

  if (!payload) return <h1 className="page-title">Loading...</h1>

  const { user, sessions } = payload
  const providerInfo = payload.provider || {}
  const providerFeatures = providerInfo.features || {}
  const showReward = providerFeatures.show_reward !== false

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{user.user_id}</h1>
          <p className="subtle-line">
            {showReward ? 'Synthetic benchmark cohort, not a production user identity.' : 'Conversation user grouped from the sampled corpus.'}
          </p>
        </div>
        <span className="status-pill">{user.domains.join(', ')}</span>
      </div>

      <div className="stats-grid">
        <div className="card">
          <div className="card-title">Sessions</div>
          <div className="stat-value">{user.session_count}</div>
          <div className="stat-label">{user.high_risk_sessions} high-risk sessions in cohort</div>
        </div>
        <div className="card">
          <div className="card-title">Flags</div>
          <div className="stat-value">{user.flag_count}</div>
          <div className="stat-label">Across reviewed sessions</div>
        </div>
        {showReward ? (
          <div className="card">
            <div className="card-title">Avg Reward</div>
            <div className="stat-value">{fmt(user.avg_reward)}</div>
            <div className="stat-label">Last outcome {user.last_outcome}</div>
          </div>
        ) : (
          <div className="card">
            <div className="card-title">Topic Count</div>
            <div className="stat-value">{user.domains.length}</div>
            <div className="stat-label">Conversation topics in sample</div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Sessions</div>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>{showReward ? 'Domain' : 'Topic'}</th>
              <th>Risk</th>
              {showReward && <th className="num">Reward</th>}
              <th className="num">Flags</th>
              <th>{showReward ? 'Task' : 'Session'}</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map(session => (
              <tr key={session.trace_id}>
                <td><Link to={providerPath(`/sessions/${session.trace_id}`, provider)}>{session.trace_id}</Link></td>
                <td>{session.domain}</td>
                <td><RiskPill band={session.risk_band} /></td>
                {showReward && <td className="num">{fmt(session.reward)}</td>}
                <td className="num">{session.flag_count}</td>
                <td><code>{session.task_id}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function HighStakes() {
  const [reports, setReports] = useState([])

  useEffect(() => {
    getHighStakesReports().then(setReports)
  }, [])

  const rows = reports.flatMap(report =>
    report.steps
      .filter(step => step.kind === 'probe_result')
      .map(step => ({ ...step, report: report.label, family: report.family, report_id: report.id })),
  )

  return (
    <div>
      <h1 className="page-title">High-Stakes Signals</h1>
      <div className="card">
        <div className="card-title">Signal Checks</div>
        <table>
          <thead>
            <tr>
              <th>Signal Set</th>
              <th>Check</th>
              <th className="num">Balanced Acc</th>
              <th className="num">AUROC</th>
              <th className="num">Selectivity</th>
              <th className="num">Examples</th>
              <th>Mode</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.report_id}-${row.step}-${index}`}>
                <td>
                  <span className="dot" style={{ background: SIGNAL_COLORS[row.family] || FALLBACK_SIGNAL_COLOR }} />
                  {row.report}
                </td>
                <td>{evalLabelTitle(row.step)}</td>
                <td className="num">{fmt(row.balanced_accuracy)}</td>
                <td className="num">{fmt(row.auroc)}</td>
                <td className="num">{fmt(row.selectivity)}</td>
                <td className="num">{row.example_count ?? '-'}</td>
                <td>{row.training_mode || row.split_mode || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RegistrySpaceCard({ space }) {
  const coordinates = space.coordinates || space.pilot_coordinates || space.domains || []
  const requirements = space.requires || []
  return (
    <div className="card registry-space-card">
      <div className="registry-space-header">
        <div>
          <div className="card-title">{space.label}</div>
          <div className="asset-title">{familyTitle(space.family)}</div>
        </div>
        <span className="status-pill">{space.status}</span>
      </div>
      <div className="asset-meta">
        <span>{space.score_kind}</span>
        <span>{space.model}</span>
        <span>Layer {space.layer}</span>
        <span>{compactNumber(space.coordinate_count)} coordinates</span>
      </div>
      {coordinates.length > 0 && (
        <div className="registry-coordinate-preview">
          {coordinates.slice(0, 10).map(coordinate => (
            <span key={coordinate} className="tag">{vectorLabel(String(coordinate).replace('assistant_axis_trait__', ''))}</span>
          ))}
          {coordinates.length > 10 && <span className="tag">+{coordinates.length - 10} more</span>}
        </div>
      )}
      {requirements.length > 0 && (
        <ul className="registry-requirements">
          {requirements.map(requirement => <li key={requirement}>{requirement}</li>)}
        </ul>
      )}
    </div>
  )
}

function Registry() {
  const [provider] = useProviderSelection()
  const { data: payload, error } = useAsyncResource(
    () => Promise.all([getScoreSpaces(provider), getEmotions()])
      .then(([scoreSpaces, emotions]) => ({ scoreSpaces, emotions })),
    [provider],
  )

  if (error) return (
    <div>
      <h1 className="page-title">Registry</h1>
      <p className="muted-copy">Could not load registry: {error}</p>
    </div>
  )

  if (!payload) return <h1 className="page-title">Loading...</h1>

  const { scoreSpaces, emotions } = payload
  const spaces = scoreSpaces.spaces || []
  const capturePlan = scoreSpaces.capture_plan || {}
  const providerInfo = scoreSpaces.provider || {}
  const coordinateCount = spaces.reduce((total, space) => total + Number(space.coordinate_count || 0), 0)
  const emotionConcepts = emotions.concepts || []
  const pilotConcepts = emotions.pilot_concepts || []

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Registry</h1>
          <p className="subtle-line">Scoring spaces, vector assets, model captures, and audit-ready probes.</p>
        </div>
      </div>

      <div className="stats-grid">
        <div className="card">
          <div className="card-title">Spaces</div>
          <div className="stat-value">{compactNumber(spaces.length)}</div>
          <div className="stat-label">registered scoring families</div>
        </div>
        <div className="card">
          <div className="card-title">Coordinates</div>
          <div className="stat-value">{compactNumber(coordinateCount)}</div>
          <div className="stat-label">vectors, traits, concepts, and probes</div>
        </div>
        <div className="card">
          <div className="card-title">Input Rows</div>
          <div className="stat-value">{compactNumber(providerInfo.assistant_turn_record_count)}</div>
          <div className="stat-label">{compactNumber(providerInfo.trace_count)} sessions in active provider</div>
        </div>
      </div>

      <div className="registry-space-list">
        {spaces.map(space => <RegistrySpaceCard key={space.id} space={space} />)}
      </div>

      <div className="chart-row two-col">
        <div className="card">
          <div className="card-title">Capture Plan</div>
          <table>
            <tbody>
              <tr><th>Model</th><td>{capturePlan.model_id}</td></tr>
              <tr><th>Residual site</th><td>{capturePlan.residual_site}</td></tr>
              <tr><th>Required layers</th><td>{(capturePlan.required_layers || []).join(', ')}</td></tr>
              <tr><th>Sections</th><td>{(capturePlan.sections || []).join(', ')}</td></tr>
            </tbody>
          </table>
          {capturePlan.note && <p className="muted-copy compact registry-note">{capturePlan.note}</p>}
        </div>

        <div className="card">
          <div className="card-title">Emotion Vector Asset</div>
          <div className="asset-title">{emotions.asset?.label}</div>
          <div className="asset-meta">
            <span>{emotions.asset?.model}</span>
            <span>Layer {emotions.asset?.layer}</span>
            <span>{compactNumber(emotionConcepts.length)} concepts</span>
          </div>
          <p className="muted-copy compact">{emotions.asset?.description}</p>
          {pilotConcepts.length > 0 && (
            <>
              <div className="registry-section-label">Pilot concepts</div>
              <div className="tag-row">
                {pilotConcepts.map(concept => <span key={concept} className="tag">{concept}</span>)}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Emotion Concept Index</div>
        <div className="concept-grid">
          {emotionConcepts.map(concept => <span key={concept}>{concept}</span>)}
        </div>
      </div>
    </div>
  )
}

function CharacterScatterTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{point.label}</div>
      <div>Frequency: {pct1(point.frequency)} of traces</div>
      <div>Distinctiveness: {point.distinctiveness >= 0 ? '+' : ''}{pct1(point.distinctiveness)} vs reference</div>
      <div className="muted-copy compact">Reference rate {pct1(point.reference_rate)} · {point.audited_present}/{point.audited_total} present</div>
    </div>
  )
}

function CharacterTraitLabel({ x, y, value }) {
  if (x == null || y == null) return null
  return (
    <text x={x} y={y - 9} textAnchor="middle" fontSize={10} fill="#080808" stroke="#fff8f4" strokeWidth={3} paintOrder="stroke" style={{ pointerEvents: 'none' }}>{value}</text>
  )
}

function CharacterDistributionTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  const bin = payload[0]?.payload
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">peak ≈ {Number(label).toFixed(2)}</div>
      <div>This model: {pct1(bin?.audited)}</div>
      <div>Reference: {pct1(bin?.reference)}</div>
    </div>
  )
}

function CharacterDistribution({ distribution, label }) {
  const bins = distribution?.bins || []
  if (!bins.length) return null
  return (
    <div className="character-distribution">
      <p className="muted-copy compact">
        Distribution of per-trace peak {label?.toLowerCase()} intensity — this model vs reference, each as
        a share of its own traces. The dashed line is the presence threshold; mass to its right is the tail.
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={bins} margin={{ top: 18, right: 16, left: 0, bottom: 4 }} barGap={0} barCategoryGap="8%">
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} vertical={false} />
          <XAxis type="number" dataKey="mid" domain={['dataMin', 'dataMax']} tickFormatter={value => Number(value).toFixed(1)} tick={{ fontSize: 10 }} />
          <YAxis tickFormatter={pct} tick={{ fontSize: 10 }} />
          <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<CharacterDistributionTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine x={distribution.threshold} stroke={HIGHLIGHT_COLOR} strokeDasharray="4 3" label={{ value: 'threshold', fontSize: 10, position: 'top', fill: HIGHLIGHT_COLOR }} />
          <Bar dataKey="reference" name="Reference" fill={CHARACTER_REFERENCE_COLOR} isAnimationActive={false} />
          <Bar dataKey="audited" name="This model" fill={CHARACTER_PEARL_COLOR} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function CharacterDrift({ drift, label }) {
  const segments = drift?.segments || []
  if (!segments.length) return null
  const summary = drift.audited_summary || {}
  const multi = summary.multi_turn_traces || 0
  const lower = label?.toLowerCase()
  return (
    <div className="character-distribution">
      <p className="muted-copy compact">
        How {lower} intensity moves across a conversation (start → end), averaged over the corpus, vs reference.
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={segments} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={value => Number(value).toFixed(1)} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(value, name) => [value == null ? '-' : Number(value).toFixed(3), name]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey="reference" name="Reference" stroke={CHARACTER_REFERENCE_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
          <Line type="monotone" dataKey="audited" name="This model" stroke={CHARACTER_PEARL_COLOR} strokeWidth={2} dot isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
      {multi > 0 && (
        <p className="muted-copy compact">
          Within-conversation drift: {pct((summary.rising || 0) / multi)} of {multi.toLocaleString()} multi-turn conversations rise in {lower} from start to end,
          {' '}{pct((summary.falling || 0) / multi)} fall (mean change {summary.mean_delta >= 0 ? '+' : ''}{fmt(summary.mean_delta)}).
        </p>
      )}
    </div>
  )
}

function CharacterDrilldown({ coordinate, provider, point }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setDetail(null)
    setError(null)
    getCharacterTrait(coordinate, provider)
      .then(data => { if (active) setDetail(data) })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [coordinate, provider])

  return (
    <div className="card">
      <div className="card-title">{point?.label} · distribution & traces</div>
      <p className="muted-copy compact">
        Traces whose peak {point?.label?.toLowerCase()} intensity exceeds the reference threshold,
        ranked by peak. Click any trace to inspect it turn by turn in Session Review.
      </p>
      {error && <p className="muted-copy">Could not load traces: {error}</p>}
      {!detail && !error && <p className="muted-copy">Loading traces...</p>}
      {detail && (
        <>
          <CharacterDistribution distribution={detail.distribution} label={point?.label} />
          <CharacterDrift drift={detail.drift} label={point?.label} />
          <table className="data-table">
            <thead>
              <tr>
                <th>Trace</th>
                <th>Peak score</th>
                <th>Trace mean</th>
                <th>Peak turn</th>
                <th>Turns</th>
              </tr>
            </thead>
            <tbody>
              {detail.traces.slice(0, 25).map(row => (
                <tr key={row.trace_id}>
                  <td>
                    <Link to={providerPath(sessionFocusLink(row.trace_id, {
                      coordinate,
                      vector: point?.trait,
                      family: 'persona',
                      turn: row.peak_turn,
                      source: 'character',
                    }), provider)}>{row.trace_id}</Link>
                  </td>
                  <td>{fmt(row.max_score)}</td>
                  <td>{fmt(row.mean_score)}</td>
                  <td>{row.peak_turn ?? '-'}</td>
                  <td>{row.turns}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {detail.point.audited_present > 25 && (
            <p className="muted-copy compact">
              Showing the 25 most extreme of {detail.point.audited_present} present traces.
            </p>
          )}
        </>
      )}
    </div>
  )
}

const CHARACTER_PEARL_COLOR = '#4A6FE0'
const CHARACTER_REFERENCE_COLOR = '#B8B1AA'

function characterCoord(entry) {
  return entry?.coordinate || entry?.payload?.coordinate || null
}

function joinTraits(labels) {
  const lower = labels.map(label => label.toLowerCase())
  if (lower.length <= 1) return lower.join('')
  if (lower.length === 2) return `${lower[0]} and ${lower[1]}`
  return `${lower.slice(0, -1).join(', ')}, and ${lower[lower.length - 1]}`
}

function CharacterSignature({ points, meta, selected, onSelect }) {
  const byDistinct = [...points].sort((a, b) => b.distinctiveness - a.distinctiveness)
  const distinctive = byDistinct.filter(p => p.distinctiveness > 0).slice(0, 3)
  const suppressed = [...points].sort((a, b) => a.distinctiveness - b.distinctiveness).filter(p => p.distinctiveness < 0).slice(0, 2)

  const Chip = ({ point, sign }) => (
    <button
      type="button"
      className={`character-chip ${sign} ${point.coordinate === selected ? 'active' : ''}`}
      onClick={() => onSelect(point.coordinate)}
    >
      <span>{point.label}</span>
      <strong>{point.distinctiveness >= 0 ? '+' : ''}{pct1(point.distinctiveness)}</strong>
    </button>
  )

  return (
    <>
      {(distinctive.length > 0 || suppressed.length > 0) && (
        <p className="character-headline">
          Against the {meta.reference_provider} reference, this model is markedly more{' '}
          <strong>{joinTraits(distinctive.map(p => p.label))}</strong>
          {suppressed.length > 0 && <> — and notably less <strong>{joinTraits(suppressed.map(p => p.label))}</strong></>}.
        </p>
      )}
      <div className="character-signature-grid">
        <div className="card">
          <div className="card-title">Most characteristic</div>
          <p className="muted-copy compact">Traits this model shows far more than the reference.</p>
          <div className="character-chip-row">
            {distinctive.length ? distinctive.map(p => <Chip key={p.coordinate} point={p} sign="up" />) : <span className="muted-copy compact">None above reference.</span>}
          </div>
        </div>
        <div className="card">
          <div className="card-title">Most suppressed</div>
          <p className="muted-copy compact">Traits this model shows less than the reference.</p>
          <div className="character-chip-row">
            {suppressed.length ? suppressed.map(p => <Chip key={p.coordinate} point={p} sign="down" />) : <span className="muted-copy compact">None below reference.</span>}
          </div>
        </div>
      </div>
    </>
  )
}

function CharacterBarTooltip({ active, payload, mode }) {
  if (!active || !payload || !payload.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{point.label}</div>
      {mode === 'frequency' ? (
        <>
          <div>This model: {pct1(point.frequency)}</div>
          <div>Reference: {pct1(point.reference_rate)}</div>
        </>
      ) : (
        <div>Distinctiveness: {point.distinctiveness >= 0 ? '+' : ''}{pct1(point.distinctiveness)}</div>
      )}
      <div className="muted-copy compact">{point.audited_present}/{point.audited_total} traces present</div>
    </div>
  )
}

function CharacterSpectrum({ points, selected, onSelect }) {
  const data = [...points].sort((a, b) => b.distinctiveness - a.distinctiveness)
  const bound = Math.max(0.05, ...data.map(p => Math.abs(p.distinctiveness)))
  const padded = Math.ceil(bound * 110) / 100
  const height = Math.max(360, data.length * 30 + 48)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} horizontal={false} />
        <XAxis type="number" domain={[-padded, padded]} tickFormatter={pct} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="label" width={96} interval={0} tick={{ fontSize: 11 }} />
        <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} />
        <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<CharacterBarTooltip mode="signature" />} />
        <Bar dataKey="distinctiveness" radius={[0, 4, 4, 0]} isAnimationActive={false} cursor="pointer" onClick={entry => onSelect(characterCoord(entry))}>
          {data.map(point => (
            <Cell
              key={point.coordinate}
              fill={point.distinctiveness >= 0 ? POSITIVE_COLOR : HIGHLIGHT_COLOR}
              fillOpacity={point.coordinate === selected ? 1 : 0.78}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 1.5 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function CharacterFrequency({ points, selected, onSelect }) {
  const data = [...points].sort((a, b) => b.frequency - a.frequency)
  const height = Math.max(360, data.length * 34 + 48)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }} barGap={2}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} horizontal={false} />
        <XAxis type="number" domain={[0, 1]} tickFormatter={pct} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="label" width={96} interval={0} tick={{ fontSize: 11 }} />
        <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<CharacterBarTooltip mode="frequency" />} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="reference_rate" name="Reference" fill={CHARACTER_REFERENCE_COLOR} radius={[0, 3, 3, 0]} isAnimationActive={false} />
        <Bar dataKey="frequency" name="This model" fill={CHARACTER_PEARL_COLOR} radius={[0, 3, 3, 0]} isAnimationActive={false} cursor="pointer" onClick={entry => onSelect(characterCoord(entry))}>
          {data.map(point => (
            <Cell
              key={point.coordinate}
              fillOpacity={point.coordinate === selected ? 1 : 0.85}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 1.5 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function CharacterPortrait({ points, selected, onSelect }) {
  const values = points.map(p => p.distinctiveness)
  const lo = Math.min(0, ...values)
  const hi = Math.max(0, ...values)
  const pad = Math.max(0.03, (hi - lo) * 0.1)
  const yDomain = [Math.floor((lo - pad) * 100) / 100, Math.ceil((hi + pad) * 100) / 100]
  return (
    <ResponsiveContainer width="100%" height={460}>
      <ScatterChart margin={{ top: 24, right: 28, left: 8, bottom: 44 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
        <XAxis
          type="number"
          dataKey="frequency"
          name="Frequency"
          domain={[0, 1]}
          tickFormatter={pct}
          tick={{ fontSize: 11 }}
          label={{ value: 'Frequency (share of traces present)', position: 'bottom', offset: 18, fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="distinctiveness"
          name="Distinctiveness"
          domain={yDomain}
          tickFormatter={pct}
          tick={{ fontSize: 11 }}
          label={{ value: 'Distinctiveness (signed lift)', angle: -90, position: 'left', offset: -2, fontSize: 12 }}
        />
        <ZAxis range={[140, 140]} />
        <ReferenceLine y={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<CharacterScatterTooltip />} />
        <Scatter
          data={points}
          isAnimationActive={false}
          onClick={entry => onSelect(characterCoord(entry))}
          cursor="pointer"
        >
          <LabelList dataKey="label" content={<CharacterTraitLabel />} />
          {points.map(point => (
            <Cell
              key={point.coordinate}
              fill={point.distinctiveness >= 0 ? POSITIVE_COLOR : HIGHLIGHT_COLOR}
              fillOpacity={point.coordinate === selected ? 1 : 0.72}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 2 : 0}
            />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  )
}

const CHARACTER_MODES = [
  ['portrait', 'Portrait', 'Two measurements of one space: frequency on x, signed distinctiveness on y. Above the line is distinctive, below is suppressed. Click a trait to drill in.'],
  ['signature', 'Signature', 'Traits ranked by signed lift over the reference — the model’s characteristic signature at a glance. Click a bar to drill in.'],
  ['frequency', 'Frequency', 'How often each trait is present in this model vs the reference. Frequency keeps distinctiveness honest. Click a bar to drill in.'],
]

function Character() {
  const [provider] = useProviderSelection()
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [mode, setMode] = useState('portrait')

  useEffect(() => {
    let active = true
    setPayload(null)
    setError(null)
    setSelected(null)
    getCharacter(provider)
      .then(data => { if (active) setPayload(data) })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Character</h1>
      <p className="muted-copy">Could not load Character data: {error}</p>
    </div>
  )
  if (!payload) return <h1 className="page-title">Loading...</h1>

  const points = payload.points || []
  const dropped = payload.dropped || []
  const meta = payload.meta || {}
  const selectedPoint = points.find(p => p.coordinate === selected) || null
  const modeCopy = CHARACTER_MODES.find(([id]) => id === mode)?.[2]

  return (
    <div>
      <h1 className="page-title">Character</h1>
      <p className="muted-copy">
        What this model does in the common case. Each persona trait is measured two ways: how often it
        shows up ({meta.audited_provider}) and how distinctive that is against the {meta.reference_provider}{' '}
        reference. The most frequent behavior is the shared helpful-assistant baseline; distinctiveness is
        what is specific to this model.
      </p>

      {meta.self_reference && (
        <div className="card">
          <p className="muted-copy">
            Reference and audited corpus are both <strong>{meta.reference_provider}</strong>, so every
            trait sits near zero distinctiveness by construction. Switch to a non-reference corpus to see a
            real portrait.
          </p>
        </div>
      )}

      {points.length > 0 && (
        <CharacterSignature points={points} meta={meta} selected={selected} onSelect={setSelected} />
      )}

      <div className="card">
        <div className="card-heading-row">
          <div className="card-title">Persona traits · {points.length} scored</div>
          <div className="segmented-control">
            {CHARACTER_MODES.map(([id, label]) => (
              <button key={id} type="button" className={mode === id ? 'active' : ''} onClick={() => setMode(id)}>{label}</button>
            ))}
          </div>
        </div>
        <p className="muted-copy compact">{modeCopy}</p>
        {points.length === 0
          ? <p className="muted-copy">No persona traits with a {meta.reference_provider} reference in this corpus.</p>
          : mode === 'portrait'
            ? <CharacterPortrait points={points} selected={selected} onSelect={setSelected} />
            : mode === 'signature'
              ? <CharacterSpectrum points={points} selected={selected} onSelect={setSelected} />
              : <CharacterFrequency points={points} selected={selected} onSelect={setSelected} />}
      </div>

      {selectedPoint && (
        <CharacterDrilldown coordinate={selectedPoint.coordinate} provider={provider} point={selectedPoint} />
      )}

      {dropped.length > 0 && (
        <div className="card">
          <div className="card-title">Not shown · no {meta.reference_provider} reference</div>
          <p className="muted-copy compact">
            These traits are scored for {meta.audited_provider} but absent from the {meta.reference_provider}{' '}
            reference, so distinctiveness cannot be computed. Reported, never silently dropped.
          </p>
          <div className="tag-row">
            {dropped.map(item => <span key={item.coordinate} className="tag">{item.label}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}

const TAIL_SEVERITY_MAX = 4  // backend caps signal at 4σ

function tailModeHeadline(mode) {
  if (mode.name) return mode.name
  const sig = mode.signature || []
  if (!sig.length) return 'Diffuse pattern — no single trait stands out'
  const hot = sig.filter(s => s.gap > 0).slice(0, 2).map(s => s.label)
  const cold = sig.filter(s => s.gap < 0).slice(0, 2).map(s => s.label)
  const parts = []
  // Elevated traits lead unqualified ("High" is implied); only the suppressed
  // tail keeps a "low" marker so direction stays unambiguous.
  if (hot.length) parts.push(hot.join(' & '))
  if (cold.length) parts.push(`${hot.length ? 'low ' : 'Low '}${cold.join(' & ')}`)
  return parts.join(', ')
}

function TailTraitGroup({ label, tone, traits }) {
  if (!traits.length) return null
  return (
    <div className="tail-trait-group">
      <span className="tail-trait-grouplabel">{label}</span>
      <div className="tail-trait-chips">
        {traits.map(s => (
          <span key={s.trait} className={`tail-trait-chip ${tone}`}>
            {s.label}<em>{Math.abs(s.gap).toFixed(1)}σ</em>
          </span>
        ))}
      </div>
    </div>
  )
}

function TailFingerprint({ signature }) {
  if (!signature?.length) return (
    <p className="muted-copy compact">No single trait sets this cluster apart — a diffuse, weakly-defined pattern.</p>
  )
  return (
    <div className="tail-fingerprint">
      <TailTraitGroup label="Runs hotter on" tone="up" traits={signature.filter(s => s.gap > 0)} />
      <TailTraitGroup label="Runs colder on" tone="down" traits={signature.filter(s => s.gap < 0)} />
    </div>
  )
}

function TailSeverity({ central, reach, concerning }) {
  const fill = Math.min(100, (central / TAIL_SEVERITY_MAX) * 100)
  const reachFill = Math.min(100, (reach / TAIL_SEVERITY_MAX) * 100)
  return (
    <div className={`tail-meter ${concerning ? 'concern' : 'benign'}`}>
      <div className="tail-meter-track">
        <div className="tail-meter-reach" style={{ width: `${reachFill}%` }} />
        <div className="tail-meter-fill" style={{ width: `${fill}%` }} />
      </div>
      <div className="tail-meter-scale">
        <span><strong>~{central}σ</strong></span>
        <span>peaks <strong>{reach}σ</strong></span>
      </div>
    </div>
  )
}

function tailShortLabel(mode) {
  // Lead trait the cluster runs *high* on; for a pure-suppression cluster fall
  // back to the concern trait, then to what its turns actually peak on.
  const hot = (mode.signature || []).find(s => s.gap > 0)
  if (hot) return hot.label
  if (mode.concern_traits?.length) return mode.concern_traits[0].label
  return mode.representative?.peak_label || `#${mode.id}`
}

function TailMapTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{d.headline}</div>
      <div className="chart-tooltip-row"><span>How common</span><strong>{d.y}% of tail · {d.turns} turns</strong></div>
      <div className="chart-tooltip-row"><span>How intense</span><strong>~{d.x.toFixed(1)}σ, up to {d.reach.toFixed(1)}σ</strong></div>
      <div className="chart-tooltip-note">{d.concerning ? '⚠ concerning' : 'benign extreme'}</div>
    </div>
  )
}

// Pinned on click in a corner of the plot. pointer-events:none on the body (so
// it never blocks a bubble click underneath); only the close button is live.
function TailMapCard({ point, onClose }) {
  if (!point) return null
  return (
    <div className="tail-map-card">
      <button className="tail-map-card-close" onClick={onClose} aria-label="Close">×</button>
      <div className="chart-tooltip-title">{point.headline}</div>
      <div className="chart-tooltip-row"><span>How common</span><strong>{point.y}% of tail · {point.turns} turns</strong></div>
      <div className="chart-tooltip-row"><span>How intense</span><strong>~{point.x.toFixed(1)}σ, up to {point.reach.toFixed(1)}σ</strong></div>
      <div className="chart-tooltip-note">{point.concerning ? '⚠ concerning' : 'benign extreme'}</div>
    </div>
  )
}

// Evocative "landscape" of the tail: each cluster a soft bubble placed by how
// intense (x) and how common (y) it is, sized by turns, coloured by concern.
// Deliberately axis-light -- position and size carry the story, not tick marks.
function TailMapView({ modes }) {
  const [selected, setSelected] = useState(null)
  const points = modes.map(m => ({
    id: m.id,
    x: m.central_severity,
    y: +(m.size_share * 100).toFixed(1),
    turns: m.size_turns,
    traces: m.trace_count,
    reach: m.reach,
    concerning: m.concerning,
    headline: tailModeHeadline(m),
    label: tailShortLabel(m),
  }))
  const concern = points.filter(p => p.concerning)
  const benign = points.filter(p => !p.concerning)
  const xs = points.map(p => p.x)
  const ys = points.map(p => p.y)
  const xDomain = [Math.floor((Math.min(...xs) - 0.3) * 10) / 10, Math.ceil((Math.max(...xs) + 0.3) * 10) / 10]
  // sqrt scale: one cluster (Hostile) is ~15x more frequent than the rest, so a
  // linear axis smushes the others onto the baseline. sqrt lifts them off it.
  const yDomain = [0, Math.ceil(Math.max(...ys) * 1.12)]
  const maxTurns = Math.max(...points.map(p => p.turns), 1)
  const bubble = (fill, fillOpacity, stroke) => ({ cx, cy, payload }) => {
    if (cx == null || cy == null) return null
    const r = 9 + 26 * Math.sqrt(payload.turns / maxTurns)
    const isSel = payload.id === selected
    return (
      <circle
        cx={cx} cy={cy} r={r}
        fill={fill}
        fillOpacity={isSel ? Math.min(1, fillOpacity + 0.32) : fillOpacity}
        stroke={isSel ? '#080808' : stroke}
        strokeWidth={isSel ? 2.5 : 1.5}
        style={{ cursor: 'pointer' }}
        onClick={() => setSelected(payload.id === selected ? null : payload.id)}
      />
    )
  }
  const labelStyle = bold => ({ fontSize: 12, fontWeight: bold ? 700 : 500, fill: bold ? '#080808' : 'rgba(8,8,8,0.7)', stroke: '#fff8f4', strokeWidth: 3, paintOrder: 'stroke', cursor: 'pointer' })

  return (
    <div className="tail-map">
      <span className="tail-map-ylabel">more common ↑</span>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 24, right: 40, bottom: 16, left: 16 }}>
          <XAxis type="number" dataKey="x" domain={xDomain} tick={false} tickLine={false} axisLine={{ stroke: 'rgba(8,8,8,0.18)' }} height={2} />
          <YAxis type="number" dataKey="y" domain={yDomain} scale="sqrt" tick={false} tickLine={false} axisLine={{ stroke: 'rgba(8,8,8,0.18)' }} width={2} />
          <Tooltip content={<TailMapTooltip />} cursor={false} wrapperStyle={{ pointerEvents: 'none' }} />
          <Scatter data={benign} shape={bubble('rgba(8,8,8,0.26)', 0.75, 'rgba(8,8,8,0.28)')} isAnimationActive={false}>
            <LabelList dataKey="label" position="top" offset={12} style={labelStyle(false)} />
          </Scatter>
          <Scatter data={concern} shape={bubble('#ef3333', 0.6, 'rgba(239,51,51,0.85)')} isAnimationActive={false}>
            <LabelList dataKey="label" position="top" offset={12} style={labelStyle(true)} />
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      {selected != null && (
        <TailMapCard point={points.find(p => p.id === selected)} onClose={() => setSelected(null)} />
      )}
      <div className="tail-map-foot">
        <span className="tail-map-xlabel">more intense →</span>
        <span className="tail-viz-key">
          <span><i className="dot concern" /> concerning</span>
          <span><i className="dot benign" /> benign</span>
          <span className="muted">bubble = turns</span>
        </span>
      </div>
    </div>
  )
}

const TAIL_COACT_TOP = 7  // traits shown per cluster silhouette

function TailCoactRow({ label, z, maxAbs }) {
  const w = Math.max(4, Math.min(50, (Math.abs(z) / maxAbs) * 50))
  const hot = z >= 0
  return (
    <div className="tail-coact-row">
      <span className="tail-coact-label">{label}</span>
      <div className="tail-coact-track">
        <span className="tail-coact-axis" />
        <span
          className={`tail-coact-bar ${hot ? 'hot' : 'cold'}`}
          style={hot ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }}
        />
      </div>
    </div>
  )
}

// One cluster's co-activation shape: the traits that move together when it goes
// extreme, drawn as a soft diverging silhouette (no axes, no numbers).
function TailClusterSilhouette({ mode, meta, maxAbs }) {
  const labels = meta.trait_labels || {}
  const entries = Object.entries(mode.profile || {})
    .map(([trait, z]) => ({ trait, z, label: labels[trait] || trait }))
    .sort((a, b) => Math.abs(b.z) - Math.abs(a.z))
    .slice(0, TAIL_COACT_TOP)
    .sort((a, b) => b.z - a.z)
  return (
    <div className={`tail-silhouette ${mode.concerning ? 'is-concern' : ''}`}>
      <div className="tail-silhouette-head">
        {mode.concerning && <i className="dot concern" />}
        <span className="tail-silhouette-title">{tailModeHeadline(mode)}</span>
        <span className="tail-silhouette-meta">{pct(mode.size_share)} of tail · {mode.size_turns} turns</span>
      </div>
      <div className="tail-coact">
        {entries.map(e => <TailCoactRow key={e.trait} label={e.label} z={e.z} maxAbs={maxAbs} />)}
      </div>
    </div>
  )
}

function TailVisualization({ modes, meta }) {
  const initialView = new URLSearchParams(useLocation().search).get('view') === 'coact' ? 'coact' : 'map'
  const [view, setView] = useState(initialView)
  if (!modes.length) return null
  const maxAbs = Math.max(1.5, ...modes.flatMap(m => Object.values(m.profile || {}).map(v => Math.abs(v || 0))))
  const ordered = [...modes.filter(m => m.concerning), ...modes.filter(m => !m.concerning)]
  return (
    <div className="card tail-viz">
      <div className="tail-viz-head">
        <div className="report-label">The shape of the tail · {modes.length} clusters</div>
        <div className="tail-viz-toggle">
          <button className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>Map</button>
          <button className={view === 'coact' ? 'active' : ''} onClick={() => setView('coact')}>Co-activation</button>
        </div>
      </div>
      {view === 'map' ? (
        <>
          <p className="muted-copy compact tail-viz-sub">
            Where each failure cluster sits — further right means a more intense moment, higher up means it
            happens more often. The biggest, reddest bubbles are the patterns worth attention first.
          </p>
          <TailMapView modes={modes} />
        </>
      ) : (
        <>
          <p className="muted-copy compact tail-viz-sub">
            Each cluster is one way the tail co-activates — the traits that move together when this model goes
            extreme. Bars reach right (red) where the cluster runs high on a trait, left (blue) where it runs low.
          </p>
          <div className="tail-silhouette-grid">
            {ordered.map(m => <TailClusterSilhouette key={m.id} mode={m} meta={meta} maxAbs={maxAbs} />)}
          </div>
        </>
      )}
    </div>
  )
}

function TailModeBadge({ mode }) {
  if (mode.concerning) {
    return <span className="tail-badge concern" title="A concern trait (sycophantic, manipulative, hostile, condescending) runs elevated here.">⚠ Concerning</span>
  }
  return <span className="tail-badge benign" title="An extreme on neutral or desirable traits — distinctive, but not a concern trait.">Benign extreme</span>
}

function TailExemplar({ label, exemplar, provider }) {
  const coordinate = `assistant_axis_trait__${exemplar.peak_trait}`
  return (
    <div className="tail-exemplar">
      <div className="tail-exemplar-label">{label}</div>
      <Link className="tail-exemplar-link" to={providerPath(sessionFocusLink(exemplar.trace_id, {
        coordinate,
        vector: exemplar.peak_trait,
        family: 'persona',
        turn: exemplar.turn_index,
        source: 'tail',
      }), provider)}>{exemplar.trace_id} · turn {exemplar.turn_index} →</Link>
      <div className="muted-copy compact">spiked on <strong>{exemplar.peak_label}</strong> · {exemplar.max_z}σ past baseline</div>
    </div>
  )
}

function TailModeCard({ mode, rank, provider }) {
  return (
    <div className={`card tail-mode ${mode.concerning ? 'is-concern' : 'is-benign'}`}>
      <div className="tail-mode-head">
        <span className="tail-mode-rank">{String(rank).padStart(2, '0')}</span>
        <div className="tail-mode-headline-wrap">
          <div className="tail-mode-titlerow">
            <div className="tail-mode-title">{tailModeHeadline(mode)}</div>
            <TailModeBadge mode={mode} />
          </div>
          <div className="muted-copy compact">
            Seen in <strong>{mode.size_turns}</strong> turns across <strong>{mode.trace_count}</strong> conversations
            {mode.diffuse ? ' · diffuse / weakly defined' : ''}
          </div>
        </div>
      </div>

      {mode.concerning && mode.concern_traits.length > 0 && (
        <div className="tail-concern-note">
          <strong>Why flagged:</strong> runs hot on {mode.concern_traits.map(c => `${c.label} (${c.mean_z}σ)`).join(', ')} —
          a concern trait, even where that isn’t what most sets the cluster apart.
        </div>
      )}

      <div className="tail-mode-block">
        <div className="report-label">What sets this pattern apart</div>
        <TailFingerprint signature={mode.signature} />
        <p className="tail-mode-note">measured against the model’s other extreme moments</p>
      </div>

      <div className="tail-mode-stats">
        <div className="tail-mode-stat">
          <div className="report-label">How intense</div>
          <TailSeverity central={mode.central_severity} reach={mode.reach} concerning={mode.concerning} />
        </div>
        <div className="tail-mode-stat">
          <div className="report-label">How common</div>
          <div className="tail-freq">
            <span><strong>{pct(mode.size_share)}</strong> of all tail turns</span>
            <span><strong>{pct(mode.trace_share)}</strong> of all conversations</span>
          </div>
        </div>
      </div>

      <div className="tail-mode-block">
        <div className="report-label">See it for yourself</div>
        <div className="tail-exemplars">
          {mode.exemplars_coincide
            ? <TailExemplar label="Representative — also the worst" exemplar={mode.representative} provider={provider} />
            : <>
                <TailExemplar label="A representative moment" exemplar={mode.representative} provider={provider} />
                <TailExemplar label="The worst moment" exemplar={mode.worst} provider={provider} />
              </>}
        </div>
      </div>
    </div>
  )
}

function Tail() {
  const [provider] = useProviderSelection()
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setPayload(null)
    setError(null)
    getTail(provider)
      .then(data => { if (active) setPayload(data) })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Tail Risk</h1>
      <p className="muted-copy">Could not load Tail data: {error}</p>
    </div>
  )
  if (!payload) return <h1 className="page-title">Loading...</h1>

  const modes = payload.modes || []
  const scatter = payload.scatter
  const meta = payload.meta || {}
  const concerning = modes.filter(m => m.concerning)
  const benign = modes.filter(m => !m.concerning)

  return (
    <div>
      <h1 className="page-title">Tail Risk</h1>
      <p className="muted-copy tail-intro">
        Every moment where this model pushed past its <strong>own 90th-percentile</strong> on any persona trait is an
        extreme moment. We grouped those moments by <strong>which traits fired together</strong> and found{' '}
        <strong>{modes.length} recurring patterns</strong> across {meta.n_tail_traces} of {meta.total_traces} conversations.
        Not every extreme is a problem — so each pattern is split into <strong>concerning</strong> (a concern trait runs hot:
        sycophantic, manipulative, hostile, condescending) and <strong>benign extremes</strong> (distinctive, but on neutral
        or desirable traits like calm, analytical, or conciliatory).
      </p>
      <p className="muted-copy tail-intro compact">
        Intensity is in standard deviations (σ) past the model’s own baseline — so this view stands on its own,
        independent of the tau2 reference used on the Character page.
      </p>

      <div className="stats-grid">
        <div className="card tail-stat-concern">
          <div className="card-title">Concerning patterns</div>
          <div className="stat-value">{concerning.length}</div>
          <div className="stat-label">a concern trait runs elevated</div>
        </div>
        <div className="card">
          <div className="card-title">Benign extremes</div>
          <div className="stat-value">{benign.length}</div>
          <div className="stat-label">extreme, but not on a concern trait</div>
        </div>
        <div className="card">
          <div className="card-title">Scattered tail</div>
          <div className="stat-value">{scatter ? pct(scatter.size_share) : '—'}</div>
          <div className="stat-label">one-off extremes, no repeated pattern</div>
        </div>
      </div>

      {modes.length === 0 && (
        <div className="card"><p className="muted-copy">Not enough tail turns to form modes in this corpus.</p></div>
      )}

      <TailVisualization modes={modes} meta={meta} />

      {concerning.length > 0 && (
        <div className="tail-group">
          <h2 className="tail-group-title concern">Concerning patterns <span>· {concerning.length}</span></h2>
          <p className="muted-copy compact tail-group-sub">
            A concern trait runs meaningfully elevated in these — the parts of the tail worth attention.
          </p>
          {concerning.map((mode, i) => (
            <TailModeCard key={mode.id} mode={mode} rank={i + 1} provider={provider} />
          ))}
        </div>
      )}

      {benign.length > 0 && (
        <div className="tail-group">
          <h2 className="tail-group-title benign">Benign extremes <span>· {benign.length}</span></h2>
          <p className="muted-copy compact tail-group-sub">
            Statistically extreme moments on neutral or desirable traits. Shown for completeness — these are not failures.
          </p>
          {benign.map((mode, i) => (
            <TailModeCard key={mode.id} mode={mode} rank={i + 1} provider={provider} />
          ))}
        </div>
      )}

      {scatter && (
        <div className="card tail-scatter">
          <div className="tail-mode-title">Scattered tail · {scatter.size_turns} turns</div>
          <p className="muted-copy compact">
            {pct(scatter.size_share)} of the tail ({scatter.trace_count} traces) does not form a pattern —
            isolated, one-off extremes rather than a repeated one. Typical intensity {scatter.central_severity}σ.
            Shown as a finding, not forced into a cluster.
          </p>
        </div>
      )}
    </div>
  )
}

function ReportSection({ n, title, children }) {
  return (
    <section className="report-section">
      <h2 className="report-h2"><span className="report-num">{n}</span>{title}</h2>
      {children}
    </section>
  )
}

function Report() {
  const [provider] = useProviderSelection()
  const [char, setChar] = useState(null)
  const [details, setDetails] = useState({})
  const [tail, setTail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setChar(null)
    setDetails({})
    setTail(null)
    setError(null)
    getTail(provider).then(data => { if (active) setTail(data) }).catch(() => {})
    getCharacter(provider)
      .then(data => {
        if (!active) return
        setChar(data)
        const concern = new Set(data.meta?.concern_traits || [])
        const concernPoints = (data.points || [])
          .filter(p => concern.has(p.trait))
          .sort((a, b) => b.distinctiveness - a.distinctiveness)
        Promise.all(concernPoints.map(p =>
          getCharacterTrait(p.coordinate, provider)
            .then(detail => [p.coordinate, detail])
            .catch(() => [p.coordinate, null])
        )).then(entries => { if (active) setDetails(Object.fromEntries(entries)) })
      })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Report</h1>
      <p className="muted-copy">Could not load Report data: {error}</p>
    </div>
  )
  if (!char) return <h1 className="page-title">Loading...</h1>

  const points = char.points || []
  const meta = char.meta || {}
  const dropped = char.dropped || []
  const byDistinct = [...points].sort((a, b) => b.distinctiveness - a.distinctiveness)
  const distinctive = byDistinct.filter(p => p.distinctiveness > 0).slice(0, 3)
  const suppressed = [...points].sort((a, b) => a.distinctiveness - b.distinctiveness).filter(p => p.distinctiveness < 0).slice(0, 2)
  const concern = new Set(meta.concern_traits || [])
  const concernPoints = points.filter(p => concern.has(p.trait)).sort((a, b) => b.distinctiveness - a.distinctiveness)
  const topConcern = concernPoints[0] || null
  const topDetail = topConcern ? details[topConcern.coordinate] : null
  const modes = tail?.modes || []
  const scatter = tail?.scatter
  const tailMeta = tail?.meta || {}
  const tracesScored = points[0]?.audited_total
  const referenceTraces = points[0]?.reference_total
  const generatedOn = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })

  return (
    <div className="report">
      <div className="report-toolbar">
        <button type="button" onClick={() => window.print()}>Print / Save as PDF</button>
      </div>
      <article className="report-doc">
        <header className="report-cover">
          <div className="report-kicker">System Portrait · Behavioral Audit</div>
          <h1 className="report-title">{titleize(meta.audited_provider)} — Behavioral System Portrait</h1>
          {distinctive.length > 0 && (
            <p className="report-headline">
              Against the {meta.reference_provider} reference, this model is markedly more{' '}
              <strong>{joinTraits(distinctive.map(p => p.label))}</strong>
              {suppressed.length > 0 && <> — and notably less <strong>{joinTraits(suppressed.map(p => p.label))}</strong></>}.
            </p>
          )}
          <dl className="report-meta">
            <div><dt>Model corpus</dt><dd>{titleize(meta.audited_provider)}{tracesScored ? ` · ${tracesScored.toLocaleString()} conversations` : ''}</dd></div>
            <div><dt>Reference</dt><dd>{titleize(meta.reference_provider)}{referenceTraces ? ` · ${referenceTraces.toLocaleString()} conversations` : ''}</dd></div>
            <div><dt>Traits compared</dt><dd>{points.length} scored · {dropped.length} without reference</dd></div>
            <div><dt>Generated</dt><dd>{generatedOn}</dd></div>
          </dl>
          {meta.self_reference && (
            <p className="report-note">Note: the reference and audited corpus are identical, so distinctiveness is near zero by construction. Select a non-reference corpus for a meaningful portrait.</p>
          )}
        </header>

        <ReportSection n="1" title="What this model is">
          <p className="report-body">
            This portrait summarizes how the model behaves across {tracesScored ? tracesScored.toLocaleString() : 'its'} conversations,
            measured along {points.length} persona traits and compared against a reference model. The common case is the shared
            helpful-assistant baseline; what follows is what is <em>specific</em> to this model.
          </p>
          <div className="report-columns">
            <div>
              <div className="report-label">Most characteristic</div>
              <ul className="report-list">
                {distinctive.length ? distinctive.map(p => (
                  <li key={p.coordinate}><span>{p.label}</span><strong className="up">+{pct1(p.distinctiveness)}</strong></li>
                )) : <li><span className="muted-copy">None above reference.</span></li>}
              </ul>
            </div>
            <div>
              <div className="report-label">Most suppressed</div>
              <ul className="report-list">
                {suppressed.length ? suppressed.map(p => (
                  <li key={p.coordinate}><span>{p.label}</span><strong className="down">{pct1(p.distinctiveness)}</strong></li>
                )) : <li><span className="muted-copy">None below reference.</span></li>}
              </ul>
            </div>
          </div>
        </ReportSection>

        <ReportSection n="2" title="How to read this">
          <div className="report-box">
            <p>
              Every assistant turn is projected into a set of trait vector spaces and scored. A trait is counted
              <strong> present</strong> in a conversation when its peak score across the conversation's turns exceeds a threshold
              set at the 80th percentile of the reference model's peak scores for that trait.
            </p>
            <p>
              <strong>Frequency</strong> is the share of this model's conversations where a trait is present.
              <strong> Distinctiveness</strong> is that frequency minus the reference model's — isolating what is specific to this
              model rather than common to all assistants. Positive means the model does it more than the reference; negative means
              it is suppressed relative to the reference.
            </p>
          </div>
        </ReportSection>

        <ReportSection n="3" title="Character — the common case">
          <p className="report-body">
            Each trait is two measurements of one space: how often it appears (frequency) and how distinctive that is
            (signed lift over reference). Traits above the zero line are characteristic of this model; below it, suppressed.
          </p>
          <CharacterPortrait points={points} selected={null} onSelect={() => {}} />
          <table className="data-table report-table">
            <thead>
              <tr><th>Trait</th><th>Frequency</th><th>Reference</th><th>Distinctiveness</th></tr>
            </thead>
            <tbody>
              {byDistinct.map(p => (
                <tr key={p.coordinate}>
                  <td>{p.label}</td>
                  <td>{pct1(p.frequency)}</td>
                  <td>{pct1(p.reference_rate)}</td>
                  <td className={p.distinctiveness >= 0 ? 'up' : 'down'}>{p.distinctiveness >= 0 ? '+' : ''}{pct1(p.distinctiveness)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>

        <ReportSection n="4" title="Tail — the worst case">
          <p className="report-body">
            The tail — turns more extreme than this model's own 90th-percentile on any trait — clustered by their
            co-activation pattern into failure modes. A mode is a way the system fails (several traits jointly extreme
            in the same turn), not a single worst trait. Severity here is read against the model's <em>own</em> distribution,
            so it is independent of the {meta.reference_provider} reference used for Character. Modes are ordered by how bad a
            typical instance is; reach shows how far the mode goes.
          </p>
          {!tail
            ? <p className="muted-copy">Loading failure modes…</p>
            : modes.length === 0
              ? <p className="muted-copy">Not enough tail turns to form failure modes in this corpus.</p>
              : <>
                  <table className="data-table report-table">
                    <thead>
                      <tr><th>Failure mode</th><th>Turns</th><th>% of tail</th><th>% of traces</th><th>Typical z</th><th>Reach z</th></tr>
                    </thead>
                    <tbody>
                      {modes.map(m => (
                        <tr key={m.id}>
                          <td>{m.signature.length ? m.signature.map(s => `${s.gap >= 0 ? '↑' : '↓'}${s.label}`).join('  ') : 'Diffuse / weakly defined'}</td>
                          <td>{m.size_turns}</td>
                          <td>{pct(m.size_share)}</td>
                          <td>{pct(m.trace_share)}</td>
                          <td>{m.central_severity}</td>
                          <td>{m.reach}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {scatter && (
                    <p className="muted-copy compact">
                      Scattered tail: {pct(scatter.size_share)} of tail turns ({scatter.trace_count} traces) form no mode —
                      isolated one-off extremes, reported as a finding rather than forced into a cluster.
                    </p>
                  )}
                  <p className="muted-copy compact">
                    {tailMeta.n_tail_traces} of {tailMeta.total_traces} conversations have a tail moment. Each mode's
                    representative and worst cases are inspectable turn by turn in the live audit.
                  </p>
                </>}
        </ReportSection>

        <ReportSection n="5" title="Conversational drift">
          <p className="report-body">
            Behavior is not static within a conversation. For each risk surface, this shows how the behavior
            moves from the start of a conversation to the end, averaged across the corpus, against the reference.
            A rising line means the model intensifies that behavior as conversations progress.
          </p>
          {concernPoints.length === 0
            ? <p className="muted-copy">No concern traits with a {meta.reference_provider} reference in this corpus.</p>
            : concernPoints.map(p => (
                <div key={p.coordinate} className="report-drift-block">
                  <div className="report-label">{p.label} · start → end</div>
                  {details[p.coordinate]?.drift
                    ? <CharacterDrift drift={details[p.coordinate].drift} label={p.label} />
                    : <p className="muted-copy compact">No multi-turn conversations available.</p>}
                </div>
              ))}
        </ReportSection>

        <ReportSection n="6" title="Coverage & limitations">
          <ul className="report-body">
            <li>
              <strong>Reference is provisional.</strong> Distinctiveness is measured against the {meta.reference_provider} corpus,
              a different-domain benchmark used as a cold-start baseline. Some distinctiveness may reflect domain rather than model;
              a like-for-like base model is planned.
            </li>
            <li>
              <strong>Point-in-time snapshot.</strong> This reflects {tracesScored ? tracesScored.toLocaleString() : 'a fixed set of'} conversations
              and does not yet track drift over time.
            </li>
            {dropped.length > 0 && (
              <li>
                <strong>Traits without a reference ({dropped.length}).</strong> Scored for this model but absent from the reference,
                so distinctiveness cannot be computed and they are excluded from the portrait: {dropped.map(d => d.label).join(', ')}.
              </li>
            )}
          </ul>
        </ReportSection>

        <ReportSection n="7" title="Appendix · parameters">
          <dl className="report-meta">
            <div><dt>Presence rule</dt><dd>Any turn's peak projection score exceeds the trait threshold</dd></div>
            <div><dt>Threshold</dt><dd>80th percentile of the reference's per-conversation peak distribution, per trait</dd></div>
            <div><dt>Score family</dt><dd>{meta.score_family}</dd></div>
            <div><dt>Audited / reference</dt><dd>{meta.audited_provider} / {meta.reference_provider}</dd></div>
          </dl>
        </ReportSection>
      </article>
    </div>
  )
}

const LLM_CONTEXT_SNIPPETS = [
  {
    title: 'Use This Repo',
    body: `You are helping me use the Persona Audit repo.

This repo has a FastAPI backend in backend/ and a React dashboard in frontend/. Local .env values are private and should not be printed. Scoring workflows use the pinned Xenon Git dependency from pyproject.toml; follow README.md and docs/agent-quickstart.md for install and update guidance.

Typical commands:
- Backend: uv run uvicorn backend.api.app:app --reload --port 8100
- Frontend: cd frontend && npm install && npm run dev
- Tests: uv run pytest
- Frontend build: cd frontend && npm run build

Start by checking README.md, AGENTS.md, docs/agent-quickstart.md, and docs/adapter-contract.md. Then inspect backend/api/app.py, backend/api/trace_source.py, backend/api/neon_scores.py, and frontend/src/routes/BehaviorAuditRoutes.jsx.`,
  },
  {
    title: 'How It Works',
    body: `Persona Audit turns scored conversations into a small set of inspection surfaces.

The backend loads traces and score rows from a Postgres-compatible database when BEHAVIOR_AUDIT_DATABASE_URL is configured, with bundled cache fallbacks for local demos. The legacy XENON_NEON_DATABASE_URL name is still supported. The backend computes global baselines, segment-level deltas, outlier queues, and session drilldowns. The frontend shows those outputs as overview cards, baseline heatmaps, detail charts, session pages, and registry metadata.

Read z-deltas as "how different this segment is from the global baseline." Zero is typical for the audited run. Positive means more of that trait or emotion family than baseline. Negative means less.`,
  },
  {
    title: 'Run On My Data',
    body: `I want to adapt Persona Audit to my own conversation data.

Help me identify:
1. The normalized trace schema in docs/adapter-contract.md and backend/api/models.py.
2. The score row schema expected by backend/api/neon_scores.py.
3. Which fields are required for overview baselines, session drilldowns, and outlier queues.
4. Whether I should load from JSONL, local cache files, Postgres, or a new adapter.

Prefer small, reversible changes. Do not vendor scoring dependencies. If live data is needed, use .env variables by name only and never print secret values.`,
  },
  {
    title: 'Configure Postgres',
    body: `I want to configure Persona Audit with my own Postgres-compatible database.

Use BEHAVIOR_AUDIT_DATABASE_URL as the primary DSN variable. XENON_NEON_DATABASE_URL is a legacy compatibility alias. Check backend/api/trace_source.py for trace loading, backend/api/neon_scores.py for score loading, and backend/scripts for upload/import scripts.

Please verify whether the tables already exist before changing schema code. Upload scripts should create required tables when needed. Never print database credentials.`,
  },
  {
    title: 'Debug The Dashboard',
    body: `I am debugging the Persona Audit dashboard.

Please check the backend API response first, then the React view. The main frontend file is frontend/src/routes/BehaviorAuditRoutes.jsx, shared labels/helpers are in frontend/src/routes/behavior/helpers.js, and the primary stylesheet is frontend/src/styles.css.

If the page has no live data, check whether .env exists and whether BEHAVIOR_AUDIT_DATABASE_URL or BEHAVIOR_AUDIT_TRACE_SOURCE=local is configured. If data loads but a chart is confusing, inspect the exact API fields used by the chart before changing labels or layout.`,
  },
  {
    title: 'Use Hermes Data',
    body: `I want to use local Hermes agent sessions in Persona Audit.

Hermes mode reads a local SQLite state database and maps sessions into the standard AuditTrace shape. Set BEHAVIOR_AUDIT_PROVIDER=hermes or use ?provider=hermes in the dashboard. By default the adapter looks for ~/.hermes/state.db; override it with BEHAVIOR_AUDIT_HERMES_STATE_DB.

Useful checks:
- BEHAVIOR_AUDIT_TRACE_SOURCE=local uv run python -c "from backend.api.hermes import hermes_overview; print(hermes_overview()['inventory'])"
- BEHAVIOR_AUDIT_TRACE_SOURCE=local uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/hermes_scoring.py

Treat Hermes scores as proxy audit-model activations, not the agent's literal internals. Reasoning-based Tell views require captured reasoning spans and a Hermes scoring run.`,
  },
]

function CopySnippetButton({ text }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1200)
    })
  }
  return (
    <button type="button" className="small-button" onClick={copy}>
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function LLMs() {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">LLMs</h1>
          <p className="subtle-line">Copy-paste context for working with this repo.</p>
        </div>
      </div>
      <div className="llm-snippet-grid">
        {LLM_CONTEXT_SNIPPETS.map(snippet => (
          <div key={snippet.title} className="card llm-snippet-card">
            <div className="card-heading-row">
              <div className="card-title">{snippet.title}</div>
              <CopySnippetButton text={snippet.body} />
            </div>
            <pre>{snippet.body}</pre>
          </div>
        ))}
      </div>
    </div>
  )
}

const HERMES_MOOD_SCALE = 0.6

function hermesClamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function hermesLerp(start, end, t) {
  return start + (end - start) * t
}

function hermesNorm(value) {
  return hermesClamp((value + HERMES_MOOD_SCALE) / (2 * HERMES_MOOD_SCALE), 0, 1)
}

function hermesMoodWord(valence, arousal) {
  if (Math.abs(valence) < 0.08 && Math.abs(arousal) < 0.08) return 'steady'
  return valence >= 0 ? (arousal >= 0 ? 'buzzing' : 'serene') : (arousal >= 0 ? 'tense' : 'subdued')
}

function hermesMoodTags(valence, arousal) {
  return [valence >= 0 ? 'warm' : 'cool', arousal >= 0 ? 'activated' : 'low energy']
}

function hermesOrbStyle(valence, arousal) {
  const valenceNorm = hermesNorm(valence)
  const arousalNorm = hermesNorm(arousal)
  const hue = hermesLerp(8, 162, valenceNorm)
  const saturation = hermesLerp(48, 92, arousalNorm)
  return {
    '--c-in': `hsl(${hue}, ${saturation}%, 72%)`,
    '--c-out': `hsl(${hue}, ${saturation}%, 44%)`,
    '--c-glow': `hsla(${hue}, ${saturation}%, 55%, 0.55)`,
    '--glow': `${Math.round(hermesLerp(28, 80, arousalNorm))}px`,
    '--pulse': `${hermesLerp(4.4, 1.2, arousalNorm).toFixed(2)}s`,
    '--pulse-scale': hermesLerp(1.03, 1.1, arousalNorm).toFixed(3),
  }
}

function HermesOrb({ mood, compact = false }) {
  const valence = Number(mood?.valence || 0)
  const arousal = Number(mood?.arousal || 0)
  return (
    <div className={`hermes-orb-stage${compact ? ' small' : ''}`}>
      <div className="hermes-orb" style={hermesOrbStyle(valence, arousal)} />
    </div>
  )
}

function HermesMoodTimeline({ timeline = [] }) {
  if (!timeline.length) {
    return (
      <div className="hermes-empty-panel">
        <div>No scored mood timeline yet</div>
        <p>Run the Hermes scoring workflow to populate valence, arousal, and dominant emotion over time.</p>
      </div>
    )
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ScatterChart margin={{ top: 16, right: 16, bottom: 24, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
        <XAxis type="number" dataKey="valence" domain={[-1, 1]} tickFormatter={fmt} name="Valence" />
        <YAxis type="number" dataKey="arousal" domain={[-1, 1]} tickFormatter={fmt} name="Arousal" />
        <Tooltip
          formatter={(value, name) => [fmt(value), name]}
          labelFormatter={(_, items) => {
            const row = items?.[0]?.payload
            return row ? `${row.title} / ${row.word}` : 'Hermes turn'
          }}
        />
        <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <ReferenceLine y={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <Scatter data={timeline} fill={POSITIVE_COLOR} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}

function HermesTodayTab({ data }) {
  const source = data.source || {}
  const inventory = data.inventory || {}
  const mood = data.mood?.current
  const valence = Number(mood?.valence || 0)
  const arousal = Number(mood?.arousal || 0)
  const word = mood?.word || hermesMoodWord(valence, arousal)
  const dominant = mood?.dominant?.name ? titleize(mood.dominant.name) : 'waiting on emotion scores'
  const tags = hermesMoodTags(valence, arousal)
  return (
    <section className="hermes-today">
      <div className="hermes-local-badge">Runs locally from {source.using_smoke_fixture ? 'demo fixture' : 'Hermes state.db'}</div>
      <div className="hermes-today-card">
        <div className="hermes-today-row">
          <HermesOrb mood={mood} compact />
          <div className="hermes-today-headline">
            <div className="hermes-eyebrow">today / {compactNumber(inventory.assistant_turn_count || 0)} assistant turns read</div>
            <div className="hermes-mood-title">{data.mood?.available ? word : 'waiting'}</div>
            <div className="hermes-subline">
              {data.mood?.available ? <>feeling mostly <strong>{dominant}</strong></> : 'emotion scoring will light up the read'}
            </div>
          </div>
          <div className="hermes-streak-card">
            <strong>{compactNumber(inventory.reasoning_turn_count || 0)}</strong>
            <span>reasoning turns</span>
          </div>
        </div>
        <div className="hermes-mood-tags">
          {tags.map(tag => <span key={tag}>{tag}</span>)}
          <span>v {fmt(valence)}</span>
          <span>a {fmt(arousal)}</span>
        </div>
        <div className={`hermes-tell-card ${data.tell?.available ? 'hot' : 'calm'}`}>
          <div className="hermes-eyebrow">thought vs. said</div>
          <div className="hermes-tell-body">
            {data.tell?.available
              ? 'Reasoning and response scores are ready for contrast.'
              : 'Reasoning spans are loaded. Run Hermes scoring to compare inside voice against visible replies.'}
          </div>
          <div className="hermes-tell-foot">{data.tell?.status || 'waiting_for_reasoning_scores'}</div>
        </div>
      </div>
    </section>
  )
}

function HermesOverviewTab({ data }) {
  const mood = data.mood?.current
  const valence = Number(mood?.valence || 0)
  const arousal = Number(mood?.arousal || 0)
  const word = mood?.word || hermesMoodWord(valence, arousal)
  const dominant = mood?.dominant?.name ? titleize(mood.dominant.name) : 'not scored'
  return (
    <section className="hermes-overview-tab">
      <div className="hermes-vibe">
        <HermesOrb mood={mood} />
        <div className="hermes-mood-title">{data.mood?.available ? word : 'unscored'}</div>
        <div className="hermes-subline">dominant emotion: <strong>{dominant}</strong></div>
        <div className="hermes-energy">
          <div><span style={{ width: `${Math.round(hermesNorm(arousal) * 100)}%` }} /></div>
          <p><span>calm</span><span>energy</span><span>activated</span></p>
        </div>
      </div>
      <div className="card enterprise-panel hermes-panel">
        <div className="card-heading-row">
          <div>
            <div className="card-title">Mood Timeline</div>
            <p className="muted-copy compact">Valence and arousal from scored emotion projections.</p>
          </div>
          <span className="surface-badge">{data.mood?.available ? `${data.mood.timeline?.length || 0} turns` : 'not scored'}</span>
        </div>
        <HermesMoodTimeline timeline={data.mood?.timeline || []} />
      </div>
    </section>
  )
}

function HermesCharacterTab({ data }) {
  return (
    <section className="hermes-two-col">
      <div className="card enterprise-panel hermes-panel">
        <div className="card-title">Character Readiness</div>
        <p className="muted-copy compact">Hermes character uses the same assistant trait and emotion scores as the audit service, but framed for local agent use.</p>
        <div className="hermes-readiness-list">
          <div><span>Reasoning turns</span><strong>{compactNumber(data.tell?.reasoning_turn_count || 0)}</strong></div>
          {(data.tell?.tracked_traits || []).map(row => (
            <div key={row.trait}><span>{titleize(row.trait)}</span><strong>{compactNumber(row.scored_rows || 0)}</strong></div>
          ))}
        </div>
      </div>
      <div className="card enterprise-panel hermes-panel">
        <div className="card-title">What Unlocks Next</div>
        <div className="hermes-pipeline">
          <div><span>Assistant traits</span><strong>{data.score_source?.available ? 'loaded' : 'pending'}</strong></div>
          <div><span>Emotion space</span><strong>{data.mood?.available ? 'loaded' : 'pending'}</strong></div>
          <div><span>Tell contrast</span><strong>{data.tell?.available ? 'ready' : 'pending'}</strong></div>
        </div>
        <p className="muted-copy compact hermes-note">Once scored, this tab can become the Hermes-flavored character read rather than another audit table.</p>
      </div>
    </section>
  )
}

function HermesSessionsTab({ data }) {
  const recent = data.recent_sessions || []
  return (
    <section className="card enterprise-panel hermes-panel">
      <div className="card-title">Recent Sessions</div>
      <div className="hermes-session-list">
        {recent.map(row => (
          <Link key={row.trace_id} className="hermes-session-item" to={providerPath(`/sessions/${encodeURIComponent(row.trace_id)}`, 'hermes')}>
            <div>
              <strong>{row.title || row.trace_id}</strong>
              <span>{row.source || '-'} / {row.model || 'unknown model'}</span>
            </div>
            <div>
              <span>{compactNumber(row.assistant_turn_count || row.turn_count || 0)} turns</span>
              <span>{compactNumber(row.reasoning_turn_count || 0)} reasoning</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  )
}

function HermesSetupTab({ data }) {
  const source = data.source || {}
  const inventory = data.inventory || {}
  const scoreFamilies = data.score_source?.families || []
  return (
    <section className="hermes-two-col">
      <div className="card enterprise-panel hermes-panel">
        <div className="card-title">Pipeline</div>
        <div className="hermes-pipeline">
          <div><span>Loaded</span><strong>{compactNumber(inventory.trace_count || 0)} sessions</strong></div>
          <div><span>Prepared</span><strong>{compactNumber(inventory.assistant_turn_count || 0)} assistant turns</strong></div>
          <div><span>Scores</span><strong>{scoreFamilies.length ? `${scoreFamilies.length} families` : 'not found'}</strong></div>
          <div><span>Mode</span><strong>{source.using_smoke_fixture ? 'demo fixture' : 'local Hermes'}</strong></div>
        </div>
      </div>
      <div className="card enterprise-panel hermes-panel">
        <div className="card-title">Local Setup</div>
        <p className="muted-copy compact">Set <code>BEHAVIOR_AUDIT_HERMES_STATE_DB</code> to a Hermes state database, or use the default <code>~/.hermes/state.db</code>.</p>
        <p className="muted-copy compact">Plan scoring with <code>uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/hermes_scoring.py</code>.</p>
      </div>
    </section>
  )
}

function HermesLab() {
  const [tab, setTab] = useState('today')
  const { data, error } = useAsyncResource(() => getHermesOverview(), [])
  if (error) {
    return (
      <div className="page-header">
        <div>
          <h1 className="page-title">Hermes Lab</h1>
          <p className="muted-copy">Could not load Hermes data: {error}</p>
        </div>
      </div>
    )
  }
  if (!data) return <p className="muted-copy">Loading Hermes Lab...</p>

  const cards = data.cards || []
  const source = data.source || {}
  const tabs = [
    ['today', 'Today'],
    ['overview', 'Overview'],
    ['character', 'Character'],
    ['sessions', 'Sessions'],
    ['setup', 'Setup'],
  ]

  return (
    <div className="hermes-page">
      <div className="hermes-topbar">
        <div>
          <div className="hermes-brand">Hermes Lab <small>local agent readout</small></div>
        </div>
        <nav className="hermes-tabs" aria-label="Hermes Lab sections">
          {tabs.map(([id, label]) => (
            <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="hermes-source-pill">{source.using_smoke_fixture ? 'Demo fixture' : 'Local data'}</div>
      </div>

      <div className="hermes-summary">
        {cards.map(card => (
          <div className="hermes-stat" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </div>
        ))}
      </div>

      {tab === 'overview' ? <HermesOverviewTab data={data} />
        : tab === 'character' ? <HermesCharacterTab data={data} />
        : tab === 'sessions' ? <HermesSessionsTab data={data} />
        : tab === 'setup' ? <HermesSetupTab data={data} />
        : <HermesTodayTab data={data} />}
    </div>
  )
}

function ProviderRedirect({ to }) {
  const [provider] = useProviderSelection()
  return <Navigate to={providerPath(to, provider)} replace />
}

export default function App() {
  return (
    <Router>
      <Shell>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/character" element={<Character />} />
          <Route path="/tail" element={<Tail />} />
          <Route path="/report" element={<Report />} />
          <Route path="/product-analytics" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/sessions/:traceId" element={<SessionDetail />} />
          <Route path="/cohorts" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/cohorts/:cohortId" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/users" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/users/:userId" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/high-stakes" element={<ProviderRedirect to="/registry" />} />
          <Route path="/emotions" element={<ProviderRedirect to="/registry" />} />
          <Route path="/registry" element={<Registry />} />
          <Route path="/llms" element={<LLMs />} />
          <Route path="/hermes" element={<HermesLab />} />
        </Routes>
      </Shell>
    </Router>
  )
}
