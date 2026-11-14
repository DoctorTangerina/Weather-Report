import Chart from './Chart.jsx'

// Free exploration of one catalog Region and one of its Variables, shown on the
// welcome panel before any Discovery is drawn. The choices are limited to the
// catalog, and a Variable is offered only for the Regions it applies to.
export default function Explorer({
  catalog,
  region,
  variable,
  variables,
  onRegion,
  onVariable,
  series,
  seriesLoading,
  timestamp,
  color,
}) {
  return (
    <section className="explorer" aria-labelledby="explore-heading">
      <h3 id="explore-heading">Or explore one Region</h3>
      <p className="muted">Choose a Region and a Variable to see its monthly series.</p>
      <div className="catalog-controls">
        <label htmlFor="explore-region">Region</label>
        <select
          id="explore-region"
          value={region?.region_id ?? ''}
          onChange={(event) => onRegion(event.target.value)}
        >
          {catalog.regions.map((item) => (
            <option key={item.region_id} value={item.region_id}>
              {item.name}
            </option>
          ))}
        </select>
        <label htmlFor="explore-variable">Variable</label>
        <select
          id="explore-variable"
          value={variable?.variable_id ?? ''}
          onChange={(event) => onVariable(event.target.value)}
        >
          {variables.map((item) => (
            <option key={item.variable_id} value={item.variable_id}>
              {item.name}
            </option>
          ))}
        </select>
      </div>
      {region && <p className="muted">{region.description}</p>}
      {variable && <p className="variable-definition">{variable.definition}</p>}
      {seriesLoading && <div className="skeleton skeleton-chart" aria-hidden="true" />}
      {!seriesLoading &&
        series.map((item) => (
          <Chart
            key={`${item.region_id}-${item.variable_id}`}
            series={item}
            timestamp={timestamp}
            color={color}
            label={region?.name ?? item.region_id}
          />
        ))}
    </section>
  )
}
