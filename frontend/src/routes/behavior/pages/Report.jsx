import { CharacterPortrait } from './Character.jsx'
import { CharacterTrackHeatmap, trackTitle } from '../tracks.jsx'
import { Link } from 'react-router-dom'
import { fmt, pct, pct1, titleize } from '../helpers'
import { getCharacter, getProductAnalytics, getTail } from '../../../api'
import { providerPath, useProviderSelection } from '../layout'
import { sessionFocusLink, vectorLabel } from '../shared.jsx'
import { useAsyncResource } from '../../../hooks/useAsyncResource'

function ReportSection({ n, title, children }) {
  return (
    <section className="report-section">
      <h2 className="report-h2"><span className="report-num">{n}</span>{title}</h2>
      {children}
    </section>
  )
}

function strongestContrast(row) {
  return [...(row?.contrasts || [])]
    .filter(contrast => contrast.paired_d != null)
    .sort((a, b) => Math.abs(Number(b.paired_d)) - Math.abs(Number(a.paired_d)))[0]
}

function comparisonRows(comparison, limitPerFamily = null) {
  const sorted = [...(comparison.vectors || [])]
    .sort((a, b) => Number(b.eta_squared || 0) - Number(a.eta_squared || 0))
  if (limitPerFamily == null) return sorted
  return ['persona', 'emotion_cluster']
    .flatMap(family => sorted.filter(row => row.family === family).slice(0, limitPerFamily))
}

