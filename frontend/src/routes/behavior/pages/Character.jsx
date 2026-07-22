// Character page and its chart components.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { CHART_GRID_COLOR, CHART_ZERO_COLOR, HIGHLIGHT_COLOR, POSITIVE_COLOR, fmt, pct, pct1 } from '../helpers'
import { CharacterTrackHeatmap, trackColor, trackTitle } from '../tracks.jsx'
import { Link } from 'react-router-dom'
import { getCharacter, getCharacterTrait } from '../../../api'
import { providerPath, useProviderSelection } from '../layout'
import { sessionFocusLink } from '../shared.jsx'
import { useEffect, useState } from 'react'

function CharacterScatterTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{point.track ? `${trackTitle(point.track)} · ${point.label}` : point.label}</div>
      <div>Frequency: {pct1(point.frequency)} of traces</div>
      <div>Distinctiveness: {point.distinctiveness >= 0 ? '+' : ''}{pct1(point.distinctiveness)} vs reference</div>
      <div className="muted-copy compact">Reference rate {pct1(point.reference_rate)} · {point.audited_present}/{point.audited_total} present</div>
    </div>
  )
}

function CharacterTraitLabel({ x, y, value }) {
  if (x == null || y == null) return null
  return (
    <text x={x} y={y - 9} textAnchor="middle" fontSize={10} fill="#080808" stroke="#fff8f4" strokeWidth={3} paintOrder="stroke" style={{ pointerEvents: 'none' }}>{value}</text>
  )
}

function CharacterDistributionTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">peak ≈ {Number(label).toFixed(2)}</div>
      {payload.map(entry => (
        <div key={entry.dataKey}>{entry.name}: {pct1(entry.value)}</div>
      ))}
    </div>
  )
}

