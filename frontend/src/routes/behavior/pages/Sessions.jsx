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
import { useState } from 'react'

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

      <div className="card">
        <div className="card-title">
          Session Audit
          {showSignal && (
            <>
              {' '}
              <InfoHint text="Signal is the trace's strongest trait or emotion deviation from its segment baseline; z is how far (+ above, − below). Score aggregates every tracked vector into one deviation — the ranking key. Click a session to open it focused on its signal." />
            </>
          )}
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
              {showReward && <th className="num">{descriptor.reward_label || 'Reward'}</th>}
              <th className="num">Turns</th>
              <th>{taskLabel}</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map(session => (
              <tr key={session.trace_id}>
                <td><Link to={sessionLink(session, provider)}>{session.trace_id}</Link></td>
                {showSignal && <td>{session.signal?.vector ? deviationLabel(session.signal) : '-'}</td>}
                {showSignal && <td className="num">{session.signal?.vector ? fmt(session.signal.z) : '-'}</td>}
                {showSignal && <td className="num">{session.signal?.vector ? fmt(session.signal.outlier_score) : '-'}</td>}
                <td>{session.user_id}</td>
                {showDomain && <td>{session.domain}</td>}
                <td><RiskPill band={session.risk_band} /></td>
                {showReward && <td className="num">{fmt(session.reward)}</td>}
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
