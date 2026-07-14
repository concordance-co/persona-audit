// Registry (scoring spaces) page.
// Moved verbatim from BehaviorAuditRoutes.jsx (pure reorganization).
import { compactNumber, vectorLabel } from '../shared.jsx'
import { familyTitle } from '../helpers'
import { getEmotions, getScoreSpaces } from '../../../api'
import { useAsyncResource } from '../../../hooks/useAsyncResource'
import { useProviderSelection } from '../layout'

function RegistrySpaceCard({ space }) {
  const coordinates = space.coordinates || space.pilot_coordinates || space.domains || []
  const requirements = space.requires || []
  return (
    <div className="card registry-space-card">
      <div className="registry-space-header">
        <div>
          <div className="card-title">{space.label}</div>
          <div className="asset-title">{familyTitle(space.family)}</div>
        </div>
        <span className="status-pill">{space.status}</span>
      </div>
      <div className="asset-meta">
        <span>{space.score_kind}</span>
        <span>{space.model}</span>
        <span>Layer {space.layer}</span>
        <span>{compactNumber(space.coordinate_count)} coordinates</span>
      </div>
      {coordinates.length > 0 && (
        <div className="registry-coordinate-preview">
          {coordinates.slice(0, 10).map(coordinate => (
            <span key={coordinate} className="tag">{vectorLabel(String(coordinate).replace('assistant_axis_trait__', ''))}</span>
          ))}
          {coordinates.length > 10 && <span className="tag">+{coordinates.length - 10} more</span>}
        </div>
      )}
      {requirements.length > 0 && (
        <ul className="registry-requirements">
          {requirements.map(requirement => <li key={requirement}>{requirement}</li>)}
        </ul>
      )}
    </div>
  )
}

function Registry() {
  const [provider] = useProviderSelection()
  const { data: payload, error } = useAsyncResource(
    () => Promise.all([getScoreSpaces(provider), getEmotions()])
      .then(([scoreSpaces, emotions]) => ({ scoreSpaces, emotions })),
    [provider],
  )

  if (error) return (
    <div>
      <h1 className="page-title">Registry</h1>
      <p className="muted-copy">Could not load registry: {error}</p>
    </div>
  )

  if (!payload) return <h1 className="page-title">Loading...</h1>

  const { scoreSpaces, emotions } = payload
  const spaces = scoreSpaces.spaces || []
  const capturePlan = scoreSpaces.capture_plan || {}
  const providerInfo = scoreSpaces.provider || {}
  const coordinateCount = spaces.reduce((total, space) => total + Number(space.coordinate_count || 0), 0)
  const emotionConcepts = emotions.concepts || []
  const pilotConcepts = emotions.pilot_concepts || []

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Registry</h1>
          <p className="subtle-line">Scoring spaces, vector assets, model captures, and audit-ready probes.</p>
        </div>
      </div>

      <div className="stats-grid">
        <div className="card">
          <div className="card-title">Spaces</div>
          <div className="stat-value">{compactNumber(spaces.length)}</div>
          <div className="stat-label">registered scoring families</div>
        </div>
        <div className="card">
          <div className="card-title">Coordinates</div>
          <div className="stat-value">{compactNumber(coordinateCount)}</div>
          <div className="stat-label">vectors, traits, concepts, and probes</div>
        </div>
        <div className="card">
          <div className="card-title">Input Rows</div>
          <div className="stat-value">{compactNumber(providerInfo.assistant_turn_record_count)}</div>
          <div className="stat-label">{compactNumber(providerInfo.trace_count)} sessions in active provider</div>
        </div>
      </div>

      <div className="registry-space-list">
        {spaces.map(space => <RegistrySpaceCard key={space.id} space={space} />)}
      </div>

      <div className="chart-row two-col">
        <div className="card">
          <div className="card-title">Capture Plan</div>
          <table>
            <tbody>
              <tr><th>Model</th><td>{capturePlan.model_id}</td></tr>
              <tr><th>Residual site</th><td>{capturePlan.residual_site}</td></tr>
              <tr><th>Required layers</th><td>{(capturePlan.required_layers || []).join(', ')}</td></tr>
              <tr><th>Sections</th><td>{(capturePlan.sections || []).join(', ')}</td></tr>
            </tbody>
          </table>
          {capturePlan.note && <p className="muted-copy compact registry-note">{capturePlan.note}</p>}
        </div>

        <div className="card">
          <div className="card-title">Emotion Vector Asset</div>
          <div className="asset-title">{emotions.asset?.label}</div>
          <div className="asset-meta">
            <span>{emotions.asset?.model}</span>
            <span>Layer {emotions.asset?.layer}</span>
            <span>{compactNumber(emotionConcepts.length)} concepts</span>
          </div>
          <p className="muted-copy compact">{emotions.asset?.description}</p>
          {pilotConcepts.length > 0 && (
            <>
              <div className="registry-section-label">Pilot concepts</div>
              <div className="tag-row">
                {pilotConcepts.map(concept => <span key={concept} className="tag">{concept}</span>)}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">Emotion Concept Index</div>
        <div className="concept-grid">
          {emotionConcepts.map(concept => <span key={concept}>{concept}</span>)}
        </div>
      </div>
    </div>
  )
}

export { Registry, RegistrySpaceCard }
