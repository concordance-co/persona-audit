// Tail page and its visualization components.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { InfoHint, sessionFocusLink } from '../shared.jsx'
import { LabelList, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { Link, useLocation } from 'react-router-dom'
import { TrackShareChips, trackColor, trackTitle } from '../tracks.jsx'
import { getTail } from '../../../api'
import { pct } from '../helpers'
import { providerPath, useProviderSelection } from '../layout'
import { useEffect, useState } from 'react'

const TAIL_SEVERITY_MAX = 4  // backend caps signal at 4σ

function tailModeHeadline(mode) {
  if (mode.name) return mode.name
  const sig = mode.signature || []
  if (!sig.length) return 'Diffuse pattern — no single trait stands out'
  const hot = sig.filter(s => s.gap > 0).slice(0, 2).map(s => s.label)
  const cold = sig.filter(s => s.gap < 0).slice(0, 2).map(s => s.label)
  const parts = []
  // Elevated traits lead unqualified ("High" is implied); only the suppressed
  // tail keeps a "low" marker so direction stays unambiguous.
  if (hot.length) parts.push(hot.join(' & '))
  if (cold.length) parts.push(`${hot.length ? 'low ' : 'Low '}${cold.join(' & ')}`)
  return parts.join(', ')
}

function TailTraitGroup({ label, tone, traits }) {
  if (!traits.length) return null
  return (
    <div className="tail-trait-group">
      <span className="tail-trait-grouplabel">{label}</span>
      <div className="tail-trait-chips">
        {traits.map(s => (
          <span key={s.trait} className={`tail-trait-chip ${tone}`}>
            {s.label}<em>{Math.abs(s.gap).toFixed(1)}σ</em>
          </span>
        ))}
      </div>
    </div>
  )
}

function TailFingerprint({ signature }) {
  if (!signature?.length) return (
    <p className="muted-copy compact">No single trait sets this cluster apart — a diffuse, weakly-defined pattern.</p>
  )
  return (
    <div className="tail-fingerprint">
      <TailTraitGroup label="Runs hotter on" tone="up" traits={signature.filter(s => s.gap > 0)} />
      <TailTraitGroup label="Runs colder on" tone="down" traits={signature.filter(s => s.gap < 0)} />
    </div>
  )
}

function TailSeverity({ central, reach, concerning }) {
  const fill = Math.min(100, (central / TAIL_SEVERITY_MAX) * 100)
  const reachFill = Math.min(100, (reach / TAIL_SEVERITY_MAX) * 100)
  return (
    <div className={`tail-meter ${concerning ? 'concern' : 'benign'}`}>
      <div className="tail-meter-track">
        <div className="tail-meter-reach" style={{ width: `${reachFill}%` }} />
        <div className="tail-meter-fill" style={{ width: `${fill}%` }} />
      </div>
      <div className="tail-meter-scale">
        <span><strong>~{central}σ</strong></span>
        <span>peaks <strong>{reach}σ</strong></span>
      </div>
    </div>
  )
}

function tailShortLabel(mode) {
  // Lead trait the cluster runs *high* on; for a pure-suppression cluster fall
  // back to the concern trait, then to what its turns actually peak on.
  const hot = (mode.signature || []).find(s => s.gap > 0)
  if (hot) return hot.label
  if (mode.concern_traits?.length) return mode.concern_traits[0].label
  return mode.representative?.peak_label || `#${mode.id}`
}

function tailTrackSummary(tracks = []) {
  if (!tracks.length) return null
  return tracks.map(group => `${trackTitle(group.track)} ${pct(group.share)}`).join(' · ')
}

function TailMapTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  const trackSummary = tailTrackSummary(d.tracks)
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{d.headline}</div>
      <div className="chart-tooltip-row"><span>How common</span><strong>{d.y}% of tail · {d.turns} turns</strong></div>
      <div className="chart-tooltip-row"><span>How intense</span><strong>~{d.x.toFixed(1)}σ, up to {d.reach.toFixed(1)}σ</strong></div>
      {trackSummary && <div className="chart-tooltip-row"><span>Tracks</span><strong>{trackSummary}</strong></div>}
      <div className="chart-tooltip-note">{d.concerning ? '⚠ concerning' : 'benign extreme'}</div>
    </div>
  )
}

