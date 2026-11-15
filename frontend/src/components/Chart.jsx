import { formatNumber } from '../format.js'
import { seriesIndexAt, seriesInRange } from '../timeline.js'

const WIDTH = 520
const HEIGHT = 170
const PAD = { top: 10, right: 10, bottom: 26, left: 70 }
const PLOT_W = WIDTH - PAD.left - PAD.right
const PLOT_H = HEIGHT - PAD.top - PAD.bottom

// A centred 12-month mean. The monthly line is dominated by the seasonal cycle;
// averaging over a full year lets the longer-term change show through. Months
// with too little data around them are left as gaps rather than guessed.
function yearlyMean(values) {
  return values.map((_, index) => {
    const window = values
      .slice(Math.max(0, index - 6), index + 6)
      .filter((value) => value !== null)
    return window.length >= 9
      ? window.reduce((sum, value) => sum + value, 0) / window.length
      : null
  })
}

function path(values, x, y) {
  let d = ''
  let drawing = false
  values.forEach((value, index) => {
    if (value === null) {
      drawing = false
      return
    }
    d += `${drawing ? 'L' : 'M'}${x(index).toFixed(1)},${y(value).toFixed(1)}`
    drawing = true
  })
  return d
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Ticks depend only on the period, so charts of one period share their axis.
// Long periods mark every fifth or second January; up to two years, every quarter.
function timeTicks(period, length) {
  const startYear = Number(period.start.slice(0, 4))
  const startMonth = Number(period.start.slice(5, 7))
  const years = length / 12
  const ticks = []
  for (let index = 0; index < length; index += 1) {
    const month = (startMonth - 1 + index) % 12
    const year = startYear + Math.floor((startMonth - 1 + index) / 12)
    if (years <= 2) {
      if (month % 3 === 0) ticks.push({ index, text: month === 0 ? `${MONTHS[0]} ${year}` : MONTHS[month] })
    } else if (month === 0 && year % (years > 12 ? 5 : years > 4 ? 2 : 1) === 0) {
      ticks.push({ index, text: String(year) })
    }
  }
  return ticks
}

// `smoothed` adds a 12-month mean drawn by the browser. Explore My World turns it
// off: there every value on screen comes from the API (#75).
export default function Chart({ series, label, timestamp, color, timeRange, smoothed = true }) {
  series = seriesInRange(series, timeRange)
  const present = series.values.filter((value) => value !== null)
  if (present.length === 0) return <p className="muted">No data for {label}.</p>

  const min = Math.min(...present)
  const max = Math.max(...present)
  const span = max - min || 1
  const last = Math.max(1, series.values.length - 1)
  const x = (index) => PAD.left + (index / last) * PLOT_W
  const y = (value) => PAD.top + PLOT_H - ((value - min) / span) * PLOT_H

  const selectedIndex = seriesIndexAt(series, timestamp)
  const selectedValue = selectedIndex >= 0 ? series.values[selectedIndex] : null
  const style = color ? { '--series': color } : undefined

  return (
    <figure className="chart" style={style}>
      <figcaption>
        <span className="chart-swatch" aria-hidden="true" />
        {label} <span className="muted">({series.units})</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`${label}, monthly values in ${series.units} from ${series.period.start} to ${series.period.end}${smoothed ? ', with a 12-month average' : ''}`}
      >
        <line
          className="chart-axis"
          x1={PAD.left}
          x2={WIDTH - PAD.right}
          y1={PAD.top + PLOT_H}
          y2={PAD.top + PLOT_H}
        />
        <text className="chart-tick" x={PAD.left - 6} y={PAD.top + 12} textAnchor="end">
          {formatNumber(max)}
        </text>
        <text className="chart-tick" x={PAD.left - 6} y={PAD.top + PLOT_H} textAnchor="end">
          {formatNumber(min)}
        </text>
        {timeTicks(series.period, series.values.length).map(({ index, text }) => (
          <text key={index} className="chart-tick chart-time" x={x(index)} y={HEIGHT - 4} textAnchor="middle">
            {text}
          </text>
        ))}
        <path className="chart-monthly" d={path(series.values, x, y)} />
        {smoothed && <path className="chart-mean" d={path(yearlyMean(series.values), x, y)} />}
        {selectedIndex >= 0 && (
          <line
            className="chart-cursor"
            x1={x(selectedIndex)}
            x2={x(selectedIndex)}
            y1={PAD.top}
            y2={PAD.top + PLOT_H}
          />
        )}
        {selectedIndex >= 0 && selectedValue !== null && (
          <circle className="chart-point" cx={x(selectedIndex)} cy={y(selectedValue)} r="4" />
        )}
      </svg>
      {timestamp && (
        <p className="chart-value">
          {timestamp}:{' '}
          {selectedValue === null ? 'no data' : `${formatNumber(selectedValue)} ${series.units}`}
        </p>
      )}
    </figure>
  )
}
