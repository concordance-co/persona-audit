// Overview page: findings first, instruments second.
// Opens with a strip of plain-language findings composed from the same
// cached payloads the deep-dive pages read (character signature, tail
// clusters, outlier queue, dataset exemplar), then the baseline heatmaps
// and triage queue. See docs/internal/focus-group.md for the rationale.
import { BaselineHeatmap, OutlierTraceChart } from '../charts.jsx'
import { EMOTION_VECTOR_KEYS, PERSONA_VECTOR_KEYS, fmt, pct } from '../helpers'
import { InvestigationQueue, TraitDetailChart } from '../panels.jsx'
import { Link } from 'react-router-dom'
import { TrackComparisonSection, trackTitle } from '../tracks.jsx'
import { InfoHint, ModeSwitch, compactMetricNumber, deviationLabel, segmentLabel, sessionFocusLink, vectorLabel } from '../shared.jsx'
import { joinTraits, signatureSummary, trackSignatureSummary } from './Character.jsx'
import { tailModeHeadline } from './Tail.jsx'
import { getCharacter, getProductAnalytics, getTail } from '../../../api'
import { providerPath, useProviderSelection } from '../layout'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useEffect, useState } from 'react'

// One promoted lead finding (the dataset's exemplar) plus at most three
// compact cards — headline hierarchy, not headline overload.
function FindingCard({ finding, lead = false }) {
  const className = `card finding-card${lead ? ' lead' : ''}`
  const body = (
    <>
      <div>
        <div className="finding-kicker">{finding.kicker}</div>
        <p className="finding-text">{finding.body}</p>
        {finding.metric && <div className="finding-metric">{finding.metric}</div>}
      </div>
      {lead && finding.cta && <span className="finding-cta">{finding.cta} <span aria-hidden="true">→</span></span>}
    </>
  )
  if (finding.to) return <Link className={className} to={finding.to}>{body}</Link>
  return <button type="button" className={className} onClick={finding.onClick}>{body}</button>
}

// One finding per deep-dive page, each composed with the same helpers those
// pages use, so the strip and the destination always agree. Builders return
// plain objects so the render step can promote the provider's exemplar.
function characterFinding(char, provider) {
  if (!char) return null
  const meta = char.meta || {}
  const trackReports = char.track_reports || []
  if ((meta.tracks || []).length && trackReports.length) {
    const parts = trackReports
      .map(report => ({ track: trackTitle(report.track), higher: trackSignatureSummary(report).higher.slice(0, 2) }))
      .filter(part => part.higher.length)
    if (!parts.length) return null
    return {
      key: 'character',
      kicker: 'Character',
      metric: 'vs control on the same seeds',
      to: providerPath('/character', provider),
      cta: 'Compare persona character',
      body: parts.map((part, index) => (
        <span key={part.track}>
          {index > 0 && ' '}
          <strong>{part.track}</strong> adds {joinTraits(part.higher.map(p => p.label))}.
        </span>
      )),
    }
  }
  if (meta.self_reference) return null
  const { distinctive, suppressed } = signatureSummary(char.points || [])
  if (!distinctive.length) return null
  return {
    key: 'character',
    kicker: 'Character',
    metric: `vs ${meta.reference_provider} reference`,
    to: providerPath('/character', provider),
    cta: 'Open Character',
    body: (
      <>
        Markedly more <strong>{joinTraits(distinctive.map(p => p.label))}</strong>
        {suppressed.length > 0 && <> — and less {joinTraits(suppressed.map(p => p.label))}</>}.
      </>
    ),
  }
}

function tailFinding(tail, provider) {
  const modes = tail?.modes || []
  if (!modes.length) return null
  const concerning = modes.filter(mode => mode.concerning)
  const lead = concerning[0] || modes[0]
  return {
    key: 'tail',
    kicker: 'Tail risk',
    metric: `${modes.length} extreme patterns · ${concerning.length} concerning`,
    to: providerPath('/tail', provider),
    cta: 'Inspect the tail',
    body: (
      <>
        {concerning.length ? 'Worst recurring pattern: ' : 'Most common extreme: '}
        <strong>{tailModeHeadline(lead)}</strong>.
      </>
    ),
  }
}

function triageFinding(outliers, provider) {
  const row = (outliers || [])[0]
  const top = row?.top_z?.[0]
  if (!row || !top) return null
  const link = providerPath(sessionFocusLink(row.trace_id, {
    coordinate: top.coordinate,
    vector: top.vector,
    family: row.family,
    polarity: top.polarity,
    baseline_scope: row.baseline_scope || 'workflow',
    source: 'overview_findings',
  }), provider)
  return {
    key: 'triage',
    kicker: 'Start reading',
    metric: `aggregate score ${fmt(row.outlier_score)}`,
    to: link,
    cta: 'Open the session',
    body: (
      <>
        <strong>{row.trace_id}</strong> is the strongest outlier: {deviationLabel(top)}, {fmt(top.z)}σ from its segment baseline.
      </>
    ),
  }
}

