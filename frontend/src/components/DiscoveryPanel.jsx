import { formatRate } from '../format.js'
import Chart from './Chart.jsx'

const LABEL_TONE = {
  'Strong evidence': 'strong',
  'Some evidence': 'some',
  'Not enough evidence yet': 'none',
}

const ARROW = { rising: '↑', falling: '↓', flat: '→' }

export function EvidenceLabel({ label }) {
  return <span className={`evidence-label evidence-${LABEL_TONE[label] ?? 'none'}`}>{label}</span>
}

function RegionRate({ trend, highlight }) {
  const { rate, interval, units } = formatRate(trend)
  return (
    <li className="region-rate" style={{ '--region': highlight.color }}>
      <h3 className="region-name">
        <span className="region-swatch" aria-hidden="true" />
        {highlight.region.name}
      </h3>
      <p className="region-description">{highlight.region.description}</p>
      <p className="rate">
        <span className="rate-arrow" aria-hidden="true">
          {ARROW[trend.direction]}
        </span>
        <span className="sr-only">{trend.direction}, </span>
        <strong className="rate-value">{rate}</strong> <span className="rate-units">{units}</span>
      </p>
      <p className="rate-detail">
        95% interval {interval} · {trend.evidence_label}
      </p>
    </li>
  )
}

export default function DiscoveryPanel({
  discovery,
  catalog,
  highlights,
  series,
  seriesLoading,
  timestamp,
  onInvestigate,
  onSurprise,
}) {
  const [lead, ...others] = discovery.contrasts
  const leadVariable = catalog.variables.find((v) => v.variable_id === lead.variable_id)
  const variableName = (id) => catalog.variables.find((v) => v.variable_id === id)?.name ?? id
  const colorOf = (regionId) => highlights.find((h) => h.region.region_id === regionId)?.color

  return (
    <article className="discovery" aria-labelledby="discovery-question">
      <p className="eyebrow">Discovery · {variableName(lead.variable_id)}</p>
      <h2 id="discovery-question">{discovery.narrative.question}</h2>
      <EvidenceLabel label={discovery.evidence_label} />

      <ul className="region-rates" aria-label="How fast each Region is changing">
        {lead.trends.map((trend) => (
          <RegionRate
            key={trend.region_id}
            trend={trend}
            highlight={highlights.find((h) => h.region.region_id === trend.region_id)}
          />
        ))}
      </ul>

      {others.length > 0 && (
        <p className="also-differs">
          These Regions also differ in{' '}
          {others.map((contrast) => variableName(contrast.variable_id).toLowerCase()).join(' and ')}.
        </p>
      )}

      <section className="discovery-charts" aria-label="Monthly series">
        {leadVariable && <p className="variable-definition">{leadVariable.definition}</p>}
        {seriesLoading && <div className="skeleton skeleton-chart" aria-hidden="true" />}
        {series.map((item) => (
          <Chart
            key={`${item.region_id}-${item.variable_id}`}
            series={item}
            timestamp={timestamp}
            color={colorOf(item.region_id)}
            label={catalog.regions.find((r) => r.region_id === item.region_id)?.name ?? item.region_id}
          />
        ))}
        {!seriesLoading && series.length > 1 && (
          <p className="chart-note">
            Each chart has its own vertical scale. Compare the direction of the Trends.
          </p>
        )}
      </section>

      <div className="panel-actions">
        <button className="primary" onClick={onInvestigate}>
          Become a Detective
        </button>
        <button className="ghost" onClick={onSurprise}>
          Surprise me again
        </button>
      </div>
    </article>
  )
}
