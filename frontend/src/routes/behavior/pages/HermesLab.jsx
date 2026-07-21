// Hermes Lab page (mood orb, tabs).
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { CHART_GRID_COLOR, CHART_ZERO_COLOR, POSITIVE_COLOR, fmt, titleize } from '../helpers'
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { Link } from 'react-router-dom'
import { compactNumber } from '../shared.jsx'
import { getHermesOverview } from '../../../api'
import { providerPath } from '../layout'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useState } from 'react'

const HERMES_MOOD_SCALE = 0.6

function hermesClamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function hermesLerp(start, end, t) {
  return start + (end - start) * t
}

function hermesNorm(value) {
  return hermesClamp((value + HERMES_MOOD_SCALE) / (2 * HERMES_MOOD_SCALE), 0, 1)
}

function hermesMoodWord(valence, arousal) {
  if (Math.abs(valence) < 0.08 && Math.abs(arousal) < 0.08) return 'steady'
  return valence >= 0 ? (arousal >= 0 ? 'buzzing' : 'serene') : (arousal >= 0 ? 'tense' : 'subdued')
}

function hermesMoodTags(valence, arousal) {
  return [valence >= 0 ? 'warm' : 'cool', arousal >= 0 ? 'activated' : 'low energy']
}

function hermesOrbStyle(valence, arousal) {
  const valenceNorm = hermesNorm(valence)
  const arousalNorm = hermesNorm(arousal)
  const hue = hermesLerp(8, 162, valenceNorm)
  const saturation = hermesLerp(48, 92, arousalNorm)
  return {
    '--c-in': `hsl(${hue}, ${saturation}%, 72%)`,
    '--c-out': `hsl(${hue}, ${saturation}%, 44%)`,
    '--c-glow': `hsla(${hue}, ${saturation}%, 55%, 0.55)`,
    '--glow': `${Math.round(hermesLerp(28, 80, arousalNorm))}px`,
    '--pulse': `${hermesLerp(4.4, 1.2, arousalNorm).toFixed(2)}s`,
    '--pulse-scale': hermesLerp(1.03, 1.1, arousalNorm).toFixed(3),
  }
}

function HermesOrb({ mood, compact = false }) {
  const valence = Number(mood?.valence || 0)
  const arousal = Number(mood?.arousal || 0)
  return (
    <div className={`hermes-orb-stage${compact ? ' small' : ''}`}>
      <div className="hermes-orb" style={hermesOrbStyle(valence, arousal)} />
    </div>
  )
}

