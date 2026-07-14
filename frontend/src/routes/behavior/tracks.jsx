// Track-comparison components (Sol/Marrow/control colors, heatmaps, panels).
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { Fragment } from 'react'
import { clamp01, compactNumber, vectorLabel, zColor } from './shared.jsx'
import { fmt, pct, titleize } from './helpers'

const TRACK_COLORS = { sol: '#B9513A', marrow: '#4A6FE0', control: '#8B8580' }
const TRACK_FALLBACK_COLORS = ['#7A4A9E', '#2E8C43', '#F5CD2F', '#080808']

function trackColor(track, index = 0) {
  return TRACK_COLORS[track] || TRACK_FALLBACK_COLORS[index % TRACK_FALLBACK_COLORS.length]
}

function trackTitle(value) {
  return titleize(value)
}

function TrackIntervalRow({ row, trackOrder, withLabels = false }) {
  const byTrack = new Map((row.tracks || []).map(item => [item.track, item]))
  const eta = Number(row.eta_squared)
  const marks = trackOrder
    .map((track, index) => {
      const item = byTrack.get(track)
      if (!item || item.display_mean == null) return null
      return { track, index, mean: clamp01(item.display_mean), item }
    })
    .filter(Boolean)
    .sort((a, b) => a.mean - b.mean)
  if (!marks.length) return null
  const spanLow = marks[0].mean
  const spanHigh = marks[marks.length - 1].mean
  let lastLabelPosition = -1
  return (
    <div className={`track-interval-row${withLabels ? ' with-labels' : ''}`}>
      <div className="track-interval-label">
        <span>{vectorLabel(row.vector)}</span>
        <small title="How much of this trait's spread is explained by which track a trace is in (η², 0–1).">
          {Number.isFinite(eta) ? eta.toFixed(2) : '-'}
        </small>
      </div>
      <div className="track-interval-axis">
        <span
          className="track-interval-span"
          style={{ left: `${spanLow * 100}%`, width: `${Math.max(0.4, (spanHigh - spanLow) * 100)}%` }}
          aria-hidden="true"
        />
        {marks.map(mark => {
          const labeled = withLabels && mark.mean - lastLabelPosition >= 0.085
          if (labeled) lastLabelPosition = mark.mean
          return (
            <Fragment key={mark.track}>
              {labeled && (
                <span className="track-dot-label" style={{ left: `${mark.mean * 100}%` }}>{trackTitle(mark.track)}</span>
              )}
              <span
                className="track-interval-dot"
                style={{ left: `${mark.mean * 100}%`, background: trackColor(mark.track, mark.index) }}
                tabIndex={0}
                aria-label={`${trackTitle(mark.track)}: mean ${fmt(mark.item.display_mean)}, ±2 SE ${fmt(Number(mark.item.display_se || 0))}, n=${mark.item.n}`}
              >
                <span className="track-interval-tip" role="tooltip">
                  <strong>{trackTitle(mark.track)}</strong>
                  <span>mean {fmt(mark.item.display_mean)}</span>
                  <span>±2 SE {fmt(Number(mark.item.display_se || 0))}</span>
                  <span>n={mark.item.n}</span>
                </span>
              </span>
            </Fragment>
          )
        })}
      </div>
    </div>
  )
}

