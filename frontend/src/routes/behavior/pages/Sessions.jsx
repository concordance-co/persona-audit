// Sessions list page.
import { Link } from 'react-router-dom'
import { RiskPill } from '../shared.jsx'
import { fmt } from '../helpers'
import { getAuditSessions } from '../../../api'
import { providerPath, useProviderSelection } from '../layout'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useProviderDescriptor } from '../../../hooks/useProviderDescriptor'
import { useState } from 'react'

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

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Sessions</h1>
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
        <div className="card-title">Session Audit</div>
        <table>
          <thead>
            <tr>
              <th>Session</th>
              <th>{cohortLabel}</th>
              {showDomain && <th>{domainLabel}</th>}
              <th>Risk</th>
              {showReward && <th className="num">{descriptor.reward_label || 'Reward'}</th>}
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
                {showDomain && <td>{session.domain}</td>}
                <td><RiskPill band={session.risk_band} /></td>
                {showReward && <td className="num">{fmt(session.reward)}</td>}
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
