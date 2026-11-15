import Chart from './Chart.jsx'
import { RegionRate } from './DiscoveryPanel.jsx'

// Compare any catalog pair, including pairs that do not form a Discovery.
export default function Explorer({
  catalog,
  region,
  secondRegion,
  variable,
  variables,
  onRegion,
  onSecondRegion,
  onVariable,
  hasData = () => true,
  error = null,
  series,
  seriesLoading,
  timestamp,
  highlights,
  trends,
}) {

  // Not every Region has a stored series for every Variable. Mark the missing
  // ones for the chosen Variable instead of letting a student hit a blank.
  const label = (item) =>
    variable && !hasData(item.region_id, variable.variable_id)
      ? `${item.name} (no data yet)`
      : item.name

  return (
    <section className="explorer" aria-labelledby="explore-heading">
      <h3 id="explore-heading">Or compare two Regions</h3>
      <p className="muted">Choose two Regions and a shared Variable to see their Trends and monthly series.</p>
      <div className="catalog-controls">
        <label htmlFor="explore-region">First Region</label>
        <select
          id="explore-region"
          value={region?.region_id ?? ''}
          onChange={(event) => onRegion(event.target.value)}
        >
          {catalog.regions.filter((item) => item.region_id !== secondRegion?.region_id).map((item) => (
            <option key={item.region_id} value={item.region_id}>
              {label(item)}
            </option>
          ))}
        </select>
        <label htmlFor="explore-second-region">Second Region</label>
        <select
          id="explore-second-region"
          value={secondRegion?.region_id ?? ''}
          onChange={(event) => onSecondRegion(event.target.value)}
        >
          {catalog.regions.filter((item) => item.region_id !== region?.region_id).map((item) => (
            <option key={item.region_id} value={item.region_id}>{label(item)}</option>
          ))}
        </select>
        <label htmlFor="explore-variable">Variable</label>
        <select
          id="explore-variable"
          value={variable?.variable_id ?? ''}
          disabled={variables.length === 0}
          onChange={(event) => onVariable(event.target.value)}
        >
          {variables.map((item) => (
            <option key={item.variable_id} value={item.variable_id}>
              {item.name}
            </option>
          ))}
        </select>
      </div>
      {error && (
        <p className="notice" role="status">
          {error.code === 'result_not_available'
            ? `There is no stored data yet for ${region?.name} and ${secondRegion?.name} with ${variable?.name.toLowerCase()}. Try a Region that is not marked "no data yet".`
            : `The comparison could not be loaded: ${error.message}`}
        </p>
      )}
      {region && <p className="muted">{region.description}</p>}
      {secondRegion && <p className="muted">{secondRegion.description}</p>}
      {variables.length === 0 && <p role="status">These Regions have no shared Variable.</p>}
      {variable && <p className="variable-definition">{variable.definition}</p>}
      <ul className="region-rates" aria-label="How fast each Region is changing">
        {trends.map((trend) => (
          <RegionRate key={trend.region_id} trend={trend}
            highlight={highlights.find((item) => item.region.region_id === trend.region_id)} />
        ))}
      </ul>
      {seriesLoading && <div className="skeleton skeleton-chart" aria-hidden="true" />}
      {!seriesLoading &&
        series.map((item) => (
          <Chart
            key={`${item.region_id}-${item.variable_id}`}
            series={item}
            timestamp={timestamp}
            color={highlights.find((h) => h.region.region_id === item.region_id)?.color}
            label={catalog.regions.find((r) => r.region_id === item.region_id)?.name ?? item.region_id}
          />
        ))}
    </section>
  )
}
