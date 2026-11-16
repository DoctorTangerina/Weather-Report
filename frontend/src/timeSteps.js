// The Time steps of spec #72 (#80). The API builds every value and owns the
// caps (`/api/explore/options`); this names the choices, checks a period
// against the caps before anything is requested, and places each value in time
// for the chart's axis. Days and 3-hour intervals follow UTC.
export const TIME_STEPS = [
  { id: '3-hourly', label: '3-hourly', unit: '3 hours', hours: 3 },
  { id: 'daily', label: 'Daily', unit: 'day', hours: 24 },
  { id: 'monthly', label: 'Monthly', unit: 'month', hours: null },
]

export const DEFAULT_TIME_STEP = 'monthly'

export const UTC_NOTE = 'Days and 3-hour intervals follow UTC.'

export const timeStepOf = (id) => TIME_STEPS.find((item) => item.id === id) ?? TIME_STEPS[2]

const HOUR = 3600 * 1000

// Calendar months from start to end (YYYY-MM), counting both.
export function monthsBetween(start, end) {
  const index = (month) => Number(month.slice(0, 4)) * 12 + Number(month.slice(5, 7))
  return index(end) - index(start) + 1
}

// `steps` is the API's options.time_steps; null until they have loaded.
export function describeLimits(steps) {
  const capped = (steps ?? []).filter((item) => item.max_months != null)
  if (capped.length === 0) return null
  const name = (item) => timeStepOf(item.time_step).label.toLowerCase()
  const [first, ...rest] = capped
  const parts = [
    `${name(first)} periods are limited to ${first.limit}`,
    ...rest.map((item) => `${name(item)} periods to ${item.limit}`),
  ]
  const text = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0]
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`
}

// Why a period cannot be requested at this Time step, or null.
export function periodLimitProblem(steps, timeStep, start, end) {
  const step = (steps ?? []).find((item) => item.time_step === timeStep)
  if (!step?.max_months || monthsBetween(start, end) <= step.max_months) return null
  return `${timeStepOf(timeStep).label} periods are limited to ${step.limit}.`
}

function stepDate(period, timeStep, index) {
  const year = Number(period.start.slice(0, 4))
  const month = Number(period.start.slice(5, 7)) - 1
  const hours = timeStepOf(timeStep).hours
  return hours
    ? new Date(Date.UTC(year, month, 1) + index * hours * HOUR)
    : new Date(Date.UTC(year, month + index, 1))
}

// The UTC month (year * 12 + month index) that a Series' `index`th value falls in.
export function monthAt(period, timeStep, index) {
  const date = stepDate(period, timeStep, index)
  return date.getUTCFullYear() * 12 + date.getUTCMonth()
}

// "first to last" Time step of a Series of `count` values.
export function stepRange(period, timeStep, count) {
  if (timeStep === 'monthly') return `${period.start} to ${period.end}`
  const text = (date) => {
    const iso = date.toISOString()
    return timeStep === 'daily' ? iso.slice(0, 10) : `${iso.slice(0, 10)} ${iso.slice(11, 16)}`
  }
  return `${text(stepDate(period, timeStep, 0))} to ${text(stepDate(period, timeStep, count - 1))} UTC`
}
