// Analytics + session drilldown panels (investigation queue, session cards).
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { CHART_GRID_COLOR, CHART_ZERO_COLOR, EMOTION_CLUSTER_BY_CONCEPT, EMOTION_SPECTRUM_X_AXIS_STEP, HIGHLIGHT_COLOR, NEGATIVE_COLOR, POSITIVE_COLOR, average, axisIdForCoordinate, buildCoordinateTrajectoryRows, buildEmotionSpectrumData, buildSessionProjectionDistributions, coordinateTitle, defaultTrajectoryCoordinates, emotionConceptKey, evalLabelTitle, familyTitle, fmt, groupByValue, pct, pct1, smoothLinePath, trajectoryCoordinateOptions } from './helpers'
import { Link } from 'react-router-dom'
import { PersonaMetric } from './charts.jsx'
import { InfoHint, actionLabel, clamp01, compactNumber, deviationLabel, scopeLabel, sessionFocusLink, taskGroupLabel, vectorLabel, zValue } from './shared.jsx'
import { providerPath } from './layout'
import { useEffect, useMemo, useState } from 'react'

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
      <div className="card-title">
        {title}{' '}
        <InfoHint text={readGuide || 'Bars show z-score vs global baseline. 0 is typical; positive is higher than baseline; negative is lower.'} />
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
  // A family toggle with an empty side is noise; so is a Family column when
  // every visible row would say the same thing.
  const bothFamilies = counts.persona > 0 && counts.emotion_cluster > 0
  const filtered = outliers.filter(row => {
    if (!bothFamilies || family === 'all') return true
    return row.family === family
  })
  return (
    <div className="card enterprise-panel">
      <div className="card-heading-row">
        <div>
          <div className="card-title">
            Investigation Queue{' '}
            <InfoHint text="Primary z is how far the named trait sits from its baseline for this trace (+ above, − below). Aggregate combines every tracked trait in that workflow into one overall deviation. Sorted by largest aggregate. Click a trace to inspect the signal turn by turn." />
          </div>
        </div>
        {bothFamilies && (
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
        )}
      </div>
      <table>
        <thead>
          <tr>
            <th>Trace</th>
            <th>Segment</th>
            {bothFamilies && <th>Family</th>}
            <th>Primary signal</th>
            <th className="num">Primary z</th>
            <th className="num">Aggregate</th>
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
                {bothFamilies && <td>{row.family === 'emotion_cluster' ? 'Emotion' : 'Persona'}</td>}
                <td>{deviationLabel(top)}</td>
                <td className="num">{fmt(top.z)}</td>
                <td className="num">{fmt(row.outlier_score)}</td>
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
      <p className="muted-copy compact">Ranked by failures weighted by how often the segment runs. Behavior evidence is the segment's strongest trait deviation from baseline.</p>
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
          Compared against {baseline.label || scopeLabel(selected.baselineScope)}. Primary z {fmt(selected.z)} is how far this trace sits from that baseline; the aggregate score stays on the queue.
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
      <p className="muted-copy compact">How far {vectorLabel(selected.vector)} sits from baseline at each turn. Zero is the baseline for turns at a similar length and position.</p>
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

export { CohortExplorerPanel, ComparableBaselinePanel, EmotionSpectrumVisualizer, InvestigationQueue, ProductContextPanel, ProductStateCards, SegmentQueuePanel, SelectedSignalTimeline, SessionAnalyticsGrid, SessionEmotionClusterCard, SessionExpectedDeviationCard, SessionGlobalFitCard, SessionInvestigationHeader, SessionProjectionDistributionCard, SessionTrajectoryChart, SignalEvidencePanel, Tau2Badge, TraitDetailChart, TurnLengthPanel, cohortSummaryRows, resolveSessionScope, selectedSessionSignal, selectedTurnEvidence, sessionSetStats, topSegmentEvidence }
