import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, getCatalog, getDiscoveries, surpriseMe } from './api.js'
import { REGION_COLORS } from './palette.js'
import MainScreen from './screens/MainScreen.jsx'

const NEW_SESSION = { shownDiscoveryIds: [], shownRegionIds: [] }

// loading → welcome → drawing → discovery ⇄ drawing … → complete → welcome
// unreachable when the catalog cannot be fetched. The investigation (#15) runs
// in the sidebar, beside the globe, from a drawn Discovery. welcome ⇄ explore
// opens one catalog Region in Explore My World (#75).
export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [phase, setPhase] = useState('loading')
  const [discovery, setDiscovery] = useState(null)
  const [notice, setNotice] = useState(null)
  const [session, setSession] = useState(NEW_SESSION)
  const [error, setError] = useState(null)
  const [exploreRegionId, setExploreRegionId] = useState(null)
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
  const draw = (nextPhase, selectedRegions = []) => {
    if (drawing.current || !catalog) return
    if (selectedRegions.length === 1) {
      setError(new ApiError('incomplete_pair', 'Choose a second Region to investigate this pair.'))
      return
    }
    drawing.current = true
    const settled = discovery ? 'discovery' : 'welcome'
    setPhase('drawing')
    setError(null)
    const request = selectedRegions.length === 2
      ? getDiscoveries().then((response) => {
          const selected = response.data.find((item) =>
            item.region_ids.length === 2 && selectedRegions.every((id) => item.region_ids.includes(id)),
          )
          if (!selected) {
            throw new ApiError('result_not_available', 'There is no Discovery to investigate for these Regions yet. Choose another pair or use Surprise Me!')
          }
          return { ...response, data: selected }
        })
      : surpriseMe(session)
    request
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
        onDetective={(selectedRegions) => draw('investigation', selectedRegions)}
        onInvestigate={() => setPhase('investigation')}
        onBack={() => setPhase('discovery')}
        onNewSession={startOver}
        exploreRegionId={exploreRegionId}
        onExplore={(regionId) => {
          setExploreRegionId(regionId)
          setError(null)
          setPhase('explore')
        }}
        onCloseExplore={() => setPhase('welcome')}
        onRetry={loadCatalog}
      />
    </main>
  )
}
