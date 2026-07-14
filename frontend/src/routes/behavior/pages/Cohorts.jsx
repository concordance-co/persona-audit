// Cohorts, cohort detail, and high-stakes pages.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { FALLBACK_SIGNAL_COLOR, SIGNAL_COLORS, evalLabelTitle, fmt } from '../helpers'
import { Link, useParams } from 'react-router-dom'
import { RiskPill } from '../shared.jsx'
import { getAuditUser, getAuditUsers, getHighStakesReports } from '../../../api'
import { providerPath, providerShowsReward, useProviderSelection } from '../layout'
import { useEffect, useState } from 'react'

function Cohorts() {
  const [provider] = useProviderSelection()
  const [users, setUsers] = useState([])

  useEffect(() => {
    getAuditUsers(provider).then(setUsers)
  }, [provider])

  const isCorpusMode = !providerShowsReward(provider)

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

export { CohortDetail, Cohorts, HighStakes }
