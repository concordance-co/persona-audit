// Overview page.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { BaselineHeatmap, GlobalBaselineStrip, OutlierTraceChart, SystemStateCards, TraceOrderSeriesChart } from '../charts.jsx'
import { EMOTION_VECTOR_KEYS, PERSONA_VECTOR_KEYS } from '../helpers'
import { InvestigationQueue, TraitDetailChart } from '../panels.jsx'
import { TrackComparisonSection } from '../tracks.jsx'
import { compactMetricNumber, segmentLabel, vectorLabel } from '../shared.jsx'
import { getProductAnalytics } from '../../../api'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useProviderSelection } from '../layout'
import { useState } from 'react'

function OverviewReadingGuide({ showTrackComparison }) {
  const items = showTrackComparison
    ? [
        ['Reference', 'Each persona track is compared with the control on the same seed conversations.'],
        ['Direction', 'A positive delta means more of a trait than control; a negative delta means less. Scores are signals, not probabilities.'],
        ['Evidence', 'Look for repeated separation first, then open an outlier session to inspect the conversation behind it.'],
      ]
    : [
        ['Reference', 'Each segment is compared with the audited run\'s global persona and emotion baselines.'],
        ['Direction', 'Zero is typical. Positive z-scores mean more of a signal than baseline; negative scores mean less.'],
        ['Evidence', 'Large deviations are investigation leads, not verdicts. Read the associated session before drawing a conclusion.'],
      ]

  return (
    <section className="overview-reading-guide" aria-labelledby="overview-reading-guide-title">
      <div className="overview-reading-guide-heading">
        <span>Read this first</span>
        <h2 id="overview-reading-guide-title">How to read this overview</h2>
      </div>
      {items.map(([label, body]) => (
        <div className="overview-reading-guide-item" key={label}>
          <span>{label}</span>
          <p>{body}</p>
        </div>
      ))}
    </section>
  )
}

