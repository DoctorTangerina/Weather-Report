import Chart from './Chart.jsx'

const provenanceLabels = {
  preloaded: 'Preloaded data (dado pré-carregado)',
  cache: 'Cached data (dado em cache)',
  live: 'Live data',
}

export default function SeriesResults({ responses, catalog }) {
  return responses.map(({ data, notice, provenance }, index) => {
    const region = catalog.regions.find((item) => item.region_id === data.region_id)
    const variable = catalog.variables.find((item) => item.variable_id === data.variable_id)
    return (
      <div key={`${data.region_id}-${data.variable_id}-${index}`}>
        {notice && <p role="alert" className="notice">{notice.message}</p>}
        {provenance && <p className="muted">{provenanceLabels[provenance]}</p>}
        <Chart series={data} label={`${region?.name ?? data.region_id} — ${variable?.name ?? data.variable_id}`} />
      </div>
    )
  })
}