function TrackSeparationPanel({ comparison }) {
  const trackRows = comparison.tracks || []
  const trackOrder = trackRows.map(row => row.track)
  const vectors = comparison.vectors || []
  if (!vectors.length || !trackOrder.length) return null
  return (
    <div className="card enterprise-panel">
      <div className="card-heading-row">
        <div>
          <div className="card-title-row">
            <div className="card-title">Trait Intensity by Track</div>
            <span className="surface-badge">Direct comparison</span>
          </div>
          <p className="muted-copy compact">
            Per-track trait means on a shared 0-1 intensity scale (0 is the lowest-scoring trace in the dataset, 1 the highest); the gray span connects the three tracks. Rows rank by the value after each trait: the share of trait variance explained by track. Hover a dot for the exact mean, ±2 SE, and n.
          </p>
        </div>
        <div className="track-legend" aria-label="Track legend">
          {trackRows.map((row, index) => (
            <span key={row.track} className="track-legend-item">
              <span className="track-legend-dot" style={{ background: trackColor(row.track, index) }} />
              {trackTitle(row.track)} · n={row.n}
            </span>
          ))}
        </div>
      </div>
      <div className="track-interval-plot">
        <div className="track-interval-row track-axis-header" aria-hidden="true">
          <div className="track-interval-label" />
          <div className="track-axis-ticks">
            {[0, 0.25, 0.5, 0.75, 1].map(tick => (
              <span
                key={tick}
                className={tick === 0 ? 'tick-start' : tick === 1 ? 'tick-end' : ''}
                style={{ left: `${tick * 100}%` }}
              >
                {tick === 0 || tick === 1 ? tick : tick.toFixed(2).replace('0.', '.')}
              </span>
            ))}
          </div>
        </div>
        {vectors.map((row, index) => (
          <TrackIntervalRow key={row.vector} row={row} trackOrder={trackOrder} withLabels={index === 0} />
        ))}
      </div>
    </div>
  )
}

function TrackScoreHeatmap({ comparison, taskLabel = 'seed' }) {
  const vectors = comparison.vectors || []
  const trackRows = comparison.tracks || []
  if (!vectors.length || !trackRows.length) return null
  const taskLabelText = taskLabel.toLowerCase()
  return (
    <div className="card enterprise-panel">
      <div className="card-heading-row">
        <div>
          <div className="card-title-row">
            <div className="card-title">Trait Scores by Track</div>
            <span className="surface-badge">{compactNumber(comparison.paired_task_count)} paired {taskLabelText}s</span>
          </div>
          <p className="muted-copy compact">
            Average trait score for each track, over the same {taskLabelText}s. Green is more of the trait, red is less; the deepest color marks the strongest score in each row. One trait per row.
          </p>
          <div className="heatmap-legend">
            <span>green = more of the trait</span>
            <span>red = less</span>
            <span>value = raw score mean</span>
          </div>
        </div>
      </div>
      <div
        className="track-contrast-grid"
        style={{ gridTemplateColumns: `minmax(160px, 1.1fr) repeat(${trackRows.length}, minmax(110px, 1fr))` }}
      >
        <div className="track-contrast-head track-contrast-trait">Trait</div>
        {trackRows.map((track, index) => (
          <div key={track.track} className="track-contrast-head">
            <span className="track-legend-dot" style={{ background: trackColor(track.track, index) }} />
            {trackTitle(track.track)}
          </div>
        ))}
        {vectors.map(row => {
          const byTrack = new Map((row.tracks || []).map(item => [item.track, item]))
          const rowMaxAbs = Math.max(
            ...(row.tracks || []).map(item => Math.abs(Number(item.basis_mean || 0))),
            0,
          )
          return (
            <Fragment key={row.vector}>
              <div className="track-contrast-trait">{vectorLabel(row.vector)}</div>
              {trackRows.map(track => {
                const item = byTrack.get(track.track)
                if (!item || item.basis_mean == null) {
                  return (
                    <div key={track.track} className="track-contrast-cell">
                      <span className="track-contrast-fill">-</span>
                    </div>
                  )
                }
                // Depth caps at zLike 1.3 (not zColor's 2.5 ceiling) so the
                // darkest fill still carries the default ink text.
                const zLike = rowMaxAbs ? 1.3 * Number(item.basis_mean) / rowMaxAbs : 0
                return (
                  <div
                    key={track.track}
                    className="track-contrast-cell"
                    title={`${trackTitle(track.track)} on ${vectorLabel(row.vector)}: raw mean ${fmt(item.basis_mean)}, sd ${fmt(item.basis_sd)}, normalized intensity ${fmt(item.display_mean)}, n=${item.n}`}
                  >
                    <span className="track-contrast-fill track-score-fill" style={{ background: zColor(zLike) }}>
                      {Number(item.basis_mean).toFixed(2)}
                    </span>
                  </div>
                )
              })}
            </Fragment>
          )
        })}
      </div>
    </div>
  )
}

