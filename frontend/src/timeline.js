export function monthIndex(timestamp) {
  const [year, month] = timestamp.slice(0, 7).split('-').map(Number)
  return year * 12 + month - 1
}

export function monthTimestamp(index) {
  return `${Math.floor(index / 12)}-${String(index % 12 + 1).padStart(2, '0')}`
}

export function timelineMonths(series) {
  const months = new Set()
  for (const item of series) {
    const start = monthIndex(item.period.start)
    item.values.forEach((_, index) => months.add(start + index))
  }
  return [...months].sort((a, b) => a - b).map(monthTimestamp)
}

export function seriesIndexAt(series, timestamp) {
  if (!timestamp) return -1
  const index = monthIndex(timestamp) - monthIndex(series.period.start)
  return index >= 0 && index < series.values.length ? index : -1
}
