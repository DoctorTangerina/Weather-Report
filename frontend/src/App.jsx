import { useEffect, useState } from 'react'
import { getCatalog, getDiscoveries, surpriseMe } from './api.js'
import DiscoveryScreen from './screens/DiscoveryScreen.jsx'
import ExperienceScreen from './screens/ExperienceScreen.jsx'
import InvestigationScreen from './screens/InvestigationScreen.jsx'

export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [view, setView] = useState('home')
  const [discovery, setDiscovery] = useState(null)
  const [session, setSession] = useState({ shownDiscoveryIds: [], shownRegionIds: [] })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    getCatalog()
      .then((response) => setCatalog(response.data))
      .catch(setError)
  }, [])

  const show = (next) => {
    setDiscovery(next)
    setSession((current) => ({
      shownDiscoveryIds: [...current.shownDiscoveryIds, next.discovery_id],
      shownRegionIds: [...current.shownRegionIds, ...next.region_ids],
    }))
  }

  const run = (load, nextView) => {
    setBusy(true)
    setError(null)
    load()
      .then((next) => {
        show(next)
        setView(nextView)
      })
      .catch(setError)
      .finally(() => setBusy(false))
  }

  const onSurprise = () => run(() => surpriseMe(session).then((r) => r.data), 'discovery')

  const onBrowse = () =>
    run(() => getDiscoveries().then((r) => r.data[0]), 'investigation')

  if (!catalog) {
    return (
      <main>
        {error ? <p className="error">{error.message}</p> : <p className="muted">Loading…</p>}
      </main>
    )
  }

  return (
    <main>
      {view === 'home' && (
        <ExperienceScreen
          catalog={catalog}
          onSurprise={onSurprise}
          onBrowse={onBrowse}
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
