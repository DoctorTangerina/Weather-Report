import { useMemo, useState } from 'react'
import Timeline from '../components/Timeline.jsx'
import Chart from '../components/Chart.jsx'
import useSeries from '../useSeries.js'
import RegionGlobe from '../components/Globe.jsx'

export default function MainScreen({ discovery, catalog, onInvestigate, onSurprise, loading, busy, error, discoveryNotice }) {
  const [timestamp, setTimestamp] = useState(null)
  const [regionId, setRegionId] = useState('')
  const [variableId, setVariableId] = useState('')
  const region = catalog?.regions.find((item) => item.region_id === regionId) ?? catalog?.regions[0]
  const variables = catalog?.variables.filter((item) => region?.variable_ids.includes(item.variable_id)) ?? []
  const variable = discovery
    ? catalog?.variables.find((item) => item.variable_id === discovery.contrasts[0].variable_id)
    : variables.find((item) => item.variable_id === variableId) ?? variables[0]
  const regions = useMemo(() => discovery?.region_ids.map((id) => catalog.regions.find((item) => item.region_id === id)) ?? [], [discovery, catalog])
  const refs = discovery
    ? discovery.contrasts[0].trends.map(({ region_id, variable_id }) => ({ region_id, variable_id }))
    : region && variable ? [{ region_id: region.region_id, variable_id: variable.variable_id }] : []
  const { loading: seriesLoading, series, notice, error: seriesError } = useSeries(refs)
  const ready = Boolean(catalog)

  return (
    <div className="main-screen">
      <header className="main-header">
        <h1 className="sr-only">Earth System Trend Detective</h1>
        <div className="top-actions" aria-label="Explore discoveries">
          <button onClick={onInvestigate} disabled={!onInvestigate || busy}>Become a Detective</button>
          <button className="secondary" onClick={onSurprise} disabled={!ready || busy || error?.code === 'no_discovery_left_in_session'}>
            {busy ? 'Looking for a Discovery…' : 'Surprise Me!'}
          </button>
        </div>
      </header>
      <section className="globe-panel" aria-label="Interactive Earth globe">
        <RegionGlobe regions={regions} />
        <p className="globe-hint">Drag to explore · Scroll or pinch to zoom</p>
      </section>
      <aside className="sidebar" tabIndex={0} aria-labelledby="explore-heading" aria-busy={loading || seriesLoading || busy}>
        <p className="eyebrow">{discovery ? 'Your Discovery' : 'Explore Earth'}</p>
        <h2 id="explore-heading">{discovery ? discovery.narrative.question : 'Explore a Region'}</h2>
        {discovery ? (
          <>
            <p className="label">{discovery.evidence_label}</p>
            <ol className="region-legend">
              {regions.map((item) => <li key={item.region_id}><strong>{item.name}</strong><p>{item.description}</p></li>)}
            </ol>
          </>
        ) : <p>Choose a Region and a Variable to view its time series. Try Surprise Me! to discover a contrast between two Regions.</p>}
        {loading && <p className="muted" role="status">Loading the catalog…</p>}
        {busy && <p className="muted" role="status">Looking for a Discovery…</p>}
        {ready && (
          <>
            {!discovery && <div className="catalog-controls">
              <label htmlFor="explore-region">Region</label>
              <select id="explore-region" value={region?.region_id ?? ''} onChange={(event) => setRegionId(event.target.value)}>
                {catalog.regions.map((item) => <option key={item.region_id} value={item.region_id}>{item.name}</option>)}
              </select>
              <label htmlFor="explore-variable">Variable</label>
              <select id="explore-variable" value={variable?.variable_id ?? ''} onChange={(event) => setVariableId(event.target.value)}>
                {variables.map((item) => <option key={item.variable_id} value={item.variable_id}>{item.name}</option>)}
              </select>
            </div>}
            {!discovery && region && <p className="muted">{region.description}</p>}
            {discovery && <h3>{variable?.name ?? discovery.contrasts[0].variable_id}</h3>}
            {variable && <p className="muted">{variable.definition}</p>}
            {seriesLoading && <p className="muted" role="status">Loading the series…</p>}
            {!seriesLoading && series.map((item) => (
              <Chart key={`${item.region_id}-${item.variable_id}`} series={item} timestamp={timestamp} label={catalog.regions.find((entry) => entry.region_id === item.region_id)?.name ?? item.region_id} />
            ))}
            {discovery && !seriesLoading && <p className="muted">Each chart has its own vertical scale. Compare the direction of the Trends.</p>}
          </>
        )}
        {(error || seriesError) && <p className="error" role="alert">{(error || seriesError).message}</p>}
        {notice && <p className="notice" role="status">{notice.message}</p>}
        {discoveryNotice && <p className="notice" role="status">{discoveryNotice.message}</p>}
        {!loading && !ready && <p className="muted">Check that the API is running, then reload to try again.</p>}
      </aside>
      <Timeline
        key={discovery?.discovery_id ?? `${region?.region_id}/${variable?.variable_id}`}
        series={seriesLoading ? [] : series}
        loading={loading || seriesLoading}
        onTimestampChange={setTimestamp}
      />
    </div>
  )
}
