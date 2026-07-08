import { NavLink, useLocation, useNavigate } from 'react-router-dom'

const PRIMARY_NAV = [
  ['/', 'Overview', true],
  ['/hermes', 'Hermes Lab'],
  ['/character', 'Character'],
  ['/tail', 'Tail'],
]

const SUPPORT_NAV = [
  ['/report', 'Report'],
  ['/sessions', 'Sessions'],
  ['/registry', 'Registry'],
  ['/llms', 'LLMs'],
]

const PROVIDERS = ['tau2', 'hermes', 'persona_demo']

export function useProviderSelection() {
  const location = useLocation()
  const navigate = useNavigate()
  const params = new URLSearchParams(location.search)
  const urlProvider = params.get('provider')
  const storedProvider = typeof window !== 'undefined' ? window.localStorage.getItem('behaviorAuditProvider') : ''
  const provider = PROVIDERS.includes(urlProvider) ? urlProvider : (PROVIDERS.includes(storedProvider) ? storedProvider : 'tau2')
  const setProvider = nextProvider => {
    const next = PROVIDERS.includes(nextProvider) ? nextProvider : 'tau2'
    if (typeof window !== 'undefined') window.localStorage.setItem('behaviorAuditProvider', next)
    const nextParams = new URLSearchParams(location.search)
    if (next === 'tau2') nextParams.delete('provider')
    else nextParams.set('provider', next)
    const query = nextParams.toString()
    navigate(`${location.pathname}${query ? `?${query}` : ''}`, { replace: false })
  }
  return [provider, setProvider]
}

function ProviderSelector({ provider, onProvider }) {
  return (
    <div className="provider-selector" aria-label="Demo provider">
      {[
        ['tau2', 'Tau2 demo'],
        ['hermes', 'Hermes'],
        ['persona_demo', 'Persona demo'],
      ].map(([id, label]) => (
        <button key={id} type="button" className={provider === id ? 'active' : ''} onClick={() => onProvider(id)}>
          {label}
        </button>
      ))}
    </div>
  )
}

export function providerPath(path, provider) {
  if (path === '/hermes') return '/hermes?provider=hermes'
  if (!provider || provider === 'tau2') return path
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
