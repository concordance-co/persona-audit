import { NavLink, useLocation, useNavigate } from 'react-router-dom'

// Hermes Lab sits last: it is the one deliberately separate surface; the
// pages above it are shared by every data source.
const PRIMARY_NAV = [
  ['/', 'Overview', true],
  ['/character', 'Character'],
  ['/tail', 'Tail'],
  ['/sessions', 'Sessions'],
  ['/hermes', 'Hermes Lab'],
]

const SUPPORT_NAV = [
  ['/report', 'Report'],
  ['/registry', 'Registry'],
  ['/llms', 'LLMs'],
]

const PROVIDERS = ['persona_demo', 'tau2', 'hermes']
const DEFAULT_PROVIDER = 'persona_demo'

// Each dataset is a lens on the same pages: what changes is the data and
// which view modes light up, never which pages exist.
const PROVIDER_LENSES = [
  ['persona_demo', 'Persona demo', 'Contrastive personas in activation space'],
  ['tau2', 'Tau2 demo', 'Product analytics over an agent benchmark'],
  ['hermes', 'Hermes', 'Bring your own agent sessions'],
]

export function useProviderSelection() {
  const location = useLocation()
  const navigate = useNavigate()
  const params = new URLSearchParams(location.search)
  const urlProvider = params.get('provider')
  const storedProvider = typeof window !== 'undefined' ? window.localStorage.getItem('behaviorAuditProvider') : ''
  const provider = PROVIDERS.includes(urlProvider) ? urlProvider : (PROVIDERS.includes(storedProvider) ? storedProvider : DEFAULT_PROVIDER)
  const setProvider = nextProvider => {
    const next = PROVIDERS.includes(nextProvider) ? nextProvider : DEFAULT_PROVIDER
    if (typeof window !== 'undefined') window.localStorage.setItem('behaviorAuditProvider', next)
    const nextParams = new URLSearchParams(location.search)
    nextParams.set('provider', next)
    navigate(`${location.pathname}?${nextParams.toString()}`, { replace: false })
  }
  return [provider, setProvider]
}

function ProviderSelector({ provider, onProvider }) {
  return (
    <div className="provider-selector" aria-label="Demo provider">
      {PROVIDER_LENSES.map(([id, label, lens]) => (
        <button key={id} type="button" className={provider === id ? 'active' : ''} title={lens} onClick={() => onProvider(id)}>
          {label}
        </button>
      ))}
    </div>
  )
}

export function providerPath(path, provider) {
  if (path === '/hermes') return '/hermes?provider=hermes'
  if (!provider) return path
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}provider=${provider}`
}

export function Shell({ children }) {
  const [provider, setProvider] = useProviderSelection()
  return (
    <div className="app-layout">
      <nav className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark" />
          <span>Persona Audit</span>
        </div>
        <ProviderSelector provider={provider} onProvider={setProvider} />
        <div className="nav-links">
          <div className="nav-group nav-group-primary" aria-label="Behavior audit">
            {PRIMARY_NAV.map(([path, label, end]) => (
              <NavLink key={path} to={providerPath(path, provider)} end={Boolean(end)}>{label}</NavLink>
            ))}
          </div>
          <div className="nav-group nav-group-support" aria-label="Evidence and registry">
            {SUPPORT_NAV.map(([path, label]) => (
              <NavLink key={path} to={providerPath(path, provider)}>{label}</NavLink>
            ))}
          </div>
        </div>
      </nav>
      <main className="main-content">{children}</main>
    </div>
  )
}
