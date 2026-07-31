import { NavLink, useLocation, useNavigate } from 'react-router'
import { createContext, useContext } from 'react'
import { getProviders } from '../../api'
import { useAsyncResource } from '../../hooks/useAsyncResource'

const PRIMARY_NAV = [
  ['/', 'Overview', true],
  ['/character', 'Character'],
  ['/tail', 'Tail'],
  ['/sessions', 'Sessions'],
]

const SUPPORT_NAV = [
  ['/report', 'Report'],
  ['/registry', 'Registry'],
  ['/llms', 'LLMs'],
]

const ProviderSelectionContext = createContext(null)

export function useProviderSelection() {
  const value = useContext(ProviderSelectionContext)
  if (!value) throw new Error('useProviderSelection must be used inside Shell')
  return value
}

function ProviderSelector({ provider, providers, onProvider }) {
  const fallback = { key: provider, label: provider === 'persona_demo' ? 'Persona demo' : provider }
  const options = providers.length
    ? (providers.some(option => option.key === provider) ? providers : [...providers, fallback])
    : [fallback]
  return (
    <div className="provider-selector" aria-label="Dataset">
      <label>
        <span className="dataset-selector-label">Dataset</span>
        <select value={provider} onChange={event => onProvider(event.target.value)}>
          {options.map(option => (
            <option key={option.key} value={option.key}>{option.label || option.key}</option>
          ))}
        </select>
      </label>
    </div>
  )
}

// Mirrors the backend descriptor's features.show_reward for pages whose
// payloads are bare lists (no embedded provider block).
const REWARD_PROVIDERS = new Set(['tau2'])

export function providerShowsReward(provider, descriptor) {
  if (descriptor?.features) return descriptor.features.show_reward !== false
  return REWARD_PROVIDERS.has(provider)
}

export function providerPath(path, provider) {
  if (!provider) return path
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}provider=${provider}`
}

export function Shell({ children }) {
  const location = useLocation()
  const navigate = useNavigate()
  const { data: providers } = useAsyncResource(getProviders, [])
  const availableProviders = providers || []
  const visibleProviders = availableProviders.filter(
    item => item.features?.show_in_provider_selector !== false,
  )
  const params = new URLSearchParams(location.search)
  const urlProvider = params.get('provider')
  const storedProvider = typeof window !== 'undefined' ? window.localStorage.getItem('behaviorAuditProvider') : ''
  const defaultProvider = visibleProviders.find(item => item.is_default)?.key || visibleProviders[0]?.key || 'persona_demo'
  const isVisible = key => !visibleProviders.length || visibleProviders.some(item => item.key === key)
  const provider = (isVisible(urlProvider) ? urlProvider : '') || (isVisible(storedProvider) ? storedProvider : '') || defaultProvider
  const descriptor = availableProviders.find(item => item.key === provider) || null
  const setProvider = nextProvider => {
    if (typeof window !== 'undefined') window.localStorage.setItem('behaviorAuditProvider', nextProvider)
    const nextParams = new URLSearchParams(location.search)
    nextParams.set('provider', nextProvider)
    navigate(`${location.pathname}?${nextParams.toString()}`, { replace: false })
  }
  return (
    <ProviderSelectionContext.Provider value={[provider, setProvider, descriptor]}>
      <div className="app-layout">
        <nav className="sidebar">
          <div className="sidebar-brand">
            <img className="brand-mark" src="/concordance_icon_black.svg" alt="" aria-hidden="true" />
            <span>Persona Audit</span>
          </div>
          <ProviderSelector provider={provider} providers={visibleProviders} onProvider={setProvider} />
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
    </ProviderSelectionContext.Provider>
  )
}