function TrackOverviewTable({ comparison, limitPerFamily = null }) {
  const rows = comparisonRows(comparison, limitPerFamily)
  if (!rows.length) return null
  return (
    <table className="data-table report-table">
      <thead>
        <tr><th>Signal</th><th>Family</th><th>Strongest paired contrast</th><th>Mean difference</th><th>Paired d</th></tr>
      </thead>
      <tbody>
        {rows.map(row => {
          const contrast = strongestContrast(row)
          return (
            <tr key={row.vector}>
              <td>{vectorLabel(row.vector)}</td>
              <td>{row.family === 'emotion_cluster' ? 'Emotion' : 'Persona'}</td>
              <td>{contrast ? `${trackTitle(contrast.a)} vs ${trackTitle(contrast.b)}` : '-'}</td>
              <td>{contrast ? `${Number(contrast.mean_delta) >= 0 ? '+' : ''}${fmt(contrast.mean_delta)}` : '-'}</td>
              <td>{contrast ? fmt(contrast.paired_d) : '-'}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function BaselineOverviewTable({ rows = [], limitPerFamily = null }) {
  const sorted = [...rows].sort((a, b) => Math.abs(Number(b.basis_mean || 0)) - Math.abs(Number(a.basis_mean || 0)))
  const visible = limitPerFamily == null
    ? sorted
    : ['persona', 'emotion_cluster'].flatMap(
        family => sorted.filter(row => row.family === family).slice(0, limitPerFamily),
      )
  return (
    <table className="data-table report-table">
      <thead><tr><th>Signal</th><th>Family</th><th>Global mean</th><th>Global sd</th><th>n</th></tr></thead>
      <tbody>
        {visible.map(row => (
          <tr key={row.vector}><td>{vectorLabel(row.vector)}</td><td>{row.family === 'emotion_cluster' ? 'Emotion' : 'Persona'}</td><td>{fmt(row.basis_mean)}</td><td>{fmt(row.basis_sd)}</td><td>{row.n}</td></tr>
        ))}
      </tbody>
    </table>
  )
}

function Report() {
  const [provider] = useProviderSelection()
  const { data, error } = useAsyncResource(
    () => Promise.all([
      getProductAnalytics(provider),
      getCharacter(provider),
      getTail(provider),
    ]).then(([analytics, character, tail]) => ({ analytics, character, tail })),
    [provider],
  )

  if (error) return (
    <div>
      <h1 className="page-title">Report</h1>
      <p className="muted-copy">Could not load Report data: {error}</p>
    </div>
  )
  if (!data) return <h1 className="page-title">Loading...</h1>

  const { analytics, character, tail } = data
  const providerInfo = analytics.provider || {}
  const overview = analytics.persona_overview || {}
  const comparison = overview.track_comparison || {}
  const points = character.points || []
  const characterMeta = character.meta || {}
  const dropped = character.dropped || []
  const modes = tail.modes || []
  const tailMeta = tail.meta || {}
  const outliers = overview.outliers || []
  const traceCount = overview.reward_math?.trace_count || analytics.trace_count || points[0]?.audited_total
  const byDistinctive = [...points].sort((a, b) => Number(b.distinctiveness || 0) - Number(a.distinctiveness || 0))
  const characteristic = byDistinctive.filter(point => Number(point.distinctiveness) > 0).slice(0, 4)
  const suppressed = [...points]
    .filter(point => Number(point.distinctiveness) < 0)
    .sort((a, b) => Number(a.distinctiveness) - Number(b.distinctiveness))
    .slice(0, 4)
  const isTrackComparison = Boolean(comparison.available && characterMeta.reference_kind === 'track')
  const topPersonaRows = comparisonRows(comparison).filter(row => row.family === 'persona').slice(0, 3)
  const topEmotionRows = comparisonRows(comparison).filter(row => row.family === 'emotion_cluster').slice(0, 3)

  return (
    <div className="report">
      <div className="report-toolbar">
        <button type="button" onClick={() => window.print()}>Print / Save as PDF</button>
      </div>
      <article className="report-doc">
        <header className="report-cover">
          <div className="report-kicker">Deterministic Behavioral Audit</div>
          <h1 className="report-title">{providerInfo.dataset_label || titleize(provider)} — Audit Report</h1>
          <p className="report-headline">
            {isTrackComparison
              ? `${comparison.tracks?.length || 0} tracks compared over ${comparison.paired_task_count || 0} paired ${String(providerInfo.task_label || 'task').toLowerCase()}s, with persona, emotion, character, tail, and session evidence drawn from the same scored bundle.`
              : `A reproducible snapshot of persona, emotion, character, tail, and session evidence for the active provider.`}
          </p>
          <dl className="report-meta">
            <div><dt>Provider</dt><dd>{providerInfo.label || titleize(provider)}</dd></div>
            <div><dt>Sessions</dt><dd>{traceCount?.toLocaleString?.() || traceCount || '-'}</dd></div>
            <div><dt>Character traits</dt><dd>{points.length} scored · {dropped.length} unavailable</dd></div>
            <div><dt>Generation</dt><dd>Computed from current API payloads; no LLM narrative</dd></div>
          </dl>
        </header>

        <ReportSection n="1" title="Executive findings">
          {isTrackComparison ? (
            <div className="report-columns">
              {[
                ['Persona signals', topPersonaRows],
                ['Emotion signals', topEmotionRows],
              ].map(([label, rows]) => (
                <div key={label}>
                  <div className="report-label">{label}</div>
                  <ul className="report-body">
                    {rows.map(row => {
                      const contrast = strongestContrast(row)
                      return (
                        <li key={row.vector}>
                          <strong>{vectorLabel(row.vector)}:</strong>{' '}
                          {contrast
                            ? `${trackTitle(contrast.a)} vs ${trackTitle(contrast.b)}, paired d ${fmt(contrast.paired_d)} across ${contrast.n_pairs} matched sessions.`
                            : 'No paired contrast available.'}
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <div className="report-columns">
              <div>
                <div className="report-label">Most characteristic</div>
                <ul className="report-list">
                  {characteristic.length
                    ? characteristic.map(point => <li key={point.coordinate}><span>{point.label}</span><strong className="up">+{pct1(point.distinctiveness)}</strong></li>)
                    : <li><span className="muted-copy">No positive reference lift.</span></li>}
                </ul>
              </div>
              <div>
                <div className="report-label">Most suppressed</div>
                <ul className="report-list">
                  {suppressed.length
                    ? suppressed.map(point => <li key={point.coordinate}><span>{point.label}</span><strong className="down">{pct1(point.distinctiveness)}</strong></li>)
                    : <li><span className="muted-copy">No negative reference lift.</span></li>}
                </ul>
              </div>
            </div>
          )}
        </ReportSection>

        <ReportSection n="2" title={isTrackComparison ? 'Overview — matched track separation' : 'Overview — scored baselines'}>
          <p className="report-body">
            {isTrackComparison
              ? 'Every contrast uses the same underlying sessions for each track. Mean difference stays in the raw direction-oriented score units; paired d standardizes that within matched pairs.'
              : 'These are the same populated score surfaces shown on Overview. Empty or under-sampled signals are excluded instead of rendered as blank columns.'}
          </p>
          <div className="report-screen-summary">
            {isTrackComparison
              ? <TrackOverviewTable comparison={comparison} limitPerFamily={5} />
              : <BaselineOverviewTable rows={overview.vector_inventory || []} limitPerFamily={5} />}
          </div>
          <details className="report-appendix">
            <summary>Full signal appendix</summary>
            {isTrackComparison
              ? <TrackOverviewTable comparison={comparison} />
              : <BaselineOverviewTable rows={overview.vector_inventory || []} />}
          </details>
        </ReportSection>

        <ReportSection n="3" title="Character — recurring trait posture">
          <p className="report-body">
            Character uses per-session peak trait scores. {isTrackComparison
              ? `Each track is shown directly; the ${trackTitle(characterMeta.reference_provider)} track supplies the within-dataset reference threshold.`
              : `Presence means a session exceeds the ${Math.round(Number(characterMeta.quantile || 0.8) * 100)}th percentile reference threshold for that trait.`}
          </p>
          {isTrackComparison
            ? <CharacterTrackHeatmap points={points} meta={characterMeta} />
            : <CharacterPortrait points={points} selected={null} onSelect={() => {}} />}
        </ReportSection>

        <ReportSection n="4" title="Tail — unusual co-activation modes">
          <p className="report-body">
            Tail modes group turns that are extreme relative to their own baseline across several traits at once. They are investigation clusters, not automatic failure labels.
          </p>
          {modes.length ? (
            <>
              <table className="data-table report-table">
                <thead><tr><th>Mode signature</th><th>Turns</th><th>Sessions</th><th>Typical z</th><th>Reach z</th></tr></thead>
                <tbody>
                  {modes.map(mode => (
                    <tr key={mode.id}>
                      <td>{mode.signature?.length ? mode.signature.map(signal => `${signal.gap >= 0 ? '↑' : '↓'}${signal.label}`).join(' · ') : 'Diffuse'}</td>
                      <td>{mode.size_turns} ({pct(mode.size_share)})</td>
                      <td>{mode.trace_count} ({pct(mode.trace_share)})</td>
                      <td>{fmt(mode.central_severity)}</td>
                      <td>{fmt(mode.reach)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted-copy compact">{tailMeta.n_tail_traces} of {tailMeta.total_traces} sessions contain at least one tail turn.</p>
            </>
          ) : <p className="muted-copy">Not enough tail turns to form a stable mode.</p>}
        </ReportSection>

        <ReportSection n="5" title="Sessions — evidence to inspect">
          <p className="report-body">These are the highest aggregate baseline deviations from the same Overview queue. Open a session to compare multiple selected signals across its trajectory and conversation log.</p>
          {outliers.length ? (
            <table className="data-table report-table">
              <thead><tr><th>Session</th><th>Segment</th><th>Signal</th><th>Primary z</th><th>Aggregate</th></tr></thead>
              <tbody>
                {outliers.slice(0, 6).map(row => {
                  const top = row.top_z?.[0] || {}
                  return (
                    <tr key={row.trace_id}>
                      <td><Link to={providerPath(sessionFocusLink(row.trace_id, {
                        coordinate: top.coordinate,
                        vector: top.vector || row.selected_vector,
                        family: row.family,
                        baseline_scope: row.baseline_scope || 'workflow',
                        source: 'report',
                      }), provider)}>{row.trace_id}</Link></td>
                      <td>{titleize(row.workflow)} / {titleize(row.final_action)}</td>
                      <td>{vectorLabel(top.vector || row.selected_vector)}</td>
                      <td>{fmt(top.z)}</td>
                      <td>{fmt(row.outlier_score)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : <p className="muted-copy">No populated investigation queue for this provider.</p>}
        </ReportSection>

        <ReportSection n="6" title="Coverage & interpretation">
          <ul className="report-body">
            <li><strong>Signals are directional.</strong> Activation projections and z-scores are evidence for inspection, not probabilities or verdicts.</li>
            <li><strong>Comparisons are case-specific.</strong> {isTrackComparison ? 'This report uses the bundled control track because every track answers the same seeds.' : `Character uses ${characterMeta.reference_provider || 'the configured reference'}; choose a scientifically comparable corpus for your own data.`}</li>
            <li><strong>Output is deterministic.</strong> The report composes current Overview, Character, Tail, and Session payloads and does not ask an LLM to invent narrative.</li>
            {dropped.length > 0 && <li><strong>Unavailable traits:</strong> {dropped.map(row => row.label).join(', ')}.</li>}
          </ul>
        </ReportSection>
      </article>
    </div>
  )
}

export { Report, ReportSection, strongestContrast }
