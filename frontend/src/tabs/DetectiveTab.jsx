import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, getDiscoveries, surpriseMe } from '../api.js'
import { REGION_COLORS } from '../palette.js'
import InvestigationScreen from '../screens/InvestigationScreen.jsx'
import { useShell, useTabDeclaration, useTabTimeline } from './shell.js'
import useDiscoveryView from './useDiscoveryView.js'

const NONE = []

// Choose two Regions (or none, and the engine picks), then investigate their
// Discovery: Predict, Check, Reason. The pair is this tab's own.
export default function DetectiveTab() {
  const { catalog, session, recordDiscovery } = useShell()
  const { timestamp, timeRange } = useTabTimeline()
  const [regionId, setRegionId] = useState('')
  const [secondRegionId, setSecondRegionId] = useState('')
  const [discovery, setDiscovery] = useState(null)
  const [investigating, setInvestigating] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState(null)
  const [step, setStep] = useState(0)
  const busy = useRef(false)

  const region = catalog.regions.find((item) => item.region_id === regionId)
  const secondRegion = catalog.regions.find((item) => item.region_id === secondRegionId)
  const { series, highlights } = useDiscoveryView(
    catalog,
    discovery,
    investigating ? 'investigation' : null,
  )

  useEffect(() => {
    if (investigating) setStep(0)
  }, [investigating, discovery?.discovery_id])

  const investigate = () => {
    if (busy.current) return
    const pair = [regionId, secondRegionId].filter(Boolean)
    if (pair.length === 1) {
      setError(new ApiError('incomplete_pair', 'Choose a second Region to investigate this pair.'))
      return
    }
    busy.current = true
    setChecking(true)
    setError(null)
    const request = pair.length === 2
      ? getDiscoveries().then((response) => {
          const found = response.data.find((item) =>
            item.region_ids.length === 2 && pair.every((id) => item.region_ids.includes(id)),
          )
          if (!found) {
            throw new ApiError('result_not_available', 'There is no Discovery to investigate for these Regions yet. Choose another pair or use Surprise Me!')
          }
          return { ...response, data: found }
        })
      : surpriseMe(session)
    request
      .then((response) => {
        setDiscovery(response.data)
        recordDiscovery(response.data)
        setInvestigating(true)
      })
      .catch((failure) => setError(
        failure.code === 'no_discovery_left_in_session'
          ? new ApiError(failure.code, 'You have seen every Discovery for now. Choose two Regions, or start a new session in Surprise Me!')
          : failure,
      ))
      .finally(() => {
        busy.current = false
        setChecking(false)
      })
  }

  // A Region clicked on the globe fills the next empty slot.
  const choose = (id) => {
    if (!regionId) setRegionId(id)
    else if (id !== regionId) setSecondRegionId(id)
  }
  const chosen = useMemo(
    () => [region, secondRegion]
      .filter(Boolean)
      .map((item, index) => ({ region: item, color: REGION_COLORS[index] })),
    [region, secondRegion],
  )
  useTabDeclaration({
    globe: investigating
      ? { highlights }
      : { highlights: chosen, onRegionClick: choose, hint: 'Click a Region to choose it' },
    timeline: investigating
      ? {
          kind: 'series',
          key: `investigation/${discovery?.discovery_id}`,
          series: series.loading || step !== 1 ? NONE : series.series,
          loading: series.loading,
        }
      : null,
  })

  if (investigating && discovery) {
    return (
      <InvestigationScreen
        key={discovery.discovery_id}
        discovery={discovery}
        catalog={catalog}
        highlights={highlights}
        onBack={() => setInvestigating(false)}
        stepIndex={step}
        onStepChange={setStep}
        loading={series.loading}
        responses={series.responses}
        substituted={series.substituted}
        error={series.error}
        timestamp={timestamp}
        timeRange={timeRange}
      />
    )
  }

  return (
    <article className="welcome" aria-labelledby="detective-heading">
      <p className="eyebrow">Become a Detective</p>
      <h2 id="detective-heading">Make a guess first, then check it against the evidence.</h2>
      <p className="welcome-lede">
        Choose two Regions, or click them on the globe. Choose none and the engine picks a
        pair for you.
      </p>
      <div className="catalog-controls">
        <label htmlFor="detective-region">First Region</label>
        <select id="detective-region" value={regionId} disabled={checking}
          onChange={(event) => setRegionId(event.target.value)}>
          <option value="">Choose a Region</option>
          {catalog.regions.filter((item) => item.region_id !== secondRegionId).map((item) => (
            <option key={item.region_id} value={item.region_id}>{item.name}</option>
          ))}
        </select>
        <label htmlFor="detective-second-region">Second Region</label>
        <select id="detective-second-region" value={secondRegionId} disabled={checking}
          onChange={(event) => setSecondRegionId(event.target.value)}>
          <option value="">Choose a Region</option>
          {catalog.regions.filter((item) => item.region_id !== regionId).map((item) => (
            <option key={item.region_id} value={item.region_id}>{item.name}</option>
          ))}
        </select>
      </div>
      <div className="experiences">
        <button className="experience" onClick={investigate} disabled={checking} aria-busy={checking}
          aria-describedby={error ? 'detective-error' : undefined}>
          <span className="experience-title">Become a Detective</span>
          <span className="experience-text">
            {regionId || secondRegionId ? 'Investigate this pair.' : 'Let the engine pick a pair.'}
          </span>
        </button>
        {error && <p id="detective-error" className="error" role="alert">{error.message}</p>}
      </div>
    </article>
  )
}
