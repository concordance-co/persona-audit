// Report page.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { CharacterDrift, CharacterPortrait, joinTraits } from './Character.jsx'
import { getCharacter, getCharacterTrait, getTail } from '../../../api'
import { pct, pct1, titleize } from '../helpers'
import { useEffect, useState } from 'react'
import { useProviderSelection } from '../layout'

function ReportSection({ n, title, children }) {
  return (
    <section className="report-section">
      <h2 className="report-h2"><span className="report-num">{n}</span>{title}</h2>
      {children}
    </section>
  )
}

function Report() {
  const [provider] = useProviderSelection()
  const [char, setChar] = useState(null)
  const [details, setDetails] = useState({})
  const [tail, setTail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setChar(null)
    setDetails({})
    setTail(null)
    setError(null)
    getTail(provider).then(data => { if (active) setTail(data) }).catch(() => {})
    getCharacter(provider)
      .then(data => {
        if (!active) return
        setChar(data)
        const concern = new Set(data.meta?.concern_traits || [])
        const concernPoints = (data.points || [])
          .filter(p => concern.has(p.trait))
          .sort((a, b) => b.distinctiveness - a.distinctiveness)
        Promise.all(concernPoints.map(p =>
          getCharacterTrait(p.coordinate, provider)
            .then(detail => [p.coordinate, detail])
            .catch(() => [p.coordinate, null])
        )).then(entries => { if (active) setDetails(Object.fromEntries(entries)) })
      })
      .catch(err => { if (active) setError(String(err)) })
    return () => { active = false }
  }, [provider])

  if (error) return (
    <div>
      <h1 className="page-title">Report</h1>
      <p className="muted-copy">Could not load Report data: {error}</p>
    </div>
  )
  if (!char) return <h1 className="page-title">Loading...</h1>

  const points = char.points || []
  const meta = char.meta || {}
  const dropped = char.dropped || []
  const byDistinct = [...points].sort((a, b) => b.distinctiveness - a.distinctiveness)
  const distinctive = byDistinct.filter(p => p.distinctiveness > 0).slice(0, 3)
  const suppressed = [...points].sort((a, b) => a.distinctiveness - b.distinctiveness).filter(p => p.distinctiveness < 0).slice(0, 2)
  const concern = new Set(meta.concern_traits || [])
  const concernPoints = points.filter(p => concern.has(p.trait)).sort((a, b) => b.distinctiveness - a.distinctiveness)
  const topConcern = concernPoints[0] || null
  const topDetail = topConcern ? details[topConcern.coordinate] : null
  const modes = tail?.modes || []
  const scatter = tail?.scatter
  const tailMeta = tail?.meta || {}
  const tracesScored = points[0]?.audited_total
  const referenceTraces = points[0]?.reference_total
  const generatedOn = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })

  return (
    <div className="report">
      <div className="report-toolbar">
        <button type="button" onClick={() => window.print()}>Print / Save as PDF</button>
      </div>
      <article className="report-doc">
        <header className="report-cover">
          <div className="report-kicker">System Portrait · Behavioral Audit</div>
          <h1 className="report-title">{titleize(meta.audited_provider)} — Behavioral System Portrait</h1>
          {distinctive.length > 0 && (
            <p className="report-headline">
              Against the {meta.reference_provider} reference, this model is markedly more{' '}
              <strong>{joinTraits(distinctive.map(p => p.label))}</strong>
              {suppressed.length > 0 && <> — and notably less <strong>{joinTraits(suppressed.map(p => p.label))}</strong></>}.
            </p>
          )}
          <dl className="report-meta">
            <div><dt>Model corpus</dt><dd>{titleize(meta.audited_provider)}{tracesScored ? ` · ${tracesScored.toLocaleString()} conversations` : ''}</dd></div>
            <div><dt>Reference</dt><dd>{titleize(meta.reference_provider)}{referenceTraces ? ` · ${referenceTraces.toLocaleString()} conversations` : ''}</dd></div>
            <div><dt>Traits compared</dt><dd>{points.length} scored · {dropped.length} without reference</dd></div>
            <div><dt>Generated</dt><dd>{generatedOn}</dd></div>
          </dl>
          {meta.self_reference && (
            <p className="report-note">Note: the reference and audited corpus are identical, so distinctiveness is near zero by construction. Select a non-reference corpus for a meaningful portrait.</p>
          )}
        </header>

        <ReportSection n="1" title="What this model is">
          <p className="report-body">
            This portrait summarizes how the model behaves across {tracesScored ? tracesScored.toLocaleString() : 'its'} conversations,
            measured along {points.length} persona traits and compared against a reference model. The common case is the shared
            helpful-assistant baseline; what follows is what is <em>specific</em> to this model.
          </p>
          <div className="report-columns">
            <div>
              <div className="report-label">Most characteristic</div>
              <ul className="report-list">
                {distinctive.length ? distinctive.map(p => (
                  <li key={p.coordinate}><span>{p.label}</span><strong className="up">+{pct1(p.distinctiveness)}</strong></li>
                )) : <li><span className="muted-copy">None above reference.</span></li>}
              </ul>
            </div>
            <div>
              <div className="report-label">Most suppressed</div>
              <ul className="report-list">
                {suppressed.length ? suppressed.map(p => (
                  <li key={p.coordinate}><span>{p.label}</span><strong className="down">{pct1(p.distinctiveness)}</strong></li>
                )) : <li><span className="muted-copy">None below reference.</span></li>}
              </ul>
            </div>
          </div>
        </ReportSection>

        <ReportSection n="2" title="How to read this">
          <div className="report-box">
            <p>
              Every assistant turn is projected into a set of trait vector spaces and scored. A trait is counted
              <strong> present</strong> in a conversation when its peak score across the conversation's turns exceeds a threshold
              set at the 80th percentile of the reference model's peak scores for that trait.
            </p>
            <p>
              <strong>Frequency</strong> is the share of this model's conversations where a trait is present.
              <strong> Distinctiveness</strong> is that frequency minus the reference model's — isolating what is specific to this
              model rather than common to all assistants. Positive means the model does it more than the reference; negative means
              it is suppressed relative to the reference.
            </p>
          </div>
        </ReportSection>

        <ReportSection n="3" title="Character — the common case">
          <p className="report-body">
            Each trait is two measurements of one space: how often it appears (frequency) and how distinctive that is
            (signed lift over reference). Traits above the zero line are characteristic of this model; below it, suppressed.
          </p>
          <CharacterPortrait points={points} selected={null} onSelect={() => {}} />
          <table className="data-table report-table">
            <thead>
              <tr><th>Trait</th><th>Frequency</th><th>Reference</th><th>Distinctiveness</th></tr>
            </thead>
            <tbody>
              {byDistinct.map(p => (
                <tr key={p.coordinate}>
                  <td>{p.label}</td>
                  <td>{pct1(p.frequency)}</td>
                  <td>{pct1(p.reference_rate)}</td>
                  <td className={p.distinctiveness >= 0 ? 'up' : 'down'}>{p.distinctiveness >= 0 ? '+' : ''}{pct1(p.distinctiveness)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>

        <ReportSection n="4" title="Tail — the worst case">
          <p className="report-body">
            The tail — turns more extreme than this model's own 90th-percentile on any trait — clustered by their
            co-activation pattern into failure modes. A mode is a way the system fails (several traits jointly extreme
            in the same turn), not a single worst trait. Severity here is read against the model's <em>own</em> distribution,
            so it is independent of the {meta.reference_provider} reference used for Character. Modes are ordered by how bad a
            typical instance is; reach shows how far the mode goes.
          </p>
          {!tail
            ? <p className="muted-copy">Loading failure modes…</p>
            : modes.length === 0
              ? <p className="muted-copy">Not enough tail turns to form failure modes in this corpus.</p>
              : <>
                  <table className="data-table report-table">
                    <thead>
                      <tr><th>Failure mode</th><th>Turns</th><th>% of tail</th><th>% of traces</th><th>Typical z</th><th>Reach z</th></tr>
                    </thead>
                    <tbody>
                      {modes.map(m => (
                        <tr key={m.id}>
                          <td>{m.signature.length ? m.signature.map(s => `${s.gap >= 0 ? '↑' : '↓'}${s.label}`).join('  ') : 'Diffuse / weakly defined'}</td>
                          <td>{m.size_turns}</td>
                          <td>{pct(m.size_share)}</td>
                          <td>{pct(m.trace_share)}</td>
                          <td>{m.central_severity}</td>
                          <td>{m.reach}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {scatter && (
                    <p className="muted-copy compact">
                      Scattered tail: {pct(scatter.size_share)} of tail turns ({scatter.trace_count} traces) form no mode —
                      isolated one-off extremes, reported as a finding rather than forced into a cluster.
                    </p>
                  )}
                  <p className="muted-copy compact">
                    {tailMeta.n_tail_traces} of {tailMeta.total_traces} conversations have a tail moment. Each mode's
                    representative and worst cases are inspectable turn by turn in the live audit.
                  </p>
                </>}
        </ReportSection>

        <ReportSection n="5" title="Conversational drift">
          <p className="report-body">
            Behavior is not static within a conversation. For each risk surface, this shows how the behavior
            moves from the start of a conversation to the end, averaged across the corpus, against the reference.
            A rising line means the model intensifies that behavior as conversations progress.
          </p>
          {concernPoints.length === 0
            ? <p className="muted-copy">No concern traits with a {meta.reference_provider} reference in this corpus.</p>
            : concernPoints.map(p => (
                <div key={p.coordinate} className="report-drift-block">
                  <div className="report-label">{p.label} · start → end</div>
                  {details[p.coordinate]?.drift
                    ? <CharacterDrift drift={details[p.coordinate].drift} label={p.label} />
                    : <p className="muted-copy compact">No multi-turn conversations available.</p>}
                </div>
              ))}
        </ReportSection>

        <ReportSection n="6" title="Coverage & limitations">
          <ul className="report-body">
            <li>
              <strong>Reference is provisional.</strong> Distinctiveness is measured against the {meta.reference_provider} corpus,
              a different-domain benchmark used as a cold-start baseline. Some distinctiveness may reflect domain rather than model;
              a like-for-like base model is planned.
            </li>
            <li>
              <strong>Point-in-time snapshot.</strong> This reflects {tracesScored ? tracesScored.toLocaleString() : 'a fixed set of'} conversations
              and does not yet track drift over time.
            </li>
            {dropped.length > 0 && (
              <li>
                <strong>Traits without a reference ({dropped.length}).</strong> Scored for this model but absent from the reference,
                so distinctiveness cannot be computed and they are excluded from the portrait: {dropped.map(d => d.label).join(', ')}.
              </li>
            )}
          </ul>
        </ReportSection>

        <ReportSection n="7" title="Appendix · parameters">
          <dl className="report-meta">
            <div><dt>Presence rule</dt><dd>Any turn's peak projection score exceeds the trait threshold</dd></div>
            <div><dt>Threshold</dt><dd>80th percentile of the reference's per-conversation peak distribution, per trait</dd></div>
            <div><dt>Score family</dt><dd>{meta.score_family}</dd></div>
            <div><dt>Audited / reference</dt><dd>{meta.audited_provider} / {meta.reference_provider}</dd></div>
          </dl>
        </ReportSection>
      </article>
    </div>
  )
}

export { Report, ReportSection }