function CharacterDistribution({ distribution, label }) {
  const bins = distribution?.bins || []
  const series = distribution?.series
  const selfProfile = Boolean(distribution?.self_profile)
  if (!bins.length) return null
  return (
    <div className="character-distribution">
      <p className="muted-copy compact">
        {series
          ? `Distribution of per-trace peak ${label?.toLowerCase()} raw scores per track, each as a share of its own traces. The dashed line marks the control track's mean per-trace peak.`
          : selfProfile
            ? `Distribution of per-trace peak ${label?.toLowerCase()} scores within this run. The dashed line marks the run's 80th percentile.`
            : `Distribution of per-trace peak ${label?.toLowerCase()} intensity — this model vs reference, each as a share of its own traces. The dashed line is the presence threshold; mass to its right is the tail.`}
      </p>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={bins} margin={{ top: 18, right: 16, left: 0, bottom: 4 }} barGap={0} barCategoryGap="8%">
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} vertical={false} />
          <XAxis type="number" dataKey="mid" domain={['dataMin', 'dataMax']} tickFormatter={value => Number(value).toFixed(1)} tick={{ fontSize: 10 }} />
          <YAxis tickFormatter={pct} tick={{ fontSize: 10 }} />
          <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<CharacterDistributionTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine x={distribution.threshold} stroke={HIGHLIGHT_COLOR} strokeDasharray="4 3" label={{ value: series ? 'control mean peak' : selfProfile ? '80th percentile' : 'threshold', fontSize: 10, position: 'top', fill: HIGHLIGHT_COLOR }} />
          {series ? (
            series.map((name, index) => (
              <Bar key={name} dataKey={name} name={trackTitle(name)} fill={trackColor(name, index)} isAnimationActive={false} />
            ))
          ) : selfProfile ? (
            <Bar dataKey="audited" name="This run" fill={CHARACTER_PEARL_COLOR} isAnimationActive={false} />
          ) : (
            <>
              <Bar dataKey="reference" name="Reference" fill={CHARACTER_REFERENCE_COLOR} isAnimationActive={false} />
              <Bar dataKey="audited" name="This model" fill={CHARACTER_PEARL_COLOR} isAnimationActive={false} />
            </>
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function CharacterDrift({ drift, label }) {
  const segments = drift?.segments || []
  const series = drift?.series
  const selfProfile = Boolean(drift?.self_profile)
  if (!segments.length) return null
  const summary = drift?.audited_summary || {}
  const multi = summary.multi_turn_traces || 0
  const lower = label?.toLowerCase()
  return (
    <div className="character-distribution">
      <p className="muted-copy compact">
        How {lower} intensity moves across a conversation (start → end), averaged over the corpus,
        {series ? ' per track.' : selfProfile ? ' within this run.' : ' vs reference.'}
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={segments} margin={{ top: 8, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} tickFormatter={value => Number(value).toFixed(1)} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(value, name) => [value == null ? '-' : Number(value).toFixed(3), name]} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {series ? (
            series.map((name, index) => (
              <Line
                key={name}
                type="monotone"
                dataKey={name}
                name={trackTitle(name)}
                stroke={trackColor(name, index)}
                strokeWidth={2}
                dot={name !== 'control'}
                isAnimationActive={false}
                connectNulls
              />
            ))
          ) : selfProfile ? (
            <Line type="monotone" dataKey="audited" name="This run" stroke={CHARACTER_PEARL_COLOR} strokeWidth={2} dot isAnimationActive={false} connectNulls />
          ) : (
            <>
              <Line type="monotone" dataKey="reference" name="Reference" stroke={CHARACTER_REFERENCE_COLOR} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
              <Line type="monotone" dataKey="audited" name="This model" stroke={CHARACTER_PEARL_COLOR} strokeWidth={2} dot isAnimationActive={false} connectNulls />
            </>
          )}
        </LineChart>
      </ResponsiveContainer>
      {series ? (
        (drift.series || []).map(name => {
          const trackSummary = drift.summaries?.[name]
          const trackMulti = trackSummary?.multi_turn_traces || 0
          if (!trackMulti) return null
          return (
            <p key={name} className="muted-copy compact">
              {trackTitle(name)}: {pct((trackSummary.rising || 0) / trackMulti)} of {trackMulti.toLocaleString()} multi-turn conversations rise in {lower},
              {' '}{pct((trackSummary.falling || 0) / trackMulti)} fall (mean change {trackSummary.mean_delta >= 0 ? '+' : ''}{fmt(trackSummary.mean_delta)}).
            </p>
          )
        })
      ) : (
        multi > 0 && (
          <p className="muted-copy compact">
            Within-conversation drift: {pct((summary.rising || 0) / multi)} of {multi.toLocaleString()} multi-turn conversations rise in {lower} from start to end,
            {' '}{pct((summary.falling || 0) / multi)} fall (mean change {summary.mean_delta >= 0 ? '+' : ''}{fmt(summary.mean_delta)}).
          </p>
        )
      )}
    </div>
  )
}

function CharacterDrilldown({ coordinate, provider, point }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setDetail(null)
    setError(null)
    getCharacterTrait(coordinate, provider)
      .then(data => { if (active) setDetail(data) })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [coordinate, provider])

  return (
    <div className="card">
      <div className="card-title">{point?.label} · distribution & traces</div>
      <p className="muted-copy compact">
        {detail?.meta?.reference_kind === 'track'
          ? <>Every audited trace ranked by peak {point?.label?.toLowerCase()} raw score, with its track. Click any trace to inspect it turn by turn in Session Review.</>
          : detail?.meta?.reference_kind === 'self_profile'
            ? <>The highest-scoring {point?.label?.toLowerCase()} traces in this run. Click any trace to inspect the underlying conversation turn by turn.</>
          : <>Traces whose peak {point?.label?.toLowerCase()} intensity exceeds the reference threshold, ranked by peak. Click any trace to inspect it turn by turn in Session Review.</>}
      </p>
      {error && <p className="muted-copy">Could not load traces: {error}</p>}
      {!detail && !error && <p className="muted-copy">Loading traces...</p>}
      {detail && (
        <>
          <CharacterDistribution distribution={detail.distribution} label={point?.label} />
          <CharacterDrift drift={detail.drift} label={point?.label} />
          <table className="data-table">
            <thead>
              <tr>
                <th>Trace</th>
                {detail.traces.some(row => row.track) && <th>Track</th>}
                <th>Peak score</th>
                <th>Trace mean</th>
                <th>Peak turn</th>
                <th>Turns</th>
              </tr>
            </thead>
            <tbody>
              {detail.traces.slice(0, 25).map(row => (
                <tr key={row.trace_id}>
                  <td>
                    <Link to={providerPath(sessionFocusLink(row.trace_id, {
                      coordinate,
                      vector: point?.trait,
                      family: 'persona',
                      turn: row.peak_turn,
                      source: 'character',
                    }), provider)}>{row.trace_id}</Link>
                  </td>
                  {detail.traces.some(item => item.track) && <td>{trackTitle(row.track)}</td>}
                  <td>{fmt(row.max_score)}</td>
                  <td>{fmt(row.mean_score)}</td>
                  <td>{row.peak_turn ?? '-'}</td>
                  <td>{row.turns}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(detail.point.audited_present ?? detail.point.audited_total) > 25 && (
            <p className="muted-copy compact">
              {detail.meta?.reference_kind === 'self_profile'
                ? `Showing the 25 highest-scoring of ${detail.point.audited_present ?? detail.point.audited_total} traces above the run's 80th percentile.`
                : `Showing the 25 most extreme of ${detail.point.audited_present ?? detail.point.audited_total} traces.`}
            </p>
          )}
        </>
      )}
    </div>
  )
}

const CHARACTER_PEARL_COLOR = '#4A6FE0'
const CHARACTER_REFERENCE_COLOR = '#B8B1AA'
const CHARACTER_VARIATION_COLOR = '#B7791F'

function characterCoord(entry) {
  return entry?.coordinate || entry?.payload?.coordinate || null
}

function joinTraits(labels) {
  const lower = labels.map(label => label.toLowerCase())
  if (lower.length <= 1) return lower.join('')
  if (lower.length === 2) return `${lower[0]} and ${lower[1]}`
  return `${lower.slice(0, -1).join(', ')}, and ${lower[lower.length - 1]}`
}

function CharacterSignature({ points, meta, selected, onSelect }) {
  const byDistinct = [...points].sort((a, b) => b.distinctiveness - a.distinctiveness)
  const distinctive = byDistinct.filter(p => p.distinctiveness > 0).slice(0, 3)
  const suppressed = [...points].sort((a, b) => a.distinctiveness - b.distinctiveness).filter(p => p.distinctiveness < 0).slice(0, 2)

  const Chip = ({ point, sign }) => (
    <button
      type="button"
      className={`character-chip ${sign} ${point.coordinate === selected ? 'active' : ''}`}
      onClick={() => onSelect(point.coordinate)}
    >
      <span>{point.label}</span>
      <strong>{point.distinctiveness >= 0 ? '+' : ''}{pct1(point.distinctiveness)}</strong>
    </button>
  )

  return (
    <>
      {(distinctive.length > 0 || suppressed.length > 0) && (
        <p className="character-headline">
          Against the {meta.reference_provider} reference, this model is markedly more{' '}
          <strong>{joinTraits(distinctive.map(p => p.label))}</strong>
          {suppressed.length > 0 && <> — and notably less <strong>{joinTraits(suppressed.map(p => p.label))}</strong></>}.
        </p>
      )}
      <div className="character-signature-grid">
        <div className="card">
          <div className="card-title">Most characteristic</div>
          <p className="muted-copy compact">Traits this model shows far more than the reference.</p>
          <div className="character-chip-row">
            {distinctive.length ? distinctive.map(p => <Chip key={p.coordinate} point={p} sign="up" />) : <span className="muted-copy compact">None above reference.</span>}
          </div>
        </div>
        <div className="card">
          <div className="card-title">Most suppressed</div>
          <p className="muted-copy compact">Traits this model shows less than the reference.</p>
          <div className="character-chip-row">
            {suppressed.length ? suppressed.map(p => <Chip key={p.coordinate} point={p} sign="down" />) : <span className="muted-copy compact">None below reference.</span>}
          </div>
        </div>
      </div>
    </>
  )
}

function SelfCharacterTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{point.label}</div>
      <div>Mean raw score: {fmt(point.mean_score)}</div>
      <div>Middle 80%: {fmt(point.trace_p10)} to {fmt(point.trace_p90)}</div>
      <div>Trace spread: {fmt(point.trace_spread)}</div>
      <div className="muted-copy compact">mean per-trace peak {fmt(point.peak_mean)} · n={point.trace_count}</div>
    </div>
  )
}

function SelfCharacterSummary({ points, selected, onSelect }) {
  const levels = [...points].filter(point => point.mean_score != null).sort((a, b) => b.mean_score - a.mean_score).slice(0, 3)
  const variable = [...points].filter(point => point.trace_spread != null).sort((a, b) => b.trace_spread - a.trace_spread).slice(0, 3)
  const traceCount = Math.max(0, ...points.map(point => Number(point.trace_count || 0)))
  const Chip = ({ point, metric, tone }) => (
    <button
      type="button"
      className={`character-chip ${tone} ${point.coordinate === selected ? 'active' : ''}`}
      onClick={() => onSelect(point.coordinate)}
    >
      <span>{point.label}</span>
      <strong>{fmt(point[metric])}</strong>
    </button>
  )

  return (
    <>
      <p className="character-headline">
        Across <strong>{traceCount.toLocaleString()} traces</strong>, the highest average signals are{' '}
        <strong>{joinTraits(levels.map(point => point.label))}</strong>;{' '}
        <strong>{joinTraits(variable.map(point => point.label))}</strong> vary most from conversation to conversation.
      </p>
      <div className="character-signature-grid">
        <div className="card">
          <div className="card-title">Highest average levels</div>
          <p className="muted-copy compact">Mean raw score across each trace; descriptive, not relative to another model.</p>
          <div className="character-chip-row">
            {levels.map(point => <Chip key={point.coordinate} point={point} metric="mean_score" tone="level" />)}
          </div>
        </div>
        <div className="card">
          <div className="card-title">Most variable across traces</div>
          <p className="muted-copy compact">Width of the middle 80% of per-trace mean scores.</p>
          <div className="character-chip-row">
            {variable.map(point => <Chip key={point.coordinate} point={point} metric="trace_spread" tone="variation" />)}
          </div>
        </div>
      </div>
    </>
  )
}

function SelfCharacterProfile({ points, selected, onSelect }) {
  const data = points.filter(point => point.mean_score != null && point.trace_spread != null)
  return (
    <ResponsiveContainer width="100%" height={460}>
      <ScatterChart margin={{ top: 24, right: 28, left: 8, bottom: 44 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
        <XAxis
          type="number"
          dataKey="mean_score"
          name="Mean raw score"
          domain={['auto', 'auto']}
          tickFormatter={value => Number(value).toFixed(1)}
          tick={{ fontSize: 11 }}
          label={{ value: 'Mean raw trait score', position: 'bottom', offset: 18, fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="trace_spread"
          name="Trace spread"
          domain={[0, 'auto']}
          tickFormatter={value => Number(value).toFixed(1)}
          tick={{ fontSize: 11 }}
          label={{ value: 'Trace-to-trace spread (P90 − P10)', angle: -90, position: 'left', offset: -2, fontSize: 12 }}
        />
        <ZAxis range={[140, 140]} />
        <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<SelfCharacterTooltip />} />
        <Scatter data={data} isAnimationActive={false} onClick={entry => onSelect(characterCoord(entry))} cursor="pointer">
          <LabelList dataKey="label" content={<CharacterTraitLabel />} />
          {data.map(point => (
            <Cell
              key={point.coordinate}
              fill={CHARACTER_PEARL_COLOR}
              fillOpacity={point.coordinate === selected ? 1 : 0.72}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 2 : 0}
            />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  )
}

function SelfCharacterBars({ points, metric, selected, onSelect }) {
  const variation = metric === 'trace_spread'
  const data = [...points].filter(point => point[metric] != null).sort((a, b) => b[metric] - a[metric])
  const height = Math.max(360, data.length * 34 + 48)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} horizontal={false} />
        <XAxis type="number" domain={variation ? [0, 'auto'] : ['auto', 'auto']} tickFormatter={value => Number(value).toFixed(1)} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="label" width={96} interval={0} tick={{ fontSize: 11 }} />
        {!variation && <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} />}
        <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<SelfCharacterTooltip />} />
        <Bar dataKey={metric} name={variation ? 'Trace spread' : 'Mean raw score'} radius={[0, 4, 4, 0]} isAnimationActive={false} cursor="pointer" onClick={entry => onSelect(characterCoord(entry))}>
          {data.map(point => (
            <Cell
              key={point.coordinate}
              fill={variation ? CHARACTER_VARIATION_COLOR : CHARACTER_PEARL_COLOR}
              fillOpacity={point.coordinate === selected ? 1 : 0.82}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 1.5 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function TrackCharacterSignature({ report, selected, onSelect }) {
  const points = report.points || []
  const higher = [...points].sort((a, b) => b.delta - a.delta).filter(p => p.delta > 0).slice(0, 3)
  const lower = [...points].sort((a, b) => a.delta - b.delta).filter(p => p.delta < 0).slice(0, 2)
  const subject = trackTitle(report.track)

  const Chip = ({ point, sign }) => (
    <button
      type="button"
      className={`character-chip ${sign} ${point.coordinate === selected ? 'active' : ''}`}
      onClick={() => onSelect(point.coordinate)}
      title={`${subject} mean ${fmt(point.mean_score)} vs control ${fmt(point.control_mean_score)} (raw score)`}
    >
      <span>{point.label}</span>
      <strong>{point.delta >= 0 ? '+' : ''}{Number(point.delta).toFixed(2)}</strong>
    </button>
  )

  return (
    <>
      {(higher.length > 0 || lower.length > 0) && (
        <p className="character-headline">
          Against control, {subject} scores highest above on{' '}
          <strong>{joinTraits(higher.map(p => p.label))}</strong>
          {lower.length > 0 && <> — and furthest below on <strong>{joinTraits(lower.map(p => p.label))}</strong></>}.
        </p>
      )}
      <div className="character-signature-grid">
        <div className="card">
          <div className="card-title">Furthest above control · {subject}</div>
          <p className="muted-copy compact">Largest positive raw-score deltas vs the control track.</p>
          <div className="character-chip-row">
            {higher.length ? higher.map(p => <Chip key={p.coordinate} point={p} sign="up" />) : <span className="muted-copy compact">None above control.</span>}
          </div>
        </div>
        <div className="card">
          <div className="card-title">Furthest below control · {subject}</div>
          <p className="muted-copy compact">Largest negative raw-score deltas vs the control track.</p>
          <div className="character-chip-row">
            {lower.length ? lower.map(p => <Chip key={p.coordinate} point={p} sign="down" />) : <span className="muted-copy compact">None below control.</span>}
          </div>
        </div>
      </div>
    </>
  )
}

function mergeTrackPoints(reports = []) {
  const byCoordinate = new Map()
  for (const report of reports) {
    for (const point of report.points || []) {
      const entry = byCoordinate.get(point.coordinate) || {
        coordinate: point.coordinate,
        label: point.label,
        control_mean_score: point.control_mean_score,
      }
      entry[point.track || report.track] = point
      byCoordinate.set(point.coordinate, entry)
    }
  }
  return [...byCoordinate.values()]
}

function rawScore(value) {
  return value == null ? '-' : Number(value).toFixed(2)
}

function TrackCharacterTooltip({ active, payload, label, formatter = rawScore }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{payload[0]?.payload?.label || label}</div>
      {payload.map(entry => (
        <div key={entry.dataKey}>{entry.name}: {formatter(entry.value)}</div>
      ))}
    </div>
  )
}

function TrackPortraitTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{trackTitle(point.track)} · {point.label}</div>
      <div>Mean raw score: {fmt(point.mean_score)}</div>
      <div>Control mean: {fmt(point.control_mean_score)}</div>
      <div>Δ vs control: {point.delta >= 0 ? '+' : ''}{fmt(point.delta)}</div>
      <div className="muted-copy compact">mean per-trace peak {fmt(point.peak_mean)} · n={point.traces}</div>
    </div>
  )
}

function TrackCharacterPortrait({ reports, selected, onSelect }) {
  const allPoints = reports.flatMap(report => (report.points || []).map(point => ({ ...point, track: report.track })))
  const xValues = allPoints.map(point => Number(point.mean_score || 0))
  const yValues = allPoints.map(point => Number(point.delta || 0))
  const xPad = Math.max(0.15, (Math.max(...xValues) - Math.min(...xValues)) * 0.08)
  const yPad = Math.max(0.15, (Math.max(...yValues) - Math.min(...yValues)) * 0.08)
  const xDomain = [Math.min(...xValues) - xPad, Math.max(...xValues) + xPad]
  const yDomain = [Math.min(0, ...yValues) - yPad, Math.max(0, ...yValues) + yPad]
  return (
    <ResponsiveContainer width="100%" height={460}>
      <ScatterChart margin={{ top: 24, right: 48, left: 8, bottom: 44 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
        <XAxis
          type="number"
          dataKey="mean_score"
          name="Mean raw score"
          domain={xDomain}
          tickFormatter={value => Number(value).toFixed(1)}
          tick={{ fontSize: 11 }}
          label={{ value: 'Mean raw trait score', position: 'bottom', offset: 18, fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="delta"
          name="Delta vs control"
          domain={yDomain}
          tickFormatter={value => Number(value).toFixed(1)}
          tick={{ fontSize: 11 }}
          label={{ value: 'Δ mean raw score vs control', angle: -90, position: 'left', offset: -2, fontSize: 12 }}
        />
        <ZAxis range={[140, 140]} />
        <ReferenceLine y={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<TrackPortraitTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {reports.map((report, index) => {
          const data = (report.points || []).map(point => ({ ...point, track: report.track }))
          return (
            <Scatter
              key={report.track}
              name={trackTitle(report.track)}
              data={data}
              fill={trackColor(report.track, index)}
              isAnimationActive={false}
              onClick={entry => onSelect(characterCoord(entry))}
              cursor="pointer"
            >
              <LabelList dataKey="label" content={<CharacterTraitLabel />} />
              {data.map(point => (
                <Cell
                  key={point.coordinate}
                  fill={trackColor(report.track, index)}
                  fillOpacity={point.coordinate === selected ? 1 : 0.78}
                  stroke={point.coordinate === selected ? '#080808' : 'none'}
                  strokeWidth={point.coordinate === selected ? 2 : 0}
                />
              ))}
            </Scatter>
          )
        })}
      </ScatterChart>
    </ResponsiveContainer>
  )
}

function TrackCharacterSpectrum({ reports, selected, onSelect }) {
  const data = mergeTrackPoints(reports)
    .map(row => ({
      ...row,
      ...Object.fromEntries(reports.map(report => [report.track, row[report.track]?.delta ?? null])),
      spread: Math.max(...reports.map(report => Math.abs(row[report.track]?.delta ?? 0))),
    }))
    .sort((a, b) => b.spread - a.spread)
  const bound = Math.max(0.2, ...data.map(row => row.spread))
  const padded = Math.ceil(bound * 11) / 10
  const height = Math.max(360, data.length * 40 + 48)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }} barGap={2}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} horizontal={false} />
        <XAxis type="number" domain={[-padded, padded]} tickFormatter={value => Number(value).toFixed(1)} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="label" width={96} interval={0} tick={{ fontSize: 11 }} />
        <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} />
        <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<TrackCharacterTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {reports.map((report, index) => (
          <Bar
            key={report.track}
            dataKey={report.track}
            name={trackTitle(report.track)}
            fill={trackColor(report.track, index)}
            radius={[0, 4, 4, 0]}
            isAnimationActive={false}
            cursor="pointer"
            onClick={entry => onSelect(characterCoord(entry))}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

function TrackCharacterLevels({ reports, selected, onSelect }) {
  const data = mergeTrackPoints(reports)
    .map(row => ({
      ...row,
      control: row.control_mean_score ?? null,
      ...Object.fromEntries(reports.map(report => [report.track, row[report.track]?.mean_score ?? null])),
    }))
    .sort((a, b) => Math.max(...reports.map(r => Math.abs(b[r.track] ?? 0))) - Math.max(...reports.map(r => Math.abs(a[r.track] ?? 0))))
  const height = Math.max(360, data.length * 52 + 48)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }} barGap={2}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} horizontal={false} />
        <XAxis type="number" domain={['auto', 'auto']} tickFormatter={value => Number(value).toFixed(1)} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="label" width={96} interval={0} tick={{ fontSize: 11 }} />
        <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} />
        <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<TrackCharacterTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        {reports.map((report, index) => (
          <Bar
            key={report.track}
            dataKey={report.track}
            name={trackTitle(report.track)}
            fill={trackColor(report.track, index)}
            radius={[0, 3, 3, 0]}
            isAnimationActive={false}
            cursor="pointer"
            onClick={entry => onSelect(characterCoord(entry))}
          />
        ))}
        <Bar dataKey="control" name="Control" fill={trackColor('control')} radius={[0, 3, 3, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function CharacterBarTooltip({ active, payload, mode }) {
  if (!active || !payload || !payload.length) return null
  const point = payload[0]?.payload
  if (!point) return null
  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{point.label}</div>
      {mode === 'frequency' ? (
        <>
          <div>This model: {pct1(point.frequency)}</div>
          <div>Reference: {pct1(point.reference_rate)}</div>
        </>
      ) : (
        <div>Distinctiveness: {point.distinctiveness >= 0 ? '+' : ''}{pct1(point.distinctiveness)}</div>
      )}
      <div className="muted-copy compact">{point.audited_present}/{point.audited_total} traces present</div>
    </div>
  )
}

function CharacterSpectrum({ points, selected, onSelect }) {
  const data = [...points].sort((a, b) => b.distinctiveness - a.distinctiveness)
  const bound = Math.max(0.05, ...data.map(p => Math.abs(p.distinctiveness)))
  const padded = Math.ceil(bound * 110) / 100
  const height = Math.max(360, data.length * 30 + 48)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} horizontal={false} />
        <XAxis type="number" domain={[-padded, padded]} tickFormatter={pct} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="label" width={96} interval={0} tick={{ fontSize: 11 }} />
        <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} />
        <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<CharacterBarTooltip mode="signature" />} />
        <Bar dataKey="distinctiveness" radius={[0, 4, 4, 0]} isAnimationActive={false} cursor="pointer" onClick={entry => onSelect(characterCoord(entry))}>
          {data.map(point => (
            <Cell
              key={point.coordinate}
              fill={point.distinctiveness >= 0 ? POSITIVE_COLOR : HIGHLIGHT_COLOR}
              fillOpacity={point.coordinate === selected ? 1 : 0.78}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 1.5 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function CharacterFrequency({ points, selected, onSelect }) {
  const data = [...points].sort((a, b) => b.frequency - a.frequency)
  const height = Math.max(360, data.length * 34 + 48)
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart layout="vertical" data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }} barGap={2}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} horizontal={false} />
        <XAxis type="number" domain={[0, 1]} tickFormatter={pct} tick={{ fontSize: 11 }} />
        <YAxis type="category" dataKey="label" width={96} interval={0} tick={{ fontSize: 11 }} />
        <Tooltip cursor={{ fill: 'rgba(8,8,8,0.04)' }} content={<CharacterBarTooltip mode="frequency" />} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Bar dataKey="reference_rate" name="Reference" fill={CHARACTER_REFERENCE_COLOR} radius={[0, 3, 3, 0]} isAnimationActive={false} />
        <Bar dataKey="frequency" name="This model" fill={CHARACTER_PEARL_COLOR} radius={[0, 3, 3, 0]} isAnimationActive={false} cursor="pointer" onClick={entry => onSelect(characterCoord(entry))}>
          {data.map(point => (
            <Cell
              key={point.coordinate}
              fillOpacity={point.coordinate === selected ? 1 : 0.85}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 1.5 : 0}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function CharacterPortrait({ points, selected, onSelect }) {
  const values = points.map(p => p.distinctiveness)
  const lo = Math.min(0, ...values)
  const hi = Math.max(0, ...values)
  const pad = Math.max(0.03, (hi - lo) * 0.1)
  const yDomain = [Math.floor((lo - pad) * 100) / 100, Math.ceil((hi + pad) * 100) / 100]
  return (
    <ResponsiveContainer width="100%" height={460}>
      <ScatterChart margin={{ top: 24, right: 28, left: 8, bottom: 44 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
        <XAxis
          type="number"
          dataKey="frequency"
          name="Frequency"
          domain={[0, 1]}
          tickFormatter={pct}
          tick={{ fontSize: 11 }}
          label={{ value: 'Frequency (share of traces present)', position: 'bottom', offset: 18, fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="distinctiveness"
          name="Distinctiveness"
          domain={yDomain}
          tickFormatter={pct}
          tick={{ fontSize: 11 }}
          label={{ value: 'Distinctiveness (signed lift)', angle: -90, position: 'left', offset: -2, fontSize: 12 }}
        />
        <ZAxis range={[140, 140]} />
        <ReferenceLine y={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} content={<CharacterScatterTooltip />} />
        <Scatter
          data={points}
          isAnimationActive={false}
          onClick={entry => onSelect(characterCoord(entry))}
          cursor="pointer"
        >
          <LabelList dataKey="label" content={<CharacterTraitLabel />} />
          {points.map(point => (
            <Cell
              key={point.coordinate}
              fill={point.distinctiveness >= 0 ? POSITIVE_COLOR : HIGHLIGHT_COLOR}
              fillOpacity={point.coordinate === selected ? 1 : 0.72}
              stroke={point.coordinate === selected ? '#080808' : 'none'}
              strokeWidth={point.coordinate === selected ? 2 : 0}
            />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  )
}

const CHARACTER_MODES = [
  ['portrait', 'Portrait', 'Two measurements of one space: frequency on x, signed distinctiveness on y. Above the line is distinctive, below is suppressed. Click a trait to drill in.'],
  ['signature', 'Signature', 'Traits ranked by signed lift over the reference — the model’s characteristic signature at a glance. Click a bar to drill in.'],
  ['frequency', 'Frequency', 'How often each trait is present in this model vs the reference. Frequency keeps distinctiveness honest. Click a bar to drill in.'],
]

const SELF_CHARACTER_MODES = [
  ['portrait', 'Profile', 'Average level on x and trace-to-trace variation on y. Upper-right traits are both stronger and less consistent within this run. Neither axis is a quality or risk judgment. Click a trait to drill in.'],
  ['levels', 'Levels', 'Traits ranked by mean raw score across traces. This describes the run’s average posture without claiming distinctiveness from another model. Click a bar to drill in.'],
  ['variation', 'Variation', 'Traits ranked by the width of their middle 80% across traces. Wider bars mean the model varies more from conversation to conversation. Click a bar to drill in.'],
]

// Track mode swaps every measure to raw score units: no present-rates, no
// threshold-crossing counts — mean raw scores and their deltas vs control.
const TRACK_CHARACTER_MODES = [
  ['portrait', 'Portrait', 'Two raw measurements of one space: how strongly the trait reads (x, mean raw score) and how far that sits from control (y, Δ raw score). The zero line is control. Click a trait to drill in.'],
  ['signature', 'Deltas', 'Traits ranked by raw-score delta vs control — each persona’s signature in score units. Click a bar to drill in.'],
  ['frequency', 'Levels', 'Mean raw score per trait for each persona, with control alongside in the same units. Click a bar to drill in.'],
]

function Character() {
  const [provider] = useProviderSelection()
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [mode, setMode] = useState('portrait')

  useEffect(() => {
    let active = true
    setPayload(null)
    setError(null)
    setSelected(null)
    getCharacter(provider)
      .then(data => { if (active) setPayload(data) })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Character</h1>
      <p className="muted-copy">Could not load Character data: {error}</p>
    </div>
  )
  if (!payload) return <h1 className="page-title">Loading...</h1>

  const points = payload.points || []
  const dropped = payload.dropped || []
  const meta = payload.meta || {}
  // Track-comparison corpora (the persona demo) use the control track as the
  // reference corpus: Sol and Marrow each get the full Character treatment
  // against control, and the views overlay both personas for direct contrast.
  const trackReports = payload.track_reports || []
  const trackMode = (meta.tracks || []).length > 0 && trackReports.length > 0
  const selfMode = !trackMode && Boolean(meta.self_reference)
  const selectedPoint = points.find(p => p.coordinate === selected) || null
  const modeOptions = trackMode ? TRACK_CHARACTER_MODES : selfMode ? SELF_CHARACTER_MODES : CHARACTER_MODES
  const modeCopy = modeOptions.find(([id]) => id === mode)?.[2]

  return (
    <div>
      <h1 className="page-title">Character</h1>
      {trackMode ? (
        <p className="muted-copy">
          What each persona does in the common case, measured against the <strong>control track</strong> as
          the reference — the same seed conversations answered by a plain assistant. Everything here is in
          raw score units: each persona's mean trait score, the control's mean, and the signed delta
          between them.
        </p>
      ) : selfMode ? (
        <p className="muted-copy">
          Within-run behavior profile for <strong>{meta.audited_provider}</strong>. Because this demo has no
          external control corpus, the page describes average trait levels and trace-to-trace variation in
          raw score units. It does not claim that these traits are distinctive from another model.
        </p>
      ) : (
        <p className="muted-copy">
          What this model does in the common case. Each persona trait is measured two ways: how often it
          shows up ({meta.audited_provider}) and how distinctive that is against the {meta.reference_provider}{' '}
          reference. The most frequent behavior is the shared helpful-assistant baseline; distinctiveness is
          what is specific to this model.
        </p>
      )}

      {trackMode
        ? trackReports.map(report => (
            <TrackCharacterSignature
              key={report.track}
              report={report}
              selected={selected}
              onSelect={setSelected}
            />
          ))
        : selfMode
          ? <SelfCharacterSummary points={points} selected={selected} onSelect={setSelected} />
        : points.length > 0 && (
            <CharacterSignature points={points} meta={meta} selected={selected} onSelect={setSelected} />
          )}

      <div className="card">
        <div className="card-heading-row">
          <div className="card-title">
            {trackMode
              ? `Persona traits vs control · ${points.length} scored`
              : selfMode
                ? `Within-run persona profile · ${points.length} scored`
                : `Persona traits · ${points.length} scored`}
          </div>
          <div className="segmented-control">
            {modeOptions.map(([id, label]) => (
              <button key={id} type="button" className={mode === id ? 'active' : ''} onClick={() => setMode(id)}>{label}</button>
            ))}
          </div>
        </div>
        <p className="muted-copy compact">{modeCopy}</p>
        {points.length === 0
          ? <p className="muted-copy">{selfMode ? 'No scored persona traits are available for this run.' : `No persona traits with a ${meta.reference_provider} reference in this corpus.`}</p>
          : trackMode
            ? mode === 'portrait'
              ? <TrackCharacterPortrait reports={trackReports} selected={selected} onSelect={setSelected} />
              : mode === 'signature'
                ? <TrackCharacterSpectrum reports={trackReports} selected={selected} onSelect={setSelected} />
                : <TrackCharacterLevels reports={trackReports} selected={selected} onSelect={setSelected} />
            : selfMode
              ? mode === 'portrait'
                ? <SelfCharacterProfile points={points} selected={selected} onSelect={setSelected} />
                : <SelfCharacterBars points={points} metric={mode === 'variation' ? 'trace_spread' : 'mean_score'} selected={selected} onSelect={setSelected} />
            : mode === 'portrait'
              ? <CharacterPortrait points={points} selected={selected} onSelect={setSelected} />
              : mode === 'signature'
                ? <CharacterSpectrum points={points} selected={selected} onSelect={setSelected} />
                : <CharacterFrequency points={points} selected={selected} onSelect={setSelected} />}
      </div>

      {trackMode && <CharacterTrackHeatmap points={points} meta={meta} />}

      {selectedPoint && (
        <CharacterDrilldown coordinate={selectedPoint.coordinate} provider={provider} point={selectedPoint} />
      )}

      {dropped.length > 0 && (
        <div className="card">
          <div className="card-title">{selfMode ? 'Not shown · insufficient scored traces' : `Not shown · no ${meta.reference_provider} reference`}</div>
          <p className="muted-copy compact">
            {selfMode
              ? 'These traits do not have enough scored traces for a stable within-run profile. Reported, never silently dropped.'
              : <>These traits are scored for {meta.audited_provider} but absent from the {meta.reference_provider}{' '}reference, so distinctiveness cannot be computed. Reported, never silently dropped.</>}
          </p>
          <div className="tag-row">
            {dropped.map(item => <span key={item.coordinate} className="tag">{item.label}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}

export { CHARACTER_MODES, CHARACTER_PEARL_COLOR, CHARACTER_REFERENCE_COLOR, SELF_CHARACTER_MODES, Character, CharacterBarTooltip, CharacterDistribution, CharacterDistributionTooltip, CharacterDrift, CharacterDrilldown, CharacterFrequency, CharacterPortrait, CharacterScatterTooltip, CharacterSignature, CharacterSpectrum, CharacterTraitLabel, SelfCharacterBars, SelfCharacterProfile, SelfCharacterSummary, TRACK_CHARACTER_MODES, TrackCharacterLevels, TrackCharacterPortrait, TrackCharacterSignature, TrackCharacterSpectrum, TrackCharacterTooltip, TrackPortraitTooltip, characterCoord, joinTraits, mergeTrackPoints, rawScore }
