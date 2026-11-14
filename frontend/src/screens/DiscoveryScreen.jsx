import Chart from '../components/Chart.jsx'
import RegionMap from '../components/RegionMap.jsx'
import useSeries from '../useSeries.js'

export default function DiscoveryScreen({ discovery, catalog, onInvestigate, onBack }) {
  const headline = discovery.contrasts[0]
  const refs = headline.trends.map((trend) => ({
    region_id: trend.region_id,
    variable_id: trend.variable_id,
  }))
  const { loading, series, notice, error } = useSeries(refs)
  const regions = discovery.region_ids.map((id) =>
    catalog.regions.find((region) => region.region_id === id),
  )

  return (
    <section>
      <button className="link" onClick={onBack}>
        ← Back
      </button>

      <h1>{discovery.narrative.question}</h1>
      <p className="label">{discovery.evidence_label}</p>

      <RegionMap regions={regions} />

      {notice && <p className="notice">{notice.message}</p>}
      {error && <p className="error">{error.message}</p>}
      {loading && <p className="muted">Loading the series…</p>}

      {series.map((item, index) => (
        <Chart
          key={`${item.region_id}-${item.variable_id}`}
          series={item}
          label={regions[index]?.name ?? item.region_id}
        />
      ))}

      <button onClick={onInvestigate}>Become a Detective</button>
    </section>
  )
}