function separationFinding(comparison, provider) {
  const lead = (comparison?.vectors || [])[0]
  const eta = Number(lead?.eta_squared)
  if (!lead || !Number.isFinite(eta)) return null
  return {
    key: 'separation',
    kicker: 'Persona separation',
    metric: `η² ${fmt(eta)}`,
    to: providerPath('/character', provider),
    cta: 'Compare persona character',
    body: (
      <>
        Which persona is speaking explains <strong>{pct(eta)}</strong> of the spread in {vectorLabel(lead.vector)} — the section below compares the tracks trait by trait.
      </>
    ),
  }
}

function outcomeFinding(rows) {
  const lead = (rows || [])[0]
  if (!lead) return null
  const more = Number(lead.delta_fail_minus_pass) > 0
  return {
    key: 'outcome',
    kicker: 'Outcome link',
    metric: `Cohen's d ${fmt(Math.abs(Number(lead.cohen_d_fail_vs_pass)))}`,
    onClick: () => document.getElementById('outcome-behavior')?.scrollIntoView({ behavior: 'smooth' }),
    cta: 'See outcome coupling',
    body: (
      <>
        Failed <strong>{segmentLabel(lead.workflow, 'workflow')}</strong> sessions read {more ? 'more' : 'less'}{' '}
        <strong>{vectorLabel(lead.vector)}</strong> than passing ones.
      </>
    ),
  }
}

// Which finding leads for each dataset — its exemplar, the thing this seed
// uniquely demonstrates. Everything else renders as a compact card (max 3).
const LEAD_FINDING_BY_PROVIDER = { persona_demo: 'separation', tau2: 'outcome', hermes: 'character' }

