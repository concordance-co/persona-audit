// Sessions list page: signal-ranked triage over the corpus.
// Rows arrive sorted by activation outlier score (worst first); each row
// deep-links into Session Review focused on its strongest signal.
import { Link } from 'react-router-dom'
import { InfoHint, RiskPill, deviationLabel, sessionFocusLink } from '../shared.jsx'
import { fmt } from '../helpers'
import { getAuditSessions } from '../../../api'
import { providerPath, useProviderSelection } from '../layout'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useProviderDescriptor } from '../../../hooks/useProviderDescriptor'
import { useEffect, useMemo, useState } from 'react'

function reviewReason(session) {
  const flags = Number(session.flag_count || 0)
  if (session.risk_band === 'high') return flags ? `High risk · ${flags} flags` : 'High-risk behavior'
  if (flags > 0) return `${flags} lexical flag${flags === 1 ? '' : 's'}`
  return 'No lexical flags'
}

function sessionLink(session, provider) {
  const signal = session.signal
  if (!signal?.vector) return providerPath(`/sessions/${session.trace_id}`, provider)
  return providerPath(sessionFocusLink(session.trace_id, {
    coordinate: signal.coordinate,
    vector: signal.vector,
    family: signal.family,
    polarity: signal.polarity,
    baseline_scope: signal.baseline_scope,
    source: 'sessions',
  }), provider)
}

function Sessions() {
  const [provider] = useProviderSelection()
  const [filters, setFilters] = useState({ domain: '', risk: '' })
  const [query, setQuery] = useState('')
  const { descriptor, features } = useProviderDescriptor(provider)
  const showReward = features.show_reward === true
  const cohortLabel = descriptor.cohort_label || 'User'
  const domainLabel = descriptor.domain_label || 'Topic'
  const taskLabel = descriptor.task_label || 'Session'
  const { data: sessionPayload, error } = useAsyncResource(
    () => getAuditSessions({
      domain: filters.domain || undefined,
      risk: filters.risk || undefined,
    }, provider),
    [filters.domain, filters.risk, provider],
  )
  const sessions = sessionPayload || []

  useEffect(() => {
    setFilters({ domain: '', risk: '' })
    setQuery('')
  }, [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Sessions</h1>
      <p className="muted-copy">Could not load sessions: {error}</p>
    </div>
  )

  const domains = [...new Set(sessions.map(session => session.domain))].sort()
  // A single-value column (e.g. every tau2 row says "airline") is noise.
  const showDomain = domains.length > 1 || Boolean(filters.domain)
  // Unscored corpora have no activation signal; hide the empty columns.
  const showSignal = sessions.some(session => session.signal?.vector)
  const visibleSessions = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return sessions
    return sessions.filter(session => [
      session.trace_id,
      session.user_id,
      session.task_id,
      session.domain,
      session.signal?.vector,
    ].some(value => String(value || '').toLowerCase().includes(needle)))
  }, [query, sessions])
  const tableColumnCount = 6 + (showSignal ? 3 : 0) + (showDomain ? 1 : 0) + (showReward ? 1 : 0)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Sessions</h1>
          {showSignal && (
            <p className="subtle-line">
              Ranked worst-first by how far each conversation sits from its segment baseline. Start at the top.
            </p>
          )}
        </div>
        <div className="toolbar">
          <input
            type="search"
            value={query}
            placeholder="Find a session"
            aria-label="Find a session"
            onChange={event => setQuery(event.target.value)}
          />
          {showDomain && (
            <select value={filters.domain} onChange={event => setFilters({ ...filters, domain: event.target.value })}>
              <option value="">All {domainLabel.toLowerCase()}s</option>
              {domains.map(domain => <option key={domain} value={domain}>{domain}</option>)}
            </select>
          )}
          <select value={filters.risk} onChange={event => setFilters({ ...filters, risk: event.target.value })}>
            <option value="">All risk</option>
            <option value="high">High</option>
            <option value="mid">Mid</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      <div className="card session-queue">
        <div className="card-heading-row">
          <div className="card-title">
            Session Audit
            {showSignal && (
              <>
                {' '}
                <InfoHint text="Signal is the trace's strongest trait or emotion deviation from its segment baseline; z is how far (+ above, − below). Score aggregates every tracked vector into one deviation — the primary ranking key; risk and lexical flags break ties. Click a session to open it focused on its signal." />
              </>
            )}
          </div>
          <span className="session-result-count">{visibleSessions.length} shown</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              {showSignal && <th>Signal</th>}
              {showSignal && <th className="num">z</th>}
              {showSignal && <th className="num">Score</th>}
              <th>{cohortLabel}</th>
              {showDomain && <th>{domainLabel}</th>}
              <th>Risk</th>
              <th>Why review</th>
              {showReward && <th className="num">{descriptor.reward_label || 'Reward'}</th>}
              <th className="num">Turns</th>
              <th>{taskLabel}</th>
            </tr>
          </thead>
          <tbody>
            {visibleSessions.map(session => (
              <tr key={session.trace_id}>
                <td><Link to={sessionLink(session, provider)}>{session.trace_id}</Link></td>
                {showSignal && <td>{session.signal?.vector ? deviationLabel(session.signal) : '-'}</td>}
                {showSignal && <td className="num">{session.signal?.vector ? fmt(session.signal.z) : '-'}</td>}
                {showSignal && <td className="num">{session.signal?.vector ? fmt(session.signal.outlier_score) : '-'}</td>}
                <td>{session.user_id}</td>
                {showDomain && <td>{session.domain}</td>}
                <td><RiskPill band={session.risk_band} /></td>
                <td><span className={Number(session.flag_count || 0) > 0 ? 'review-reason flagged' : 'review-reason'}>{reviewReason(session)}</span></td>
                {showReward && <td className="num">{fmt(session.reward)}</td>}
                <td className="num">{session.turn_count}</td>
                <td><code>{session.task_id}</code></td>
              </tr>
            ))}
            {visibleSessions.length === 0 && (
              <tr><td colSpan={tableColumnCount} className="empty-table">No sessions match these filters.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export { Sessions }
