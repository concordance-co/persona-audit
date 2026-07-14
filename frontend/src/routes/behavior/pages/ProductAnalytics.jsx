// Product analytics page (Report tab data view).
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { BaselineHeatmap, GlobalBaselineStrip } from '../charts.jsx'
import { CohortExplorerPanel, InvestigationQueue, ProductStateCards, SegmentQueuePanel, TraitDetailChart, TurnLengthPanel } from '../panels.jsx'
import { EMOTION_VECTOR_KEYS, PERSONA_VECTOR_KEYS, familyTitle, fmt, pct, topRows } from '../helpers'
import { actionLabel, compactNumber, segmentLabel, taskGroupLabel, vectorLabel } from '../shared.jsx'
import { getAuditSessions, getAuditUsers, getProductAnalytics } from '../../../api'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useProviderSelection } from '../layout'
import { useState } from 'react'

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
              <span className="stat-label">Cells with n&ge;10 only; {compactNumber(hiddenMatrixRows)} smaller cells hidden to keep the first read clean.</span>
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

export { ProductAnalytics }
