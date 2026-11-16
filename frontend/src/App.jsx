import { useCallback, useEffect, useState } from 'react'
import { getCatalog } from './api.js'
import MainScreen from './screens/MainScreen.jsx'

const NEW_SESSION = { shownDiscoveryIds: [], shownRegionIds: [] }

// loading → ready, or unreachable when the catalog cannot be fetched. Each tab
// owns its own flow (#114); the app keeps the catalog and the one session that
// Surprise Me! and Become a Detective share.
export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [phase, setPhase] = useState('loading')
  const [notice, setNotice] = useState(null)
  const [session, setSession] = useState(NEW_SESSION)

  const loadCatalog = useCallback(() => {
    setPhase('loading')
    getCatalog()
      .then((response) => {
        setCatalog(response.data)
        setNotice(response.notice)
        setPhase('ready')
      })
      .catch(() => setPhase('unreachable'))
  }, [])
  useEffect(loadCatalog, [loadCatalog])

  const recordDiscovery = useCallback((discovery) => {
    setSession((current) => ({
      shownDiscoveryIds: [...new Set([...current.shownDiscoveryIds, discovery.discovery_id])],
      shownRegionIds: [...new Set([...current.shownRegionIds, ...discovery.region_ids])],
    }))
  }, [])
  const resetSession = useCallback(() => setSession(NEW_SESSION), [])

  return (
    <main className="app-home">
      <MainScreen
        phase={phase}
        catalog={catalog}
        notice={notice}
        session={session}
        recordDiscovery={recordDiscovery}
        resetSession={resetSession}
        onRetry={loadCatalog}
      />
    </main>
  )
}
