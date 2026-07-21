// Overview chart components (baseline heatmap, outlier previews).
import { CHART_GRID_COLOR, fmt } from './helpers'
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Fragment } from 'react'
import { InfoHint, actionLabel, deviationLabel, rowsByGroupAndVector, sessionFocusLink, topVectorsByDelta, vectorLabel, zColor, zValue } from './shared.jsx'
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

function BaselineHeatmap({ title, badge, description, rows = [], vectors = [], groupKey = 'workflow', groupLabel = value => value, groupHeader = 'Segment', expanded = false, onExpanded }) {
  // Columns with no data anywhere are noise, not signal — skip them.
  const scoredVectors = new Set(rows.map(row => row.vector))
  const candidateVectors = vectors.filter(vector => scoredVectors.has(vector))
  const visibleVectors = expanded ? candidateVectors : topVectorsByDelta(rows, candidateVectors, 5)
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
        </div>
        {onExpanded && candidateVectors.length > visibleVectors.length && (
          <button type="button" className="small-button" onClick={() => onExpanded(!expanded)}>
            {expanded ? 'Top 5' : `Show all ${candidateVectors.length}`}
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

export { BaselineHeatmap, OutlierTraceChart, PersonaMetric }
