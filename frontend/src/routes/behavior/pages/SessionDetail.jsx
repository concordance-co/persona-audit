// Session detail page.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { ComparableBaselinePanel, EmotionSpectrumVisualizer, ProductContextPanel, SelectedSignalTimeline, SessionAnalyticsGrid, SessionInvestigationHeader, SessionTrajectoryChart, SignalEvidencePanel, Tau2Badge, selectedSessionSignal, selectedTurnEvidence } from '../panels.jsx'
import { buildProjectionTailThresholds, buildTurnAxisRows, fmt } from '../helpers'
import { deviationLabel } from '../shared.jsx'
import { getAuditSession } from '../../../api'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useLocation, useParams } from 'react-router'
import { useEffect, useMemo, useState } from 'react'
import { useProviderSelection } from '../layout'

function SessionDetail() {
  const [provider] = useProviderSelection()
  const { traceId } = useParams()
  const location = useLocation()
  const { data: payload, error } = useAsyncResource(() => getAuditSession(traceId, provider), [traceId, provider])
  const searchParams = new URLSearchParams(location.search)
  const analytics = payload?.session_analytics || {}
  const defaultSelectedSignal = selectedSessionSignal(analytics, searchParams)
  const [selectedVectors, setSelectedVectors] = useState([])
  useEffect(() => {
    setSelectedVectors(defaultSelectedSignal?.vector ? [defaultSelectedSignal.vector] : [])
  }, [traceId, provider, defaultSelectedSignal?.vector])

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
  const focusedCoordinate = searchParams.get('coordinate') || ''
  const focusedTurn = searchParams.get('turn')
  const signalOptions = analytics.vector_deviations || []
  const activeVectors = selectedVectors.length
    ? selectedVectors
    : (defaultSelectedSignal?.vector ? [defaultSelectedSignal.vector] : [])
  const selectedSignals = activeVectors
    .map(vector => {
      const params = new URLSearchParams(location.search)
      params.set('vector', vector)
      params.delete('coordinate')
      return selectedSessionSignal(analytics, params)
    })
    .filter(Boolean)
  const selectedSignal = selectedSignals[0] || defaultSelectedSignal
  const selectedCoordinate = selectedSignal?.coordinate || focusedCoordinate
  const turnEvidenceByVector = new Map(selectedSignals.map(selected => [
    selected.vector,
    new Map(
      selectedTurnEvidence(analytics.turn_deviations || [], selected.vector)
        .map(row => [Number(row.turn_index), row]),
    ),
  ]))
  const addSignal = vector => {
    if (!vector || activeVectors.includes(vector)) return
    setSelectedVectors([...activeVectors, vector].slice(0, 6))
  }
  const removeSignal = vector => {
    if (activeVectors.length <= 1) return
    setSelectedVectors(activeVectors.filter(item => item !== vector))
  }
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

      <div className="card signal-comparison-card">
        <div className="card-heading-row trajectory-heading">
          <div>
            <div className="card-title">Compare Signals</div>
            <p className="muted-copy compact">Select up to six persona or emotion coordinates. The same selection drives the z-score trajectory and the evidence shown beside each conversation turn.</p>
            <div className="axis-chip-row">
              {selectedSignals.map((selected, index) => (
                <button
                  key={selected.vector}
                  className="axis-chip"
                  type="button"
                  onClick={() => removeSignal(selected.vector)}
                  disabled={selectedSignals.length <= 1}
                  aria-label={`Remove ${deviationLabel({ vector: selected.vector, z: selected.z })}`}
                >
                  <span className={selected.z < 0 ? 'comparison-dot-low' : 'comparison-dot-high'} />
                  {deviationLabel({ vector: selected.vector, z: selected.z })} · z {fmt(selected.z)}
                </button>
              ))}
            </div>
          </div>
          <div className="trajectory-controls">
            <select value="" onChange={event => addSignal(event.target.value)} aria-label="Add signal">
              <option value="">Add signal</option>
              {signalOptions
                .filter(row => !activeVectors.includes(row.vector))
                .map(row => <option key={row.vector} value={row.vector}>{row.family === 'emotion_cluster' ? 'Emotion' : 'Persona'} · {row.vector.replaceAll('_', ' ')}</option>)}
            </select>
          </div>
        </div>
      </div>

      <SessionInvestigationHeader trace={trace} selected={selectedSignal} />

      <div className="chart-row three-col session-evidence-grid">
        <SignalEvidencePanel selected={selectedSignal} />
        <ComparableBaselinePanel selected={selectedSignal} />
        <ProductContextPanel trace={trace} />
      </div>

      <div className="chart-row">
        <SelectedSignalTimeline selectedSignals={selectedSignals} turnRows={analytics.turn_deviations || []} />
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
              const projectionChips = selectedSignals.flatMap(selected => {
                const signal = turnEvidenceByVector.get(selected.vector)?.get(Number(turn.index))?.signal
                return signal
                  ? [{
                      id: `${turn.index}-${selected.vector}`,
                      tone: Number(signal.z || 0) < 0 ? 'low' : 'high',
                      label: deviationLabel({ vector: selected.vector, z: signal.z, polarity: signal.polarity }),
                      value: signal.z,
                    }]
                  : []
              })
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