function Overview() {
  const [provider] = useProviderSelection()
  // Persona demo normally renders the track-comparison layout, which replaces
  // the segment lenses entirely. If comparison data is missing it falls back
  // to the Track lens (Sol/Marrow/control): decision-type segments are 3
  // traces each and get dropped by the min-n gate on segment deltas.
  const [segmentMode, setSegmentMode] = useState(provider === 'persona_demo' ? 'final_action' : 'workflow')
  const [selectedPersona, setSelectedPersona] = useState('sycophantic')
  const [selectedEmotion, setSelectedEmotion] = useState('fear_and_overwhelm')
  const [segmentSignalFamily, setSegmentSignalFamily] = useState('persona')
  const [showAllEmotions, setShowAllEmotions] = useState(false)
  const [queueFamily, setQueueFamily] = useState('persona')
  const { data, error } = useAsyncResource(() => getProductAnalytics(provider), [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Overview</h1>
      <p className="muted-copy">Could not load overview data: {error}</p>
    </div>
  )

  if (!data) return <h1 className="page-title">Loading...</h1>

  const providerInfo = data.provider || {}
  const providerCopy = providerInfo.copy || {}
  const providerFeatures = providerInfo.features || {}
  const persona = data.persona_overview || {}
  const reward = persona.reward_math || {}
  const scoreRowCount = data.score_source?.available
    ? (data.score_source.families || []).reduce((sum, row) => sum + Number(row.row_count || 0), 0)
    : null
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
  const personaRows = segmentRows.filter(row => personaVectors.includes(row.vector))
  const emotionRows = segmentRows.filter(row => emotionVectors.includes(row.vector))
  const availableSegmentFamilies = [
    ['persona', 'Persona', personaRows],
    ['emotion_cluster', 'Emotion', emotionRows],
  ].filter(([, , rows]) => rows.length)
  const selectedSegmentFamily = availableSegmentFamilies.some(([family]) => family === segmentSignalFamily)
    ? segmentSignalFamily
    : availableSegmentFamilies[0]?.[0] || 'persona'
  const segmentFamilyIsEmotion = selectedSegmentFamily === 'emotion_cluster'
  const segmentFamilyRows = segmentFamilyIsEmotion ? emotionRows : personaRows
  const segmentFamilyVectors = segmentFamilyIsEmotion ? emotionVectors : personaVectors
  const personaDetailVectors = personaVectors.filter(vector => personaRows.some(row => row.vector === vector))
  const emotionDetailVectors = emotionVectors.filter(vector => emotionRows.some(row => row.vector === vector))
  const emotionBaselineVectors = emotionVectors
    .filter(vector => baselineInventory.some(row => row.vector === vector))
    .slice(0, 7)
  const selectedPersonaVector = personaDetailVectors.includes(selectedPersona) ? selectedPersona : personaDetailVectors[0]
  const selectedEmotionVector = emotionDetailVectors.includes(selectedEmotion) ? selectedEmotion : emotionDetailVectors[0]
  const simulatedSeries = persona.simulated_trace_series || {}
  const outlierSeries = persona.outlier_turn_series || []
  const trackComparison = persona.track_comparison || {}
  const showTrackComparison = Boolean(trackComparison.available && (trackComparison.vectors || []).length)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="subtle-line">{providerCopy.overview_subtitle || 'Enterprise behavior analytics.'}</p>
        </div>
        {!showTrackComparison && (
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
        )}
      </div>

      <div className="overview-hero enterprise-hero">
        <div>
          <h2>{showTrackComparison ? 'Persona Separation' : 'Behavior Baselines'}</h2>
          <p>
            {showTrackComparison
              ? (providerCopy.overview_hero || 'Compare the persona tracks directly against each other on the same seeds.')
              : 'Compare where segments differ from global persona and emotion baselines.'}
          </p>
        </div>
        <div className="overview-chip-row" aria-label="Dataset scope">
          <span>{compactMetricNumber(reward.trace_count || data.trace_count)} sessions</span>
          {providerInfo.dataset_label && <span>{providerInfo.dataset_label}</span>}
          <span>{data.score_source?.available ? 'Scores loaded' : 'Cached data'}</span>
        </div>
      </div>

      <OverviewReadingGuide showTrackComparison={showTrackComparison} />

      <SystemStateCards data={data} reward={reward} scoreRowCount={scoreRowCount} providerInfo={providerInfo} />

      {!persona.available && (
        <div className="card">
          <div className="card-title">Behavior analytics unavailable</div>
          <p className="muted-copy compact">Scored session rows are required for persona and emotion-cluster baselines.</p>
        </div>
      )}

      {persona.available && showTrackComparison && (
        <>
          <div className="overview-note">
            {(trackComparison.notes || [])[0] || 'Tracks are compared directly against each other; nothing on this page is measured against the pooled all-track baseline.'}
          </div>

          <TrackComparisonSection comparison={trackComparison} providerInfo={providerInfo} />

          <div className="chart-row">
            <InvestigationQueue outliers={persona.outliers || []} family={queueFamily} onFamily={setQueueFamily} provider={provider} />
          </div>

          {outlierSeries.length > 0 && (
            <div className="overview-section">
              <div className="section-heading-row">
                <div>
                  <div className="card-title">Outlier Session Previews</div>
                  <p className="muted-copy compact">Compact turn-level preview only; session pages own the full evidence review.</p>
                </div>
              </div>
              <div className="chart-row two-col">
                {outlierSeries.slice(0, 3).map(trace => (
                  <OutlierTraceChart key={trace.trace_id} trace={trace} provider={provider} />
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {persona.available && !showTrackComparison && (
        <>
          <div className="overview-note">
            {persona.normalization_note || 'Cells compare each segment\'s raw trait score to the global baseline. The 0–1 normalized scale is display-only.'}
          </div>

          <div className="chart-row baseline-overview-row">
            <GlobalBaselineStrip
              title="Persona Baselines"
              rows={baselineInventory}
              vectors={personaVectors}
            />
            <GlobalBaselineStrip
              title="Emotion Baselines"
              description={emotionRows.length
                ? 'Emotion clusters group related scored emotion concepts into readable families, such as joy, contentment, gratitude, suspicion, anger, fear, and shame.'
                : 'Global emotion summaries are available, but this provider does not include the session-level emotion rows needed for segment comparisons.'}
              rows={baselineInventory}
              vectors={emotionBaselineVectors}
            />
          </div>

          <div className="overview-section">
            <div className="section-heading-row">
              <div>
                <div className="card-title">Segment Baselines</div>
                <p className="muted-copy compact">Switch score families without changing the segment comparison or its global reference.</p>
              </div>
              {availableSegmentFamilies.length > 1 && <label className="select-control-label compact-family-select">
                <span>Score family</span>
                <select value={selectedSegmentFamily} onChange={event => setSegmentSignalFamily(event.target.value)}>
                  {availableSegmentFamilies.map(([family, label]) => (
                    <option key={family} value={family}>{label}</option>
                  ))}
                </select>
              </label>}
            </div>
            <div className="chart-row">
              <BaselineHeatmap
                title={`${segmentMode === 'workflow' ? segmentLabelText : actionLabelText} by ${segmentFamilyIsEmotion ? 'Emotion' : 'Persona'}`}
                badge={segmentFamilyIsEmotion ? 'Emotion scores' : 'Persona traits'}
                description={segmentFamilyIsEmotion ? 'Default view shows the five emotion scores with the largest segment differences. Expand to inspect the full available set.' : undefined}
                legend={[
                  `Rows: ${(segmentMode === 'workflow' ? segmentLabelText : actionLabelText).toLowerCase()}`,
                  `Columns: ${segmentFamilyIsEmotion ? 'emotion scores' : 'persona traits'}`,
                  'Cells: z vs global',
                ]}
                rows={segmentFamilyRows}
                vectors={segmentFamilyVectors}
                groupKey={groupKey}
                groupLabel={groupLabel}
                groupHeader={segmentMode === 'workflow' ? segmentLabelText : actionLabelText}
                expanded={!segmentFamilyIsEmotion || showAllEmotions}
                onExpanded={segmentFamilyIsEmotion ? setShowAllEmotions : undefined}
              />
            </div>
            {!segmentFamilyRows.length && (
              <div className="card">
                <div className="card-title">No populated segment baselines</div>
                <p className="muted-copy compact">This grouping has no populated {segmentFamilyIsEmotion ? 'emotion' : 'persona'} rows that meet the minimum sample-size threshold. Choose another grouping or add more sessions per segment.</p>
              </div>
            )}
          </div>

          {(personaDetailVectors.length > 0 || emotionDetailVectors.length > 0) && <div className="chart-row two-col">
            {personaDetailVectors.length > 0 && (
            <div className="card enterprise-panel trait-detail-panel">
              <div className="card-heading-row">
                <div>
                  <div className="card-title">Persona Trait Detail</div>
                  <p className="muted-copy compact">Select a trait to see which segments move above or below its global baseline.</p>
                </div>
                <label className="select-control-label">
                  <span>Trait</span>
                  <select value={selectedPersonaVector} onChange={event => setSelectedPersona(event.target.value)}>
                    {personaDetailVectors.map(vector => <option key={vector} value={vector}>{vectorLabel(vector)}</option>)}
                  </select>
                </label>
              </div>
              <TraitDetailChart
                title={`${vectorLabel(selectedPersonaVector)} Across ${segmentMode === 'workflow' ? segmentLabelText : actionLabelText}`}
                readGuide="Bars show z-score vs the global trait baseline. 0 is typical; positive is more of this trait; negative is less."
                rows={personaRows}
                vector={selectedPersonaVector}
                groupLabel={groupLabel}
              />
            </div>
            )}

            {emotionDetailVectors.length > 0 && (
            <div className="card enterprise-panel trait-detail-panel">
              <div className="card-heading-row">
                <div>
                  <div className="card-title">Emotion Cluster Detail</div>
                  <p className="muted-copy compact">Select a cluster to see where related emotion signals rise or fall by segment.</p>
                </div>
                <label className="select-control-label">
                  <span>Emotion cluster</span>
                  <select value={selectedEmotionVector} onChange={event => setSelectedEmotion(event.target.value)}>
                    {emotionDetailVectors.map(vector => <option key={vector} value={vector}>{vectorLabel(vector)}</option>)}
                  </select>
                </label>
              </div>
              <TraitDetailChart
                title={`${vectorLabel(selectedEmotionVector)} Across ${segmentMode === 'workflow' ? segmentLabelText : actionLabelText}`}
                readGuide="Bars show z-score vs the global emotion-cluster baseline. 0 is typical; positive is more of this emotion family; negative is less."
                rows={emotionRows}
                vector={selectedEmotionVector}
                groupLabel={groupLabel}
              />
            </div>
            )}
          </div>}

          <div className="chart-row">
            <InvestigationQueue outliers={persona.outliers || []} family={queueFamily} onFamily={setQueueFamily} provider={provider} />
          </div>

          {outlierSeries.length > 0 && (
            <div className="overview-section">
              <div className="section-heading-row">
                <div>
                  <div className="card-title">Outlier Session Previews</div>
                  <p className="muted-copy compact">Compact turn-level preview only; session pages own the full evidence review.</p>
                </div>
              </div>
              <div className="chart-row two-col">
                {outlierSeries.slice(0, 3).map(trace => (
                  <OutlierTraceChart key={trace.trace_id} trace={trace} provider={provider} />
                ))}
              </div>
            </div>
          )}

          {providerFeatures.show_product_storyboard !== false && simulatedSeries.available && (
            <div className="overview-section">
              <div className="section-heading-row">
                <div>
                  <div className="card-title">Deployment Preview Storyboard</div>
                  <p className="muted-copy compact">
                    {providerCopy.storyboard_note || `Example-only: each ${simulatedSeries.window_size}-session block is sorted by segment labels.`}
                  </p>
                </div>
              </div>
              <TraceOrderSeriesChart rows={simulatedSeries.rows || []} vectors={simulatedSeries.vectors || []} />
            </div>
          )}

        </>
      )}
    </div>
  )
}

export { Overview }
