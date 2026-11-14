import { useMemo, useState } from 'react'
import DiscoveryPanel from '../components/DiscoveryPanel.jsx'
import Explorer from '../components/Explorer.jsx'
import RegionGlobe from '../components/Globe.jsx'
import { Drawing, SessionComplete, Unreachable, Welcome } from '../components/PanelStates.jsx'
import Timeline from '../components/Timeline.jsx'
import { REGION_COLORS } from '../palette.js'
import useSeries from '../useSeries.js'

const NONE = []

export default function MainScreen({
  phase,
  catalog,
  discovery,
  highlights,
  notice,
  error,
  seen,
  onSurprise,
  onDetective,
  onInvestigate,
  onNewSession,
  onRetry,
}) {
  const [timestamp, setTimestamp] = useState(null)
  const [regionId, setRegionId] = useState('')
  const [variableId, setVariableId] = useState('')

  const exploring = phase === 'welcome' && Boolean(catalog)
  const showing = phase === 'discovery' && Boolean(discovery)

  const region = catalog?.regions.find((item) => item.region_id === regionId) ?? catalog?.regions[0]
  const variables =
    catalog?.variables.filter((item) => region?.variable_ids.includes(item.variable_id)) ?? NONE
  const variable = variables.find((item) => item.variable_id === variableId) ?? variables[0]

  const refs = useMemo(() => {
    if (showing) {
      return discovery.contrasts[0].trends.map(({ region_id, variable_id }) => ({
        region_id,
        variable_id,
      }))
    }
    if (exploring && region && variable) {
      return [{ region_id: region.region_id, variable_id: variable.variable_id }]
    }
    return NONE
  }, [showing, exploring, discovery, region, variable])

  const explored = useMemo(
    () => (exploring && region ? [{ region, color: REGION_COLORS[0] }] : NONE),
    [exploring, region],
  )

  const { loading: seriesLoading, series, notice: seriesNotice, error: seriesError } =
    useSeries(refs)
  const banner = notice ?? seriesNotice
  const timelineKey = showing
    ? discovery.discovery_id
    : `${region?.region_id}/${variable?.variable_id}`

  return (
    <div className="main-screen">
      <header className="main-header">
        <h1 className="brand">
          <span className="brand-mark" aria-hidden="true" />
          Earth System Trend Detective
        </h1>
        {seen > 0 && (
          <p className="session-count" aria-live="polite">
            {seen === 1 ? '1 Discovery seen' : `${seen} Discoveries seen`}
          </p>
        )}
      </header>

      <section className="globe-panel" aria-label="Interactive Earth globe">
        <RegionGlobe highlights={showing ? highlights : explored} />
        <p className="globe-hint">Drag to explore · Scroll or pinch to zoom</p>
      </section>

      <aside
        className="sidebar"
        tabIndex={0}
        aria-busy={phase === 'loading' || phase === 'drawing' || seriesLoading}
      >
        {banner && (
          <p className="notice" role="status">
            {banner.message}
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error.message}
          </p>
        )}
        {seriesError && (
          <p className="error" role="alert">
            The monthly series could not be loaded: {seriesError.message}
          </p>
        )}

        {phase === 'loading' && <Drawing />}
        {phase === 'unreachable' && <Unreachable onRetry={onRetry} />}
        {exploring && (
          <>
            <Welcome catalog={catalog} onSurprise={onSurprise} onDetective={onDetective} />
            <Explorer
              catalog={catalog}
              region={region}
              variable={variable}
              variables={variables}
              onRegion={setRegionId}
              onVariable={setVariableId}
              series={series}
              seriesLoading={seriesLoading}
              timestamp={timestamp}
              color={REGION_COLORS[0]}
            />
          </>
        )}
        {phase === 'drawing' && <Drawing />}
        {phase === 'complete' && <SessionComplete seen={seen} onNewSession={onNewSession} />}
        {showing && (
          <DiscoveryPanel
            discovery={discovery}
            catalog={catalog}
            highlights={highlights}
            series={series}
            seriesLoading={seriesLoading}
            timestamp={timestamp}
            onInvestigate={onInvestigate}
            onSurprise={onSurprise}
          />
        )}
      </aside>

      {(showing || exploring) && (
        <Timeline
          key={timelineKey}
          series={seriesLoading ? NONE : series}
          loading={seriesLoading}
          onTimestampChange={setTimestamp}
        />
      )}
    </div>
  )
}
