// Overview/system chart components (baselines, trace-order series, outliers).
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { CHART_GRID_COLOR, EMOTION_VECTOR_KEYS, PERSONA_VECTOR_KEYS, fmt } from './helpers'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Fragment, useState } from 'react'
import { InfoHint, actionLabel, compactMetricNumber, compactNumber, deltaColor, deviationLabel, emotionClusterDetail, rowsByGroupAndVector, sessionFocusLink, topVectorsByDelta, vectorLabel, zColor, zValue } from './shared.jsx'
import { Link } from 'react-router-dom'
import { providerPath } from './layout'

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
      <p className="muted-copy compact">Example only: traces grouped by Tau2 task label, to preview how production monitoring would look. The jumps between blocks come from the grouping, not from real drift.</p>
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

export { BaselineHeatmap, GlobalBaselineStrip, OutlierTraceChart, PersonaMetric, SystemStateCards, TraceOrderSeriesChart }
