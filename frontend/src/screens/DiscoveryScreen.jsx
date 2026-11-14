import { useEffect, useRef } from 'react'
import Chart from '../components/Chart.jsx'
import RegionMap from '../components/RegionMap.jsx'
import useSeries from '../useSeries.js'

export default function DiscoveryScreen({ discovery, catalog, onInvestigate, onBack, onSurprise, busy, error: selectionError, discoveryNotice }) {
  const headingRef = useRef(null)
  useEffect(() => { headingRef.current?.focus() }, [])
  const headline = discovery.contrasts[0]
  const variable = catalog.variables.find((item) => item.variable_id === headline.variable_id)
  const refs = headline.trends.map(({ region_id, variable_id }) => ({ region_id, variable_id }))
  const { loading, series, notice, error } = useSeries(refs)
  const regions = discovery.region_ids.map((id) => catalog.regions.find((region) => region.region_id === id))

  return (
    <section aria-busy={busy || loading}>
      <button className="link" onClick={onBack} disabled={busy}>← Back to main screen</button>
      <p className="eyebrow">Your Discovery</p>
      <h1 ref={headingRef} tabIndex={-1}>{discovery.narrative.question}</h1>
      <p className="label">{discovery.evidence_label}</p>
      <RegionMap regions={regions} />
      {discoveryNotice && <p className="notice" role="status">{discoveryNotice.message}</p>}
      {notice && <p className="notice" role="status">{notice.message}</p>}
      {(error || selectionError) && <p className="error" role="alert">{(selectionError || error).message}</p>}
      <h2>{variable?.name ?? headline.variable_id}</h2>
      {variable && <p className="muted">{variable.definition}</p>}
      <div role="status">{loading && <p className="muted">Loading the series…</p>}</div>
      {series.map((item) => (
        <Chart
          key={`${item.region_id}-${item.variable_id}`}
          series={item}
          label={catalog.regions.find((region) => region.region_id === item.region_id)?.name ?? item.region_id}
        />
      ))}
      <p className="muted">Each chart has its own vertical scale. Compare the direction of the Trends.</p>
      <div className="actions">
        <button onClick={onInvestigate} disabled={busy}>Become a Detective</button>
        <button className="secondary" onClick={onSurprise} disabled={busy || selectionError?.code === 'no_discovery_left_in_session'}>
          {busy ? 'Looking for a Discovery…' : 'Surprise Me!'}
        </button>
      </div>
      <div role="status">{busy && <p className="muted">Looking for a Discovery…</p>}</div>
    </section>
  )
}