function TrackShareChips({ tracks, order = [] }) {
  if (!tracks?.length) return null
  const indexByTrack = new Map(order.map((track, index) => [track, index]))
  return (
    <span className="track-share-chips">
      {tracks.map(group => (
        <span key={group.track} className="track-share-chip">
          <span className="track-legend-dot" style={{ background: trackColor(group.track, indexByTrack.get(group.track) ?? 0) }} />
          {trackTitle(group.track)} {pct(group.share)}
        </span>
      ))}
    </span>
  )
}

function CharacterTrackHeatmap({ points, meta }) {
  const tracks = meta.tracks || []
  const rows = points
    .filter(point => (point.tracks || []).some(track => track.mean_score != null))
    .map(point => {
      const means = point.tracks.map(track => Number(track.mean_score || 0))
      return { ...point, trackSpread: Math.max(...means) - Math.min(...means) }
    })
    .sort((a, b) => b.trackSpread - a.trackSpread)
  if (!tracks.length || !rows.length) return null
  return (
    <div className="card enterprise-panel">
      <div className="card-heading-row">
        <div>
          <div className="card-title-row">
            <div className="card-title">Trait Scores by Track</div>
            <span className="surface-badge">Direct comparison</span>
          </div>
          <p className="muted-copy compact">
            Mean raw trait score per track, in the same units for every cell. Green is a positive raw score
            (more of the trait), red negative, depth relative to the strongest score in the row. Rows rank by
            how far the tracks disagree. Hover for per-trace peaks.
          </p>
        </div>
      </div>
      <div
        className="track-contrast-grid"
        style={{ gridTemplateColumns: `minmax(160px, 1.1fr) repeat(${tracks.length}, minmax(110px, 1fr))` }}
      >
        <div className="track-contrast-head track-contrast-trait">Trait</div>
        {tracks.map((track, index) => (
          <div key={track} className="track-contrast-head">
            <span className="track-legend-dot" style={{ background: trackColor(track, index) }} />
            {trackTitle(track)}
          </div>
        ))}
        {rows.map(point => {
          const byTrack = new Map(point.tracks.map(track => [track.track, track]))
          const rowValues = point.tracks.map(track => Number(track.mean_score || 0))
          const rowMaxAbs = Math.max(...rowValues.map(Math.abs), 0.0001)
          const cellFor = (key, value, tooltip) => {
            if (value == null) {
              return (
                <div key={key} className="track-contrast-cell">
                  <span className="track-contrast-fill">-</span>
                </div>
              )
            }
            const zLike = 1.3 * Number(value) / rowMaxAbs
            return (
              <div key={key} className="track-contrast-cell" title={tooltip}>
                <span className="track-contrast-fill track-score-fill" style={{ background: zColor(zLike) }}>
                  {Number(value).toFixed(2)}
                </span>
              </div>
            )
          }
          return (
            <Fragment key={point.coordinate}>
              <div className="track-contrast-trait">{point.label}</div>
              {tracks.map(track => {
                const cell = byTrack.get(track)
                return cellFor(
                  track,
                  cell?.mean_score,
                  cell
                    ? `${trackTitle(track)} on ${point.label}: mean raw score ${fmt(cell.mean_score)}, mean per-trace peak ${fmt(cell.peak_mean)}, n=${cell.traces}`
                    : undefined,
                )
              })}
            </Fragment>
          )
        })}
      </div>
    </div>
  )
}

function TrackComparisonSection({ comparison, providerInfo = {} }) {
  if (!comparison?.available) return null
  return (
    <div className="overview-section">
      <div className="chart-row">
        <TrackSeparationPanel comparison={comparison} />
      </div>
      <div className="chart-row">
        <TrackScoreHeatmap comparison={comparison} taskLabel={providerInfo.task_label || 'seed'} />
      </div>
    </div>
  )
}

export { CharacterTrackHeatmap, TRACK_COLORS, TRACK_FALLBACK_COLORS, TrackComparisonSection, TrackIntervalRow, TrackScoreHeatmap, TrackSeparationPanel, TrackShareChips, trackColor, trackTitle }
