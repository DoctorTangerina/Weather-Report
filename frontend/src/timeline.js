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

// Slice both boundaries inclusively, preserving missing months and metadata.
export function seriesInRange(series, range) {
  if (!range) return series
  const origin = monthIndex(series.period.start)
  const start = Math.max(0, monthIndex(range.start) - origin)
  const end = Math.min(series.values.length - 1, monthIndex(range.end) - origin)
  return {
    ...series,
    period: { start: monthTimestamp(origin + start), end: monthTimestamp(origin + end) },
    values: series.values.slice(start, Math.max(start, end + 1)),
  }
}
