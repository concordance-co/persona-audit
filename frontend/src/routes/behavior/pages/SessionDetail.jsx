// Session detail page.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { ComparableBaselinePanel, EmotionSpectrumVisualizer, ProductContextPanel, SelectedSignalTimeline, SessionAnalyticsGrid, SessionInvestigationHeader, SessionTrajectoryChart, SignalEvidencePanel, Tau2Badge, selectedSessionSignal, selectedTurnEvidence } from '../panels.jsx'
import { buildProjectionTailThresholds, buildTurnAxisRows, fmt } from '../helpers'
import { deviationLabel } from '../shared.jsx'
import { getAuditSession } from '../../../api'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useLocation, useParams } from 'react-router-dom'
import { useMemo } from 'react'
import { useProviderSelection } from '../layout'

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

export { SessionDetail }
