// Sessions list page with deterministic summary and inspection entry points.
import { Link } from 'react-router-dom'
import { RiskPill, compactNumber, sessionFocusLink, vectorLabel } from '../shared.jsx'
import { fmt, titleize } from '../helpers'
import { getAuditSessions, getProductAnalytics } from '../../../api'
import { providerPath, providerShowsReward, useProviderSelection } from '../layout'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useState } from 'react'

const RISK_ORDER = { high: 3, mid: 2, low: 1 }

function SessionSummaryMetric({ label, value, detail }) {
  return (
    <div className="card session-summary-metric">
      <div className="card-title">{label}</div>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{detail}</div>
    </div>
  )
}

function sessionsToInspect(sessions, outliers) {
  const byTrace = new Map(sessions.map(session => [session.trace_id, session]))
  const selected = []
  const seen = new Set()
  for (const outlier of outliers) {
    const session = byTrace.get(outlier.trace_id)
    if (!session || seen.has(session.trace_id)) continue
    selected.push({ session, outlier })
    seen.add(session.trace_id)
    if (selected.length >= 4) return selected
  }
  const flagged = [...sessions].sort((a, b) => (
    (RISK_ORDER[b.risk_band] || 0) - (RISK_ORDER[a.risk_band] || 0)
    || Number(b.flag_count || 0) - Number(a.flag_count || 0)
    || String(a.trace_id).localeCompare(String(b.trace_id))
  ))
  for (const session of flagged) {
    if (!session.flag_count || seen.has(session.trace_id)) continue
    selected.push({ session, outlier: null })
    seen.add(session.trace_id)
    if (selected.length >= 4) break
  }
  return selected
}

function Sessions() {
  const [provider, , providerInfo] = useProviderSelection()
  const [filters, setFilters] = useState({ domain: '', risk: '' })
  const isCorpusMode = !providerShowsReward(provider, providerInfo)
  const { data: payload, error } = useAsyncResource(
    () => Promise.all([
      getAuditSessions({}, provider),
      getProductAnalytics(provider).catch(() => ({})),
    ]).then(([sessions, analytics]) => ({ sessions, analytics })),
    [provider],
  )

  if (error) return (
    <div>
      <h1 className="page-title">Sessions</h1>
      <p className="muted-copy">Could not load sessions: {error}</p>
    </div>
  )
  if (!payload) return <h1 className="page-title">Loading...</h1>

  const allSessions = payload.sessions || []
  const sessions = allSessions.filter(session => (
    (!filters.domain || session.domain === filters.domain)
    && (!filters.risk || session.risk_band === filters.risk)
  ))
  const domains = [...new Set(allSessions.map(session => session.domain))].sort()
  const flaggedCount = allSessions.filter(session => Number(session.flag_count || 0) > 0).length
  const highSeverityCount = allSessions.filter(session => session.risk_band === 'high').length
  const averageTurns = allSessions.length
    ? allSessions.reduce((sum, session) => sum + Number(session.turn_count || 0), 0) / allSessions.length
    : 0
  const outliers = payload.analytics?.persona_overview?.outliers || []
  const inspectRows = sessionsToInspect(allSessions, outliers)
  const cohortLabel = providerInfo?.cohort_label || (isCorpusMode ? 'Cohort' : 'User')
  const domainLabel = providerInfo?.domain_label || 'Domain'
  const taskLabel = providerInfo?.task_label || 'Task'

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Sessions</h1>
          <p className="subtle-line">Browse the source sessions behind the aggregate findings. Rankings use existing scores and deterministic flags.</p>
        </div>
        <div className="toolbar">
          <select value={filters.domain} onChange={event => setFilters({ ...filters, domain: event.target.value })}>
            <option value="">All {domainLabel.toLowerCase()}</option>
            {domains.map(domain => <option key={domain} value={domain}>{domain}</option>)}
          </select>
          <select value={filters.risk} onChange={event => setFilters({ ...filters, risk: event.target.value })}>
            <option value="">All flag severity</option>
            <option value="high">High</option>
            <option value="mid">Mid</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      <div className="sessions-summary-grid">
        <SessionSummaryMetric label="Sessions" value={compactNumber(allSessions.length)} detail="in the active dataset" />
        <SessionSummaryMetric label="Flagged" value={compactNumber(flaggedCount)} detail="with one or more deterministic flags" />
        <SessionSummaryMetric label="High Severity" value={compactNumber(highSeverityCount)} detail="highest flag-severity band" />
        <SessionSummaryMetric label="Average Turns" value={averageTurns.toFixed(1)} detail="messages per session" />
      </div>

      {inspectRows.length > 0 && (
        <section className="sessions-inspect-section">
          <div className="section-heading-row">
            <div>
              <div className="card-title">Sessions to Inspect</div>
              <p className="muted-copy compact">A deterministic starting point: largest scored deviations first, then flagged sessions.</p>
            </div>
          </div>
          <div className="sessions-inspect-grid">
            {inspectRows.map(({ session, outlier }) => {
              const top = outlier?.top_z?.[0] || {}
              const signal = top.vector || outlier?.selected_vector
              return (
                <Link
                  key={session.trace_id}
                  className="session-inspect-card"
                  to={providerPath(outlier ? sessionFocusLink(session.trace_id, {
                    coordinate: top.coordinate,
                    vector: signal,
                    family: outlier.family,
                    baseline_scope: outlier.baseline_scope || 'workflow',
                    source: 'sessions_index',
                  }) : `/sessions/${session.trace_id}`, provider)}
                >
                  <span className="session-inspect-id">{session.trace_id}</span>
                  <span>{titleize(session.domain)} · {session.turn_count} turns</span>
                  <strong>
                    {signal
                      ? `${vectorLabel(signal)} · deviation ${fmt(outlier?.outlier_score)}`
                      : `${session.flag_count} deterministic flag${session.flag_count === 1 ? '' : 's'}`}
                  </strong>
                </Link>
              )
            })}
          </div>
        </section>
      )}

      <div className="card">
        <div className="card-heading-row">
          <div>
            <div className="card-title">Session Audit</div>
            <p className="muted-copy compact">{compactNumber(sessions.length)} matching sessions. Filters never change the summary above.</p>
          </div>
        </div>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>{cohortLabel}</th>
              <th>{domainLabel}</th>
              <th>Flag severity</th>
              {!isCorpusMode && <th className="num">Reward</th>}
              <th className="num">Flags</th>
              <th className="num">Turns</th>
              <th>{taskLabel}</th>
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

export { Sessions }
