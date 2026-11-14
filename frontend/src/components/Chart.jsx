import { seriesIndexAt } from '../timeline.js'

const WIDTH = 520
const HEIGHT = 140

export default function Chart({ series, label, timestamp }) {
  const present = series.values.filter((value) => value !== null)
  if (present.length === 0) return <p className="muted">No data for {label}.</p>

  const min = Math.min(...present)
  const max = Math.max(...present)
  const span = max - min || 1
  const selectedIndex = seriesIndexAt(series, timestamp)
  const selectedValue = selectedIndex >= 0 ? series.values[selectedIndex] : null
  const selectedX = selectedIndex / Math.max(1, series.values.length - 1) * WIDTH
  const points = series.values
    .map((value, index) =>
      value === null
        ? null
        : `${(index / Math.max(1, series.values.length - 1)) * WIDTH},${HEIGHT - ((value - min) / span) * HEIGHT}`,
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
        {selectedIndex >= 0 && <line className="chart-cursor" x1={selectedX} x2={selectedX} y1="0" y2={HEIGHT} />}
        {selectedValue != null && (
          <circle className="chart-point" cx={selectedX} cy={HEIGHT - ((selectedValue - min) / span) * HEIGHT} r="4" />
        )}
      </svg>
      <p className="muted">
        {series.period.start} to {series.period.end}
      </p>
      {timestamp && <p className="chart-value">{timestamp}: {selectedValue == null ? 'No data' : `${selectedValue.toLocaleString(undefined, { maximumFractionDigits: 3 })} ${series.units}`}</p>}
    </figure>
  )
}
