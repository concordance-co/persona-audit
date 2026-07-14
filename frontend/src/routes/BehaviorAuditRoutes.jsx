// Route table for the behavior-audit dashboard. Pages live under
// ./behavior/pages/, shared components under ./behavior/. This file was a
// 4,900-line monolith; it was split verbatim (pure reorganization).
import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom'
import { Character } from './behavior/pages/Character.jsx'
import { HermesLab } from './behavior/pages/HermesLab.jsx'
import { LLMs } from './behavior/pages/LLMs.jsx'
import { Overview } from './behavior/pages/Overview.jsx'
import { Registry } from './behavior/pages/Registry.jsx'
import { Report } from './behavior/pages/Report.jsx'
import { SessionDetail } from './behavior/pages/SessionDetail.jsx'
import { Sessions } from './behavior/pages/Sessions.jsx'
import { Shell, providerPath, useProviderSelection } from './behavior/layout'
import { Tail } from './behavior/pages/Tail.jsx'

function ProviderRedirect({ to }) {
  const [provider] = useProviderSelection()
  return <Navigate to={providerPath(to, provider)} replace />
}

export default function App() {
  return (
    <Router>
      <Shell>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/character" element={<Character />} />
          <Route path="/tail" element={<Tail />} />
          <Route path="/report" element={<Report />} />
          <Route path="/product-analytics" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/sessions/:traceId" element={<SessionDetail />} />
          <Route path="/cohorts" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/cohorts/:cohortId" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/users" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/users/:userId" element={<ProviderRedirect to="/sessions" />} />
          <Route path="/high-stakes" element={<ProviderRedirect to="/registry" />} />
          <Route path="/emotions" element={<ProviderRedirect to="/registry" />} />
          <Route path="/registry" element={<Registry />} />
          <Route path="/llms" element={<LLMs />} />
          <Route path="/hermes" element={<HermesLab />} />
        </Routes>
      </Shell>
    </Router>
  )
}
