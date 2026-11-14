import { useState } from 'react'
import Timeline from '../components/Timeline.jsx'
import Chart from '../components/Chart.jsx'
import useSeries from '../useSeries.js'
import RegionGlobe from '../components/Globe.jsx'

export default function MainScreen({ discovery, catalog, onInvestigate, onSurprise, loading, busy, error }) {
  const [timestamp, setTimestamp] = useState(null)
  const refs = discovery?.contrasts[0]?.trends.map(({ region_id, variable_id }) => ({
    region_id,
    variable_id,
  })) ?? []
  const { loading: seriesLoading, series, notice, error: seriesError } = useSeries(refs)
  const ready = Boolean(discovery && catalog)

  return (
    <div className="main-screen">
      <header className="main-header">
        <h1 className="sr-only">Earth System Trend Detective</h1>
        <div className="top-actions" aria-label="Explore discoveries">
          <button onClick={onInvestigate} disabled={!ready || busy}>Become a Detective</button>
          <button className="secondary" onClick={onSurprise} disabled={!ready || busy}>
            {busy ? 'Looking for a Discovery…' : 'Surprise Me!'}
          </button>
        </div>
      </header>
      <section className="globe-panel" aria-label="Interactive Earth globe">
        <RegionGlobe />
        <p className="globe-hint">Drag to explore · Scroll or pinch to zoom</p>
      </section>
      <aside className="sidebar" tabIndex={0} aria-labelledby="discovery-heading" aria-busy={loading || seriesLoading}>
        <p className="eyebrow">Featured Discovery</p>
        <h2 id="discovery-heading">{discovery?.narrative.question ?? 'Discover the story behind the data'}</h2>
        {discovery && <p className="label">{discovery.evidence_label}</p>}
        {loading && <p className="muted">Loading the Discovery…</p>}
        {ready && (
          <>
            <h3>Compare the Regions</h3>
            {seriesLoading && <p className="muted">Loading the series…</p>}
            {series.map((item) => (
              <Chart
                key={`${item.region_id}-${item.variable_id}`}
                series={item}
                timestamp={timestamp}
                label={catalog.regions.find((region) => region.region_id === item.region_id)?.name ?? item.region_id}
              />
            ))}
          </>
        )}
        {(error || seriesError) && <p className="error" role="alert">{(error || seriesError).message}</p>}
        {notice && <p className="notice">{notice.message}</p>}
        {!loading && !ready && <p className="muted">Check that the API is running, then reload to try again.</p>}
      </aside>
      <Timeline
        key={discovery?.discovery_id ?? 'loading'}
        series={series}
        loading={loading || seriesLoading}
        onTimestampChange={setTimestamp}
      />
    </div>
  )
}

