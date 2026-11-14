import RegionMap from '../components/RegionMap.jsx'
import SeriesResults from '../components/SeriesResults.jsx'
import useSeries from '../useSeries.js'

export default function DiscoveryScreen({ discovery, catalog, onInvestigate, onBack }) {
  const headline = discovery.contrasts[0]
  const refs = headline.trends.map((trend) => ({
    region_id: trend.region_id,
    variable_id: trend.variable_id,
  }))
  const { loading, responses, substituted, error } = useSeries(refs, discovery.period)
  const regionIds = substituted
    ? [...new Set(responses.map(({ data }) => data.region_id))]
    : discovery.region_ids
  const regions = regionIds.map((id) => catalog.regions.find((region) => region.region_id === id))

  return (
    <section>
      <button className="link" onClick={onBack}>← Back</button>
      <h1>{substituted ? 'Preloaded examples' : discovery.narrative.question}</h1>
      {!substituted && <p className="label">{discovery.evidence_label}</p>}
      <RegionMap regions={regions} />
      {substituted && <p role="alert" className="notice">These examples cannot answer the original investigation.</p>}
      {error && <p className="error">{error.message}</p>}
      {loading && <p className="muted">Loading the series…</p>}
      <SeriesResults responses={responses} catalog={catalog} />
      <button disabled={loading || Boolean(error) || substituted} onClick={onInvestigate}>Become a Detective</button>
    </section>
  )
}