// Pinned on click in a corner of the plot. pointer-events:none on the body (so
// it never blocks a bubble click underneath); only the close button is live.
function TailMapCard({ point, onClose }) {
  if (!point) return null
  const trackSummary = tailTrackSummary(point.tracks)
  return (
    <div className="tail-map-card">
      <button className="tail-map-card-close" onClick={onClose} aria-label="Close">×</button>
      <div className="chart-tooltip-title">{point.headline}</div>
      <div className="chart-tooltip-row"><span>How common</span><strong>{point.y}% of tail · {point.turns} turns</strong></div>
      <div className="chart-tooltip-row"><span>How intense</span><strong>~{point.x.toFixed(1)}σ, up to {point.reach.toFixed(1)}σ</strong></div>
      {trackSummary && <div className="chart-tooltip-row"><span>Tracks</span><strong>{trackSummary}</strong></div>}
      <div className="chart-tooltip-note">{point.concerning ? '⚠ concerning' : 'benign extreme'}</div>
    </div>
  )
}

// Evocative "landscape" of the tail: each cluster a soft bubble placed by how
// intense (x) and how common (y) it is, sized by turns, coloured by concern.
// Deliberately axis-light -- position and size carry the story, not tick marks.
function TailMapView({ modes }) {
  const [selected, setSelected] = useState(null)
  const points = modes.map(m => ({
    id: m.id,
    x: m.central_severity,
    y: +(m.size_share * 100).toFixed(1),
    turns: m.size_turns,
    traces: m.trace_count,
    reach: m.reach,
    concerning: m.concerning,
    tracks: m.tracks || [],
    headline: tailModeHeadline(m),
    label: tailShortLabel(m),
  }))
  const concern = points.filter(p => p.concerning)
  const benign = points.filter(p => !p.concerning)
  const xs = points.map(p => p.x)
  const ys = points.map(p => p.y)
  const xDomain = [Math.floor((Math.min(...xs) - 0.3) * 10) / 10, Math.ceil((Math.max(...xs) + 0.3) * 10) / 10]
  // sqrt scale: one cluster (Hostile) is ~15x more frequent than the rest, so a
  // linear axis smushes the others onto the baseline. sqrt lifts them off it.
  const yDomain = [0, Math.ceil(Math.max(...ys) * 1.12)]
  const maxTurns = Math.max(...points.map(p => p.turns), 1)
  const bubble = (fill, fillOpacity, stroke) => ({ cx, cy, payload }) => {
    if (cx == null || cy == null) return null
    const r = 9 + 26 * Math.sqrt(payload.turns / maxTurns)
    const isSel = payload.id === selected
    return (
      <circle
        cx={cx} cy={cy} r={r}
        fill={fill}
        fillOpacity={isSel ? Math.min(1, fillOpacity + 0.32) : fillOpacity}
        stroke={isSel ? '#080808' : stroke}
        strokeWidth={isSel ? 2.5 : 1.5}
        style={{ cursor: 'pointer' }}
        onClick={() => setSelected(payload.id === selected ? null : payload.id)}
      />
    )
  }
  const labelStyle = bold => ({ fontSize: 12, fontWeight: bold ? 700 : 500, fill: bold ? '#080808' : 'rgba(8,8,8,0.7)', stroke: '#fff8f4', strokeWidth: 3, paintOrder: 'stroke', cursor: 'pointer' })

  return (
    <div className="tail-map">
      <span className="tail-map-ylabel">more common ↑</span>
      <ResponsiveContainer width="100%" height={400}>
        <ScatterChart margin={{ top: 24, right: 40, bottom: 16, left: 16 }}>
          <XAxis type="number" dataKey="x" domain={xDomain} tick={false} tickLine={false} axisLine={{ stroke: 'rgba(8,8,8,0.18)' }} height={2} />
          <YAxis type="number" dataKey="y" domain={yDomain} scale="sqrt" tick={false} tickLine={false} axisLine={{ stroke: 'rgba(8,8,8,0.18)' }} width={2} />
          <Tooltip content={<TailMapTooltip />} cursor={false} wrapperStyle={{ pointerEvents: 'none' }} />
          <Scatter data={benign} shape={bubble('rgba(8,8,8,0.26)', 0.75, 'rgba(8,8,8,0.28)')} isAnimationActive={false}>
            <LabelList dataKey="label" position="top" offset={12} style={labelStyle(false)} />
          </Scatter>
          <Scatter data={concern} shape={bubble('#ef3333', 0.6, 'rgba(239,51,51,0.85)')} isAnimationActive={false}>
            <LabelList dataKey="label" position="top" offset={12} style={labelStyle(true)} />
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      {selected != null && (
        <TailMapCard point={points.find(p => p.id === selected)} onClose={() => setSelected(null)} />
      )}
      <div className="tail-map-foot">
        <span className="tail-map-xlabel">more intense →</span>
        <span className="tail-viz-key">
          <span><i className="dot concern" /> concerning</span>
          <span><i className="dot benign" /> benign</span>
          <span className="muted">bubble = turns</span>
        </span>
      </div>
    </div>
  )
}

