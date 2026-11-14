import { useEffect, useState } from 'react'
import { getCatalog, getDiscoveries, surpriseMe } from './api.js'
import DiscoveryScreen from './screens/DiscoveryScreen.jsx'
import InvestigationScreen from './screens/InvestigationScreen.jsx'
import MainScreen from './screens/MainScreen.jsx'

export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [view, setView] = useState('home')
  const [discovery, setDiscovery] = useState(null)
  const [session, setSession] = useState({ shownDiscoveryIds: [], shownRegionIds: [] })
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getCatalog(), getDiscoveries()])
      .then(([catalogResponse, discoveriesResponse]) => {
        if (cancelled) return
        const initialDiscovery = discoveriesResponse.data[0]
        if (!initialDiscovery) throw new Error('No discoveries are available.')
        setDiscovery(initialDiscovery)
        setCatalog(catalogResponse.data)
        setSession({
          shownDiscoveryIds: [initialDiscovery.discovery_id],
          shownRegionIds: [...initialDiscovery.region_ids],
        })
      })
      .catch((error) => { if (!cancelled) setError(error) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const onSurprise = () => {
    setBusy(true)
    setError(null)
    surpriseMe(session)
      .then(({ data: next }) => {
        setDiscovery(next)
        setSession((current) => ({
          shownDiscoveryIds: [...current.shownDiscoveryIds, next.discovery_id],
          shownRegionIds: [...current.shownRegionIds, ...next.region_ids],
        }))
        setView('discovery')
      })
      .catch(setError)
      .finally(() => setBusy(false))
  }

  return (
    <main className={view === 'home' ? 'app-home' : 'detail-screen'}>
      {view === 'home' && (
        <MainScreen
          discovery={discovery}
          catalog={catalog}
          onInvestigate={() => setView('investigation')}
          onSurprise={onSurprise}
          loading={loading}
          busy={busy}
          error={error}
        />
      )}
      {view === 'discovery' && discovery && (
        <DiscoveryScreen
          discovery={discovery}
          catalog={catalog}
          onInvestigate={() => setView('investigation')}
          onBack={() => setView('home')}
        />
      )}
      {view === 'investigation' && discovery && (
        <InvestigationScreen
          discovery={discovery}
          catalog={catalog}
          onBack={() => setView('home')}
        />
      )}
    </main>
  )
}
