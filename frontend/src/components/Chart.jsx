const WIDTH = 520
const HEIGHT = 140

export default function Chart({ series, label }) {
  const present = series.values.filter((value) => value !== null)
  if (present.length === 0) return <p className="muted">No data for {label}.</p>

  const min = Math.min(...present)
  const max = Math.max(...present)
  const span = max - min || 1
  const points = series.values
    .map((value, index) =>
      value === null
        ? null
        : `${(index / (series.values.length - 1)) * WIDTH},${HEIGHT - ((value - min) / span) * HEIGHT}`,
    )
    .filter(Boolean)
    .join(' ')

  return (
    <figure className="chart">
      <figcaption>
        {label} <span className="muted">({series.units})</span>
      </figcaption>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${label} over time`}>
        <polyline points={points} />
      </svg>
      <p className="muted">
        {series.period.start} to {series.period.end}
      </p>
    </figure>
  )
}