function HermesMoodTimeline({ timeline = [] }) {
  if (!timeline.length) {
    return (
      <div className="hermes-empty-panel">
        <div>No scored mood timeline yet</div>
        <p>Run the Hermes scoring workflow to populate valence, arousal, and dominant emotion over time.</p>
      </div>
    )
  }
  return (
    <ResponsiveContainer width="100%" height={220}>
      <ScatterChart margin={{ top: 16, right: 16, bottom: 24, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID_COLOR} />
        <XAxis type="number" dataKey="valence" domain={[-1, 1]} tickFormatter={fmt} name="Valence" />
        <YAxis type="number" dataKey="arousal" domain={[-1, 1]} tickFormatter={fmt} name="Arousal" />
        <Tooltip
          formatter={(value, name) => [fmt(value), name]}
          labelFormatter={(_, items) => {
            const row = items?.[0]?.payload
            return row ? `${row.title} / ${row.word}` : 'Hermes turn'
          }}
        />
        <ReferenceLine x={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <ReferenceLine y={0} stroke={CHART_ZERO_COLOR} strokeDasharray="2 3" />
        <Scatter data={timeline} fill={POSITIVE_COLOR} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}

function HermesTodayTab({ data }) {
  const source = data.source || {}
  const inventory = data.inventory || {}
  const mood = data.mood?.current
  const valence = Number(mood?.valence || 0)
  const arousal = Number(mood?.arousal || 0)
  const word = mood?.word || hermesMoodWord(valence, arousal)
  const dominant = mood?.dominant?.name ? titleize(mood.dominant.name) : 'waiting on emotion scores'
  const tags = hermesMoodTags(valence, arousal)
  return (
    <section className="hermes-today">
      <div className="hermes-local-badge">Runs locally from {source.using_smoke_fixture ? 'demo fixture' : 'Hermes state.db'}</div>
      <div className="hermes-today-card">
        <div className="hermes-today-row">
          <HermesOrb mood={mood} compact />
          <div className="hermes-today-headline">
            <div className="hermes-eyebrow">today / {compactNumber(inventory.assistant_turn_count || 0)} assistant turns read</div>
            <div className="hermes-mood-title">{data.mood?.available ? word : 'waiting'}</div>
            <div className="hermes-subline">
              {data.mood?.available ? <>feeling mostly <strong>{dominant}</strong></> : 'emotion scoring will light up the read'}
            </div>
          </div>
          <div className="hermes-streak-card">
            <strong>{compactNumber(inventory.reasoning_turn_count || 0)}</strong>
            <span>reasoning turns</span>
          </div>
        </div>
        <div className="hermes-mood-tags">
          {tags.map(tag => <span key={tag}>{tag}</span>)}
          <span>v {fmt(valence)}</span>
          <span>a {fmt(arousal)}</span>
        </div>
        <div className={`hermes-tell-card ${data.tell?.available ? 'hot' : 'calm'}`}>
          <div className="hermes-eyebrow">thought vs. said</div>
          <div className="hermes-tell-body">
            {data.tell?.available
              ? 'Reasoning and response scores are ready for contrast.'
              : 'Reasoning spans are loaded. Run Hermes scoring to compare inside voice against visible replies.'}
          </div>
          <div className="hermes-tell-foot">{data.tell?.status || 'waiting_for_reasoning_scores'}</div>
        </div>
        <p className="muted-copy compact">
          Trait-by-trait character analysis of this corpus lives on the shared{' '}
          <Link to={providerPath('/character', 'hermes')}>Character page</Link>.
        </p>
      </div>
      <div className="card enterprise-panel hermes-panel">
        <div className="card-heading-row">
          <div>
            <div className="card-title">Mood Timeline</div>
            <p className="muted-copy compact">Valence and arousal from scored emotion projections.</p>
          </div>
          <span className="surface-badge">{data.mood?.available ? `${data.mood.timeline?.length || 0} turns` : 'not scored'}</span>
        </div>
        <HermesMoodTimeline timeline={data.mood?.timeline || []} />
      </div>
    </section>
  )
}

function HermesSessionsTab({ data }) {
  const recent = data.recent_sessions || []
  return (
    <section className="card enterprise-panel hermes-panel">
      <div className="card-title">Recent Sessions</div>
      <div className="hermes-session-list">
        {recent.map(row => (
          <Link key={row.trace_id} className="hermes-session-item" to={providerPath(`/sessions/${encodeURIComponent(row.trace_id)}`, 'hermes')}>
            <div>
              <strong>{row.title || row.trace_id}</strong>
              <span>{row.source || '-'} / {row.model || 'unknown model'}</span>
            </div>
            <div>
              <span>{compactNumber(row.assistant_turn_count || row.turn_count || 0)} turns</span>
              <span>{compactNumber(row.reasoning_turn_count || 0)} reasoning</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  )
}

function HermesSetupTab({ data }) {
  const source = data.source || {}
  const inventory = data.inventory || {}
  const scoreFamilies = data.score_source?.families || []
  return (
    <section className="hermes-two-col">
      <div className="card enterprise-panel hermes-panel">
        <div className="card-title">Pipeline</div>
        <div className="hermes-pipeline">
          <div><span>Loaded</span><strong>{compactNumber(inventory.trace_count || 0)} sessions</strong></div>
          <div><span>Prepared</span><strong>{compactNumber(inventory.assistant_turn_count || 0)} assistant turns</strong></div>
          <div><span>Scores</span><strong>{scoreFamilies.length ? `${scoreFamilies.length} families` : 'not found'}</strong></div>
          <div><span>Mode</span><strong>{source.using_smoke_fixture ? 'demo fixture' : 'local Hermes'}</strong></div>
        </div>
      </div>
      <div className="card enterprise-panel hermes-panel">
        <div className="card-title">Local Setup</div>
        <p className="muted-copy compact">Set <code>BEHAVIOR_AUDIT_HERMES_STATE_DB</code> to a Hermes state database, or use the default <code>~/.hermes/state.db</code>.</p>
        <p className="muted-copy compact">Plan scoring with <code>uv run python -m pipelines_v2.cli workflow plan --file backend/workflows/hermes_scoring.py</code>.</p>
      </div>
    </section>
  )
}

function HermesLab() {
  const [tab, setTab] = useState('today')
  const { data, error } = useAsyncResource(() => getHermesOverview(), [])
  if (error) {
    return (
      <div className="page-header">
        <div>
          <h1 className="page-title">Hermes Lab</h1>
          <p className="muted-copy">Could not load Hermes data: {error}</p>
        </div>
      </div>
    )
  }
  if (!data) return <p className="muted-copy">Loading Hermes Lab...</p>

  const cards = data.cards || []
  const source = data.source || {}
  // Three tabs: the mood read (Today, with its timeline), the session list,
  // and setup. The former Overview tab duplicated Today with a larger orb;
  // the former Character tab was a placeholder — both folded away.
  const tabs = [
    ['today', 'Today'],
    ['sessions', 'Sessions'],
    ['setup', 'Setup'],
  ]

  return (
    <div className="hermes-page">
      <div className="hermes-topbar">
        <div>
          <div className="hermes-brand">Hermes Lab <small>local agent readout</small></div>
        </div>
        <nav className="hermes-tabs" aria-label="Hermes Lab sections">
          {tabs.map(([id, label]) => (
            <button key={id} type="button" className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="hermes-source-pill">{source.using_smoke_fixture ? 'Demo fixture' : 'Local data'}</div>
      </div>

      <div className="hermes-summary">
        {cards.map(card => (
          <div className="hermes-stat" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </div>
        ))}
      </div>

      {tab === 'sessions' ? <HermesSessionsTab data={data} />
        : tab === 'setup' ? <HermesSetupTab data={data} />
        : <HermesTodayTab data={data} />}
    </div>
  )
}

export { HERMES_MOOD_SCALE, HermesLab, HermesMoodTimeline, HermesOrb, HermesSessionsTab, HermesSetupTab, HermesTodayTab, hermesClamp, hermesLerp, hermesMoodTags, hermesMoodWord, hermesNorm, hermesOrbStyle }
