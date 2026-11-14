import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getCatalog, surpriseMe } from './api.js'
import { REGION_COLORS } from './palette.js'
import InvestigationScreen from './screens/InvestigationScreen.jsx'
import MainScreen from './screens/MainScreen.jsx'

const NEW_SESSION = { shownDiscoveryIds: [], shownRegionIds: [] }

// loading → welcome → drawing → discovery ⇄ drawing … → complete → welcome
// unreachable when the catalog cannot be fetched; investigation is ticket #15.
export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [phase, setPhase] = useState('loading')
  const [discovery, setDiscovery] = useState(null)
  const [notice, setNotice] = useState(null)
  const [session, setSession] = useState(NEW_SESSION)
  const [error, setError] = useState(null)
  const drawing = useRef(false)

  const loadCatalog = useCallback(() => {
    setPhase('loading')
    getCatalog()
      .then((response) => {
        setCatalog(response.data)
        setNotice(response.notice)
        setPhase('welcome')
      })
      .catch(() => setPhase('unreachable'))
  }, [])

  useEffect(loadCatalog, [loadCatalog])

  const highlights = useMemo(() => {
    if (!discovery || !catalog) return []
    return discovery.region_ids
      .map((id, index) => ({
        region: catalog.regions.find((region) => region.region_id === id),
        color: REGION_COLORS[index],
      }))
      .filter((highlight) => highlight.region)
  }, [discovery, catalog])

  // Guards against a double click firing two draws before the first returns,
  // which would send the same session history twice.
  const draw = (nextPhase) => {
    if (drawing.current || !catalog) return
    drawing.current = true
    const settled = discovery ? 'discovery' : 'welcome'
    setPhase('drawing')
    setError(null)
    surpriseMe(session)
      .then((response) => {
        const next = response.data
        setDiscovery(next)
        setNotice(response.notice)
        setSession((current) => ({
          shownDiscoveryIds: [...new Set([...current.shownDiscoveryIds, next.discovery_id])],
          shownRegionIds: [...new Set([...current.shownRegionIds, ...next.region_ids])],
        }))
        setPhase(nextPhase)
      })
      .catch((failure) => {
        if (failure.code === 'no_discovery_left_in_session') {
          setPhase('complete')
          return
        }
        setError(failure)
        setPhase(settled)
      })
      .finally(() => {
        drawing.current = false
      })
  }

  const startOver = () => {
    setSession(NEW_SESSION)
    setDiscovery(null)
    setError(null)
    setPhase('welcome')
  }

  if (phase === 'investigation' && discovery) {
    return (
      <main className="detail-screen">
        <InvestigationScreen
          key={discovery.discovery_id}
          discovery={discovery}
          catalog={catalog}
          onBack={() => setPhase('discovery')}
        />
      </main>
    )
  }

  return (
    <main className="app-home">
      <MainScreen
        phase={phase}
        catalog={catalog}
        discovery={discovery}
        highlights={highlights}
        notice={notice}
        error={error}
        seen={session.shownDiscoveryIds.length}
        onSurprise={() => draw('discovery')}
        onDetective={() => draw('investigation')}
        onInvestigate={() => setPhase('investigation')}
        onNewSession={startOver}
        onRetry={loadCatalog}
      />
    </main>
  )
}
