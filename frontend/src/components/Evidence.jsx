import { formatRate } from '../format.js'

export default function Evidence({ discovery, catalog }) {
  const evidence = discovery.narrative.how_do_we_know
  const regionName = (id) => catalog.regions.find((region) => region.region_id === id)?.name ?? id
  const variableName = (id) => catalog.variables.find((variable) => variable.variable_id === id)?.name ?? id

  return (
    <details className="evidence">
      <summary>How do we know?</summary>
      <p className="label">{discovery.evidence_label}</p>
      <p>Period analyzed: {evidence.period.start} to {evidence.period.end}.</p>
      <p>A rate per decade describes the change over ten years. The 95% interval shows the uncertainty around that estimate.</p>
      <ul>
        {discovery.contrasts.flatMap((contrast) => contrast.trends.map((trend) => {
          // Rounded exactly as the narrative rounds them (discovery.schema.json).
          const { rate, interval, units } = formatRate(trend)
          return (
            <li key={`${trend.region_id}-${trend.variable_id}`}>
              <strong>{regionName(trend.region_id)} — {variableName(trend.variable_id)}</strong>: {rate}{' '}
              {units} (95% interval {interval}). {trend.evidence_label}.
            </li>
          )
        }))}
      </ul>
      <ul>
        {evidence.sources.map((entry) => {
          const variable = catalog.variables.find((item) => item.variable_id === entry.variable_id)
          const synthetic = entry.source.provider === 'Synthetic (stub)'
          return (
            <li key={`${entry.region_id}-${entry.variable_id}`}>
              <strong>{regionName(entry.region_id)} — {variableName(entry.variable_id)}</strong>: {' '}
              Source: {entry.source.provider} — {entry.source.dataset} ({entry.source.variable}).
              {entry.source.url && <> <a href={entry.source.url} target="_blank" rel="noopener noreferrer">View source</a>.</>}
              {synthetic && <p className="notice">These are synthetic demonstration data, not NASA observations.
                {variable?.source && <> Intended NASA source: {variable.source.provider}. The NASA dataset is not connected in this demonstration.</>}
              </p>}
            </li>
          )
        })}
      </ul>
      <p>{evidence.statistics_summary}</p>
      <p className="muted">Method paper: {evidence.method_citation}</p>
    </details>
  )
}
