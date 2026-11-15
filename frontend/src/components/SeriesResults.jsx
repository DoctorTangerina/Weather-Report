import Chart from './Chart.jsx'

const provenanceLabels = {
  preloaded: 'Preloaded data (dado pré-carregado)',
  cache: 'Cached data (dado em cache)',
  live: 'Live data',
}

export default function SeriesResults({ responses, catalog, timeRange, timestamp, highlights = [] }) {
  return responses.map(({ data, notice, provenance }, index) => {
    const region = catalog.regions.find((item) => item.region_id === data.region_id)
    const variable = catalog.variables.find((item) => item.variable_id === data.variable_id)
    return (
      <div key={`${data.region_id}-${data.variable_id}-${index}`}>
        {notice && <p role="alert" className="notice">{notice.message}</p>}
        {provenance && <p className="muted">{provenanceLabels[provenance]}</p>}
        <p className="muted">{data.period.start} to {data.period.end}</p>
        <Chart series={data} timestamp={timestamp} timeRange={timeRange} color={highlights.find((item) => item.region.region_id === data.region_id)?.color} label={`${region?.name ?? data.region_id} — ${variable?.name ?? data.variable_id}`} />
      </div>
    )
  })
}
