import { useEffect, useRef, useState } from 'react'
import { getCatalog, surpriseMe } from './api.js'
import MainScreen from './screens/MainScreen.jsx'

export default function App() {
  const [catalog, setCatalog] = useState(null)
  const [view, setView] = useState('home')
  const [discovery, setDiscovery] = useState(null)
  const [session, setSession] = useState({ shownDiscoveryIds: [], shownRegionIds: [] })
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const requestPending = useRef(false)

  const remember = (next) => setSession((current) => ({
    shownDiscoveryIds: [...new Set([...current.shownDiscoveryIds, next.discovery_id])],
    shownRegionIds: [...new Set([...current.shownRegionIds, ...next.region_ids])],
  }))

  useEffect(() => {
    let cancelled = false
    getCatalog()
      .then((catalogResponse) => {
        if (cancelled) return
        setCatalog(catalogResponse.data)
        setNotice(catalogResponse.notice ?? null)
      })
      .catch((error) => { if (!cancelled) setError(error) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  const onSurprise = () => {
    if (requestPending.current || loading || !catalog) return
    requestPending.current = true
    setBusy(true)
    setError(null)
    surpriseMe(session)
      .then(({ data: next, notice: nextNotice }) => {
        setDiscovery(next)
        setView('home')
        remember(next)
        setNotice(nextNotice ?? null)
      })
      .catch(setError)
      .finally(() => {
        requestPending.current = false
        setBusy(false)
      })
  }

  return (
    <main className="app-home">
        <MainScreen
          discovery={discovery}
          catalog={catalog}
          onInvestigate={discovery ? () => setView('investigation') : undefined}
          investigating={view === 'investigation'}
          onBack={() => setView('home')}
          onSurprise={onSurprise}
          loading={loading}
          busy={busy}
          error={error}
          discoveryNotice={notice}
        />
    </main>
  )
}