// The tau2 exemplar: the computed-but-previously-hidden coupling between
// behavior and task outcome. Only renders when a corpus carries rewards.
function OutcomeBehaviorCard({ rows, segmentLabelText }) {
  if (!rows?.length) return null
  return (
    <div className="card enterprise-panel" id="outcome-behavior">
      <div className="card-heading-row">
        <div>
          <div className="card-title">
            Outcome ↔ Behavior{' '}
            <InfoHint text="Cohen's d of each trait's raw score, failed sessions minus passing ones, within a segment (segments need at least 4 of each). Positive means the trait reads stronger when the task fails. A coupling worth investigating, not a causal claim." />
          </div>
          <p className="muted-copy compact">
            Where behavior separates failing sessions from passing ones, per {segmentLabelText.toLowerCase()}.
          </p>
        </div>
      </div>
      <table>
        <thead>
          <tr>
            <th>{segmentLabelText}</th>
            <th>Trait</th>
            <th>Read</th>
            <th className="num">d (fail − pass)</th>
            <th className="num">n fail / pass</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 6).map(row => (
            <tr key={`${row.workflow}-${row.vector}`}>
              <td>{segmentLabel(row.workflow, 'workflow')}</td>
              <td>{vectorLabel(row.vector)}</td>
              <td>{Number(row.delta_fail_minus_pass) > 0 ? 'stronger in failures' : 'weaker in failures'}</td>
              <td className="num">{fmt(row.cohen_d_fail_vs_pass)}</td>
              <td className="num">{row.n_fail} / {row.n_pass}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Overview() {
  const [provider] = useProviderSelection()
  // Persona demo defaults to the Track segment lens (Sol/Marrow/control):
  // its decision-type segments are 3 traces each and get dropped by the
  // min-n gate on segment deltas.
  const [segmentMode, setSegmentMode] = useState(provider === 'persona_demo' ? 'final_action' : 'workflow')
  // Approved exception to the shared-defaults rule (July 2026 focus-group
  // merge): the persona demo leads with its paired-track separation view —
  // the one thing that corpus uniquely demonstrates. Every other dataset
  // lands on Behavior Baselines, and the mode stays visible everywhere.
  const [viewMode, setViewMode] = useState(provider === 'persona_demo' ? 'separation' : 'baselines')
  const [selectedTrait, setSelectedTrait] = useState('sycophantic')
  const [showAllEmotions, setShowAllEmotions] = useState(false)
  const [queueFamily, setQueueFamily] = useState('persona')
  // Provider switches don't remount this page, so the per-provider defaults
  // must be re-applied when the lens changes.
  useEffect(() => {
    setSegmentMode(provider === 'persona_demo' ? 'final_action' : 'workflow')
    setViewMode(provider === 'persona_demo' ? 'separation' : 'baselines')
  }, [provider])
  const { data, error } = useAsyncResource(() => getProductAnalytics(provider), [provider])
  // Character and Tail are cached server-side; their headlines feed the
  // findings strip. A failure here only hides the strip's card.
  const { data: characterData } = useAsyncResource(() => getCharacter(provider), [provider])
  const { data: tailData } = useAsyncResource(() => getTail(provider), [provider])

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
  const personaVectors = (persona.persona_vectors || PERSONA_VECTOR_KEYS).filter(vector => PERSONA_VECTOR_KEYS.includes(vector))
  const emotionVectors = (persona.emotion_cluster_vectors || EMOTION_VECTOR_KEYS).filter(vector => EMOTION_VECTOR_KEYS.includes(vector))
  const segmentRows = segmentMode === 'final_action'
    ? (persona.action_vector_deltas || [])
    : (persona.workflow_vector_deltas || [])
  const groupKey = segmentMode === 'final_action' ? 'final_action' : 'workflow'
  const groupLabel = value => segmentLabel(value, groupKey)
  const segmentLabelText = providerInfo.segment_label || 'Task'
  const actionLabelText = providerInfo.action_label || 'Final Action'
  const personaRows = segmentRows.filter(row => personaVectors.includes(row.vector))
  const emotionRows = segmentRows.filter(row => emotionVectors.includes(row.vector))
  // Offer only vectors that actually have segment rows; a dropdown of dead
  // options in front of an empty chart is noise.
  const personaDetailVectors = personaVectors.filter(vector => personaRows.some(row => row.vector === vector))
  const emotionDetailVectors = emotionVectors.filter(vector => emotionRows.some(row => row.vector === vector))
  const detailVectors = [...personaDetailVectors, ...emotionDetailVectors]
  const activeTrait = detailVectors.includes(selectedTrait) ? selectedTrait : detailVectors[0]
  const activeTraitRows = personaDetailVectors.includes(activeTrait) ? personaRows : emotionRows
  const outlierSeries = persona.outlier_turn_series || []
  const trackComparison = persona.track_comparison || {}
  const separationAvailable = providerFeatures.show_track_comparison !== false
    && Boolean(trackComparison.available && (trackComparison.vectors || []).length)
  const outcomeRows = providerFeatures.show_pass_rate === false ? [] : (persona.workflow_outcome_deltas || [])
  const viewModes = [
    {
      id: 'separation',
      label: 'Persona separation',
      disabled: !separationAvailable,
      disabledHint: 'Persona separation needs paired persona tracks answering the same seeds — the Persona demo lens ships Sol, Marrow, and control over 25 shared seeds.',
    },
    { id: 'baselines', label: 'Behavior baselines', disabled: false },
  ]
  const activeView = separationAvailable && viewMode === 'separation' ? 'separation' : 'baselines'

  const findings = [
    characterFinding(characterData, provider),
    tailFinding(tailData, provider),
    separationAvailable ? separationFinding(trackComparison, provider) : null,
    outcomeFinding(outcomeRows),
    triageFinding(persona.outliers, provider),
  ].filter(Boolean)
  const leadFinding = findings.find(finding => finding.key === LEAD_FINDING_BY_PROVIDER[provider]) || findings[0]
  const compactFindings = findings.filter(finding => finding !== leadFinding).slice(0, 3)

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Overview</h1>
          <p className="subtle-line">{providerCopy.overview_subtitle || 'Enterprise behavior analytics.'}</p>
        </div>
        <div className="page-header-controls">
          <ModeSwitch modes={viewModes} value={activeView} onChange={setViewMode} />
          {activeView === 'baselines' && (
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
      </div>

      {leadFinding && (
        <div className="findings-strip" aria-label="What stands out">
          <FindingCard finding={leadFinding} lead />
          {compactFindings.length > 0 && (
            <div className="findings-grid">
              {compactFindings.map(finding => <FindingCard key={finding.key} finding={finding} />)}
            </div>
          )}
        </div>
      )}

      <div className="overview-hero enterprise-hero">
        <div>
          <h2>{activeView === 'separation' ? 'Persona Separation' : 'Behavior Baselines'}</h2>
          <p>
            {activeView === 'separation'
              ? (providerCopy.overview_hero || 'Compare the persona tracks directly against each other on the same seeds.')
              : 'Compare where segments differ from global persona and emotion baselines.'}
          </p>
        </div>
        <div className="overview-chip-row" aria-label="Dataset scope">
          <span>{compactMetricNumber(reward.trace_count || data.trace_count)} traces</span>
          {reward.assistant_turn_count != null && <span>{compactMetricNumber(reward.assistant_turn_count)} turns</span>}
          {providerInfo.dataset_label && <span>{providerInfo.dataset_label}</span>}
          <span>{data.score_source?.available ? 'Scores loaded' : 'Cached data'}</span>
        </div>
      </div>

      {!persona.available && (
        <div className="card">
          <div className="card-title">Behavior analytics unavailable</div>
          <p className="muted-copy compact">Scored session rows are required for persona and emotion-cluster baselines.</p>
        </div>
      )}

      {persona.available && activeView === 'separation' && (
        <>
          <div className="overview-note">
            {(trackComparison.notes || [])[0] || 'Tracks are compared directly against each other; nothing on this page is measured against the pooled all-track baseline.'}
          </div>

          <TrackComparisonSection comparison={trackComparison} providerInfo={providerInfo} />
        </>
      )}

      {persona.available && activeView === 'baselines' && (
        <>
          <div className="overview-section">
            <div className="section-heading-row">
              <div className="card-title">
                Segment Baselines{' '}
                <InfoHint text={persona.normalization_note || 'Cells compare each segment\'s raw trait score to the global baseline; values are z vs global. The 0–1 normalized scale is display-only.'} />
              </div>
            </div>
            <div className="chart-row segment-baseline-stack">
              <BaselineHeatmap
                title={`${segmentMode === 'workflow' ? segmentLabelText : actionLabelText} by Persona`}
                badge="Persona traits"
                rows={personaRows}
                vectors={personaVectors}
                groupKey={groupKey}
                groupLabel={groupLabel}
                groupHeader={segmentMode === 'workflow' ? segmentLabelText : actionLabelText}
                expanded
              />
              <BaselineHeatmap
                title={`${segmentMode === 'workflow' ? segmentLabelText : actionLabelText} by Emotion`}
                badge="Emotion clusters"
                description="Emotion clusters group related scored emotion concepts into readable families, such as joy, contentment, gratitude, suspicion, anger, fear, and shame."
                rows={emotionRows}
                vectors={emotionVectors}
                groupKey={groupKey}
                groupLabel={groupLabel}
                groupHeader={segmentMode === 'workflow' ? segmentLabelText : actionLabelText}
                expanded={showAllEmotions}
                onExpanded={setShowAllEmotions}
              />
            </div>
          </div>

          <div className="chart-row">
            {activeTraitRows.length > 0 && (
              <div className="card enterprise-panel trait-detail-panel">
                <div className="card-heading-row">
                  <div className="card-title">Trait Detail</div>
                  <label className="select-control-label">
                    <span>Trait</span>
                    <select value={activeTrait} onChange={event => setSelectedTrait(event.target.value)}>
                      {personaDetailVectors.length > 0 && (
                        <optgroup label="Persona traits">
                          {personaDetailVectors.map(vector => <option key={vector} value={vector}>{vectorLabel(vector)}</option>)}
                        </optgroup>
                      )}
                      {emotionDetailVectors.length > 0 && (
                        <optgroup label="Emotion clusters">
                          {emotionDetailVectors.map(vector => <option key={vector} value={vector}>{vectorLabel(vector)}</option>)}
                        </optgroup>
                      )}
                    </select>
                  </label>
                </div>
                <TraitDetailChart
                  title={`${vectorLabel(activeTrait)} Across ${segmentMode === 'workflow' ? segmentLabelText : actionLabelText}`}
                  readGuide="Bars show z-score vs the global baseline for this trait or emotion family. 0 is typical; positive is more; negative is less."
                  rows={activeTraitRows}
                  vector={activeTrait}
                  groupLabel={groupLabel}
                />
              </div>
            )}

          </div>

          {outcomeRows.length > 0 && (
            <div className="chart-row">
              <OutcomeBehaviorCard rows={outcomeRows} segmentLabelText={segmentLabelText} />
            </div>
          )}
        </>
      )}

      {persona.available && (
        <>
          <div className="chart-row">
            <InvestigationQueue outliers={persona.outliers || []} family={queueFamily} onFamily={setQueueFamily} provider={provider} />
          </div>

          {outlierSeries.length > 0 && (
            <div className="overview-section">
              <div className="section-heading-row">
                <div>
                  <div className="card-title">
                    Outlier Trace Previews{' '}
                    <InfoHint text="Turn-level signed z for each trace's tracked signal; the dotted line is the comparable length/position baseline. Click a trace id for full inspection." />
                  </div>
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
    </div>
  )
}

export { Overview }