const TAIL_COACT_TOP = 7  // traits shown per cluster silhouette

function TailCoactRow({ label, z, maxAbs }) {
  const w = Math.max(4, Math.min(50, (Math.abs(z) / maxAbs) * 50))
  const hot = z >= 0
  return (
    <div className="tail-coact-row">
      <span className="tail-coact-label">{label}</span>
      <div className="tail-coact-track">
        <span className="tail-coact-axis" />
        <span
          className={`tail-coact-bar ${hot ? 'hot' : 'cold'}`}
          style={hot ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }}
        />
      </div>
    </div>
  )
}

// One cluster's co-activation shape: the traits that move together when it goes
// extreme, drawn as a soft diverging silhouette (no axes, no numbers).
function TailClusterSilhouette({ mode, meta, maxAbs }) {
  const labels = meta.trait_labels || {}
  const entries = Object.entries(mode.profile || {})
    .map(([trait, z]) => ({ trait, z, label: labels[trait] || trait }))
    .sort((a, b) => Math.abs(b.z) - Math.abs(a.z))
    .slice(0, TAIL_COACT_TOP)
    .sort((a, b) => b.z - a.z)
  return (
    <div className={`tail-silhouette ${mode.concerning ? 'is-concern' : ''}`}>
      <div className="tail-silhouette-head">
        {mode.concerning && <i className="dot concern" />}
        <span className="tail-silhouette-title">{tailModeHeadline(mode)}</span>
        <span className="tail-silhouette-meta">
          {pct(mode.size_share)} of tail · {mode.size_turns} turns
          {(mode.tracks || [])[0]?.share >= 0.6 ? ` · mostly ${trackTitle(mode.tracks[0].track)}` : ''}
        </span>
      </div>
      <div className="tail-coact">
        {entries.map(e => <TailCoactRow key={e.trait} label={e.label} z={e.z} maxAbs={maxAbs} />)}
      </div>
    </div>
  )
}

function TailVisualization({ modes, meta }) {
  const initialView = new URLSearchParams(useLocation().search).get('view') === 'coact' ? 'coact' : 'map'
  const [view, setView] = useState(initialView)
  if (!modes.length) return null
  const maxAbs = Math.max(1.5, ...modes.flatMap(m => Object.values(m.profile || {}).map(v => Math.abs(v || 0))))
  const ordered = [...modes.filter(m => m.concerning), ...modes.filter(m => !m.concerning)]
  return (
    <div className="card tail-viz">
      <div className="tail-viz-head">
        <div className="report-label">The shape of the tail · {modes.length} clusters</div>
        <div className="tail-viz-toggle">
          <button className={view === 'map' ? 'active' : ''} onClick={() => setView('map')}>Map</button>
          <button className={view === 'coact' ? 'active' : ''} onClick={() => setView('coact')}>Co-activation</button>
        </div>
      </div>
      {view === 'map' ? (
        <>
          <p className="muted-copy compact tail-viz-sub">
            Where each failure cluster sits — further right means a more intense moment, higher up means it
            happens more often. The biggest, reddest bubbles are the patterns worth attention first.
          </p>
          <TailMapView modes={modes} />
        </>
      ) : (
        <>
          <p className="muted-copy compact tail-viz-sub">
            Each cluster is one way the tail co-activates — the traits that move together when this model goes
            extreme. Bars reach right (red) where the cluster runs high on a trait, left (blue) where it runs low.
          </p>
          <div className="tail-silhouette-grid">
            {ordered.map(m => <TailClusterSilhouette key={m.id} mode={m} meta={meta} maxAbs={maxAbs} />)}
          </div>
        </>
      )}
    </div>
  )
}

function TailModeBadge({ mode }) {
  if (mode.concerning) {
    return <span className="tail-badge concern" title="A concern trait (sycophantic, manipulative, hostile, condescending) runs elevated here.">⚠ Concerning</span>
  }
  return <span className="tail-badge benign" title="An extreme on neutral or desirable traits — distinctive, but not a concern trait.">Benign extreme</span>
}

