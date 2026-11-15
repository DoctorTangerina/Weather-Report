import { AGGREGATIONS, describeAggregation } from '../aggregations.js'
import { TIME_STEPS } from '../timeSteps.js'
import { FIRST_MONTH, MAX_VARIABLES } from '../useExploreView.js'
import Chart from './Chart.jsx'

const exclusion = (code, noun) =>
  ({
    too_many_missing_months: 'more than one month in five has no value',
    too_many_missing_time_steps: 'more than one Time step in five has no value',
    insufficient_land_fraction: `less than half of the ${noun} is valid land`,
  })[code] ?? code

// The keyboard route into Explore My World, beside clicking a Region on the globe.
export function ExploreEntry({ catalog, onExplore, children }) {
  return (
    <section className="explore-entry" aria-labelledby="explore-entry-heading">
      <h3 id="explore-entry-heading">Explore My World</h3>
      <p className="muted">
        Click a Region on the globe, or choose one here, to chart its Variables over a period you
        pick.
      </p>
      <div className="catalog-controls">
        <label htmlFor="explore-world-region">Region to explore</label>
        <select
          id="explore-world-region"
          value=""
          onChange={(event) => event.target.value && onExplore(event.target.value)}
        >
          <option value="">Choose a Region</option>
          {catalog.regions.map((item) => (
            <option key={item.region_id} value={item.region_id}>
              {item.name}
            </option>
          ))}
        </select>
      </div>
      {children}
    </section>
  )
}

// The same view for a catalog Region and a Selected area (BS-005); `noun` names
// which one it is in the text ("Region" or "area").
export default function ExploreMyWorld({
  catalog,
  title,
  description,
  noun,
  view,
  color,
  timestamp,
  onBack,
  children,
}) {
  const name = (variableId) =>
    catalog.variables.find((item) => item.variable_id === variableId)?.name ?? variableId

  return (
    <section className="explore" aria-labelledby="explore-view-heading">
      <button className="link" onClick={onBack}>← Back</button>
      <p className="eyebrow">Explore My World</p>
      <h2 id="explore-view-heading">{title}</h2>
      <p className="muted">{description}</p>

      <fieldset className="explore-choices">
        <legend>Variables, up to {MAX_VARIABLES}</legend>
        {view.offered.map((item) => {
          const checked = view.chosen.includes(item.variable_id)
          return (
            <label key={item.variable_id} className="explore-variable">
              <input
                type="checkbox"
                checked={checked}
                disabled={!checked && view.chosen.length >= MAX_VARIABLES}
                onChange={() => view.toggle(item.variable_id)}
              />
              {item.name}
            </label>
          )
        })}
        {view.unavailable.length > 0 && (
          <p className="chart-note">
            {view.timeStep === 'monthly' ? 'No data yet' : `No ${view.timeStep} data`} for{' '}
            {view.unavailable.map((item) => item.name.toLowerCase()).join(', ')}.
          </p>
        )}
        {view.removed && <p className="notice" role="status">{view.removed}</p>}
      </fieldset>

      <div className="catalog-controls">
        <label htmlFor="explore-time-step">Time step</label>
        <select
          id="explore-time-step"
          value={view.timeStep}
          onChange={(event) => view.setTimeStep(event.target.value)}
        >
          {TIME_STEPS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <p className="chart-note">
        {view.utcNote}
        {view.limits && ` ${view.limits}`}
      </p>

      <fieldset className="explore-choices explore-period">
        <legend>Period</legend>
        <span className="explore-month">
          <label htmlFor="explore-start">From</label>
          <input
            id="explore-start"
            type="month"
            min={FIRST_MONTH}
            max={view.latest ?? undefined}
            value={view.start}
            onChange={(event) => view.setStart(event.target.value)}
          />
        </span>
        <span className="explore-month">
          <label htmlFor="explore-end">To</label>
          <input
            id="explore-end"
            type="month"
            min={FIRST_MONTH}
            max={view.latest ?? undefined}
            value={view.end}
            onChange={(event) => view.setEnd(event.target.value)}
          />
        </span>
      </fieldset>
      {view.periodError ? (
        <p className="notice" role="status">{view.periodError}</p>
      ) : (
        <p className="chart-note">{view.range}</p>
      )}
      <div className="catalog-controls">
        <label htmlFor="explore-aggregation">Aggregation</label>
        <select
          id="explore-aggregation"
          value={view.aggregation}
          onChange={(event) => view.setAggregation(event.target.value)}
        >
          {AGGREGATIONS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </div>
      <p className="chart-note">{describeAggregation(view.aggregation, view.timeStep)}</p>

      {view.chosen.length === 0 && <p role="status">Choose at least one Variable.</p>}
      {view.error && (
        <p className="notice" role="status">
          {view.error.code === 'acquisition_failed'
            ? `${view.error.message} Not obtained: ${view.chosen.map(name).join(', ')}.`
            : view.error.code === 'result_not_available'
            ? `There is no stored data yet for ${title} over this period.`
            : `The Series could not be loaded: ${view.error.message}`}
        </p>
      )}
      {view.loading && view.progress != null && (
        <div role="status">
          <p>Obtaining the Series: {view.progress}%</p>
          <progress aria-label="Series acquisition progress" value={view.progress} max="100" />
        </div>
      )}
      {view.loading &&
        view.chosen.map((id) => <div key={id} className="skeleton skeleton-chart" aria-hidden="true" />)}
      <div className="explore-charts">
        {!view.loading &&
          view.series.map((series) =>
            series.quality.included ? (
              <Chart
                key={series.variable_id}
                series={series}
                label={name(series.variable_id)}
                timestamp={view.timeStep === 'monthly' ? timestamp : null}
                timeStep={view.timeStep}
                color={color}
                smoothed={false}
              />
            ) : (
              <p key={series.variable_id} className="notice">
                {name(series.variable_id)} is excluded by the Quality gate for this period:{' '}
                {series.quality.exclusions.map((code) => exclusion(code, noun)).join('; ')}.
              </p>
            ),
          )}
      </div>
      {children}
    </section>
  )
}