function TailExemplar({ label, exemplar, provider }) {
  const coordinate = `assistant_axis_trait__${exemplar.peak_trait}`
  return (
    <div className="tail-exemplar">
      <div className="tail-exemplar-label">{label}</div>
      <Link className="tail-exemplar-link" to={providerPath(sessionFocusLink(exemplar.trace_id, {
        coordinate,
        vector: exemplar.peak_trait,
        family: 'persona',
        turn: exemplar.turn_index,
        source: 'tail',
      }), provider)}>{exemplar.trace_id} · turn {exemplar.turn_index} →</Link>
      <div className="muted-copy compact">spiked on <strong>{exemplar.peak_label}</strong> · {exemplar.max_z}σ past baseline</div>
    </div>
  )
}

function TailModeCard({ mode, rank, provider, trackOrder = [] }) {
  return (
    <div className={`card tail-mode ${mode.concerning ? 'is-concern' : 'is-benign'}`}>
      <div className="tail-mode-head">
        <span className="tail-mode-rank">{String(rank).padStart(2, '0')}</span>
        <div className="tail-mode-headline-wrap">
          <div className="tail-mode-titlerow">
            <div className="tail-mode-title">{tailModeHeadline(mode)}</div>
            <TailModeBadge mode={mode} />
          </div>
          <div className="muted-copy compact">
            Seen in <strong>{mode.size_turns}</strong> turns across <strong>{mode.trace_count}</strong> conversations
            {mode.diffuse ? ' · diffuse / weakly defined' : ''}
          </div>
          {(mode.tracks || []).length > 0 && (
            <div className="tail-track-row">
              <TrackShareChips tracks={mode.tracks} order={trackOrder} />
            </div>
          )}
        </div>
      </div>

      {mode.concerning && mode.concern_traits.length > 0 && (
        <div className="tail-concern-note">
          <strong>Why flagged:</strong> runs hot on {mode.concern_traits.map(c => `${c.label} (${c.mean_z}σ)`).join(', ')} —
          a concern trait, even where that isn’t what most sets the cluster apart.
        </div>
      )}

      <div className="tail-mode-block">
        <div className="report-label">What sets this pattern apart</div>
        <TailFingerprint signature={mode.signature} />
        <p className="tail-mode-note">measured against the model’s other extreme moments</p>
      </div>

      <div className="tail-mode-stats">
        <div className="tail-mode-stat">
          <div className="report-label">How intense</div>
          <TailSeverity central={mode.central_severity} reach={mode.reach} concerning={mode.concerning} />
        </div>
        <div className="tail-mode-stat">
          <div className="report-label">How common</div>
          <div className="tail-freq">
            <span><strong>{pct(mode.size_share)}</strong> of all tail turns</span>
            <span><strong>{pct(mode.trace_share)}</strong> of all conversations</span>
          </div>
        </div>
      </div>

      <div className="tail-mode-block">
        <div className="report-label">See it for yourself</div>
        <div className="tail-exemplars">
          {mode.exemplars_coincide
            ? <TailExemplar label="Representative — also the worst" exemplar={mode.representative} provider={provider} />
            : <>
                <TailExemplar label="A representative moment" exemplar={mode.representative} provider={provider} />
                <TailExemplar label="The worst moment" exemplar={mode.worst} provider={provider} />
              </>}
        </div>
      </div>
    </div>
  )
}

function Tail() {
  const [provider] = useProviderSelection()
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setPayload(null)
    setError(null)
    getTail(provider)
      .then(data => { if (active) setPayload(data) })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Tail Risk</h1>
      <p className="muted-copy">Could not load Tail data: {error}</p>
    </div>
  )
  if (!payload) return <h1 className="page-title">Loading...</h1>

  const modes = payload.modes || []
  const scatter = payload.scatter
  const meta = payload.meta || {}
  const concerning = modes.filter(m => m.concerning)
  const benign = modes.filter(m => !m.concerning)

  return (
    <div>
      <h1 className="page-title">Tail Risk</h1>
      <p className="muted-copy tail-intro">
        Every moment where {(meta.tracks || []).length > 0
          ? <>a persona track pushed past <strong>its own track&apos;s 90th-percentile</strong></>
          : <>this model pushed past its <strong>own 90th-percentile</strong></>} on any persona trait is an
        extreme moment. We grouped those moments by <strong>which traits fired together</strong> and found{' '}
        <strong>{modes.length} recurring patterns</strong> across {meta.n_tail_traces} of {meta.total_traces} conversations.
        Not every extreme is a problem — so each pattern is split into <strong>concerning</strong> (a concern trait runs hot:
        sycophantic, manipulative, hostile, condescending) and <strong>benign extremes</strong> (distinctive, but on neutral
        or desirable traits like calm, analytical, or conciliatory).
      </p>
      <p className="muted-copy tail-intro compact">
        {(meta.tracks || []).length > 0
          ? 'Intensity is in standard deviations (σ) past each track’s own baseline — extreme means extreme for that persona, never far from the pooled blend of personas. Clustering is shared, so a failure shape that more than one persona exhibits is one pattern.'
          : 'Intensity is in standard deviations (σ) past the model’s own baseline — so this view stands on its own, independent of the tau2 reference used on the Character page.'}
      </p>

      {(meta.tail_composition || []).length > 0 && (
        <div className="card tail-composition">
          <div className="card-heading-row compact-heading">
            <div className="card-title">Whose extremes are these?</div>
            <InfoHint text="Every track contributes the same number of turns, so an even split would mean the personas go extreme equally often. A skew means one persona owns more of the tail." />
          </div>
          <div className="track-legend tail-composition-chips">
            {(meta.tail_composition || []).map((group, index) => {
              const corpus = (meta.corpus_composition || []).find(item => item.track === group.track)
              return (
                <span
                  key={group.track}
                  className="track-legend-item"
                  title={corpus ? `${trackTitle(group.track)}: ${pct(group.share)} of tail turns vs ${pct(corpus.share)} of all turns` : undefined}
                >
                  <span className="track-legend-dot" style={{ background: trackColor(group.track, index) }} />
                  {trackTitle(group.track)} · {pct(group.share)} of tail
                </span>
              )
            })}
          </div>
        </div>
      )}

      <div className="stats-grid">
        <div className="card tail-stat-concern">
          <div className="card-title">Concerning patterns</div>
          <div className="stat-value">{concerning.length}</div>
          <div className="stat-label">a concern trait runs elevated</div>
        </div>
        <div className="card">
          <div className="card-title">Benign extremes</div>
          <div className="stat-value">{benign.length}</div>
          <div className="stat-label">extreme, but not on a concern trait</div>
        </div>
        <div className="card">
          <div className="card-title">Scattered tail</div>
          <div className="stat-value">{scatter ? pct(scatter.size_share) : '—'}</div>
          <div className="stat-label">one-off extremes, no repeated pattern</div>
        </div>
      </div>

      {modes.length === 0 && (
        <div className="card"><p className="muted-copy">Not enough tail turns to form modes in this corpus.</p></div>
      )}

      <TailVisualization modes={modes} meta={meta} />

      {concerning.length > 0 && (
        <div className="tail-group">
          <h2 className="tail-group-title concern">Concerning patterns <span>· {concerning.length}</span></h2>
          <p className="muted-copy compact tail-group-sub">
            A concern trait runs meaningfully elevated in these — the parts of the tail worth attention.
          </p>
          {concerning.map((mode, i) => (
            <TailModeCard key={mode.id} mode={mode} rank={i + 1} provider={provider} trackOrder={meta.tracks || []} />
          ))}
        </div>
      )}

      {benign.length > 0 && (
        <div className="tail-group">
          <h2 className="tail-group-title benign">Benign extremes <span>· {benign.length}</span></h2>
          <p className="muted-copy compact tail-group-sub">
            Statistically extreme moments on neutral or desirable traits. Shown for completeness — these are not failures.
          </p>
          {benign.map((mode, i) => (
            <TailModeCard key={mode.id} mode={mode} rank={i + 1} provider={provider} trackOrder={meta.tracks || []} />
          ))}
        </div>
      )}

      {scatter && (
        <div className="card tail-scatter">
          <div className="tail-mode-title">Scattered tail · {scatter.size_turns} turns</div>
          <p className="muted-copy compact">
            {pct(scatter.size_share)} of the tail ({scatter.trace_count} traces) does not form a pattern —
            isolated, one-off extremes rather than a repeated one. Typical intensity {scatter.central_severity}σ.
            Shown as a finding, not forced into a cluster.
          </p>
        </div>
      )}
    </div>
  )
}

export { TAIL_COACT_TOP, TAIL_SEVERITY_MAX, Tail, TailClusterSilhouette, TailCoactRow, TailExemplar, TailFingerprint, TailMapCard, TailMapTooltip, TailMapView, TailModeBadge, TailModeCard, TailSeverity, TailTraitGroup, TailVisualization, tailModeHeadline, tailShortLabel, tailTrackSummary }
