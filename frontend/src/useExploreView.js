import { useEffect, useState } from 'react'
import { DEFAULT_AGGREGATION } from './aggregations.js'
import { getExploreOptions } from './api.js'
import useExploreSeries from './useExploreSeries.js'

export const FIRST_MONTH = '2000-01'
export const MAX_VARIABLES = 5

// The month `count` months after `month`, both YYYY-MM.
function addMonths(month, count) {
  const index = Number(month.slice(0, 4)) * 12 + Number(month.slice(5, 7)) - 1 + count
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}`
}

// One Explore My World view: a catalog Region (#75) or a Selected area (#79), up
// to five Variables, one Aggregation (#78) and one period, the same for every
// chart. A Region offers the Variables with stored data; a Selected area offers
// those the API can fetch for any area. The API supplies the last requestable
// month; a Region's initial period uses the seed set.
export default function useExploreView(catalog, region, available, area = null) {
  const [options, setOptions] = useState(null)
  useEffect(() => {
    let cancelled = false
    getExploreOptions().then(({ data }) => {
      if (!cancelled) setOptions(data)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])
  const latest = options?.latest_month ?? available.latest

  const regionId = region?.region_id ?? null
  const placeKey = area ? `area:${JSON.stringify(area)}` : regionId
  const candidates = !catalog
    ? []
    : area
      ? catalog.variables
      : catalog.variables.filter((item) => region?.variable_ids.includes(item.variable_id))
  const offered = candidates.filter((item) =>
    area
      ? options?.area_variable_ids.includes(item.variable_id)
      : available.has(regionId, item.variable_id),
  )
  const unavailable = candidates.filter((item) => !offered.includes(item))

  // Choices belong to one place; opening another starts from its defaults. Every
  // Selected-area Series is fetched from NASA, so its first period is one year.
  const [choice, setChoice] = useState(null)
  const current =
    choice?.placeKey === placeKey
      ? choice
      : {
          placeKey,
          chosen: offered.slice(0, 1).map((item) => item.variable_id),
          start: area && latest ? addMonths(latest, -11) : FIRST_MONTH,
          end: (area ? latest : available.latest) ?? '',
          aggregation: DEFAULT_AGGREGATION,
        }
  const update = (change) => setChoice({ ...current, ...change })

  const toggle = (variableId) => {
    if (current.chosen.includes(variableId)) {
      update({ chosen: current.chosen.filter((id) => id !== variableId) })
    } else if (current.chosen.length < MAX_VARIABLES) {
      update({ chosen: [...current.chosen, variableId] })
    }
  }

  const range = latest
    ? `Periods run from ${FIRST_MONTH} to ${latest}, the latest available month.`
    : `Periods run from ${FIRST_MONTH} to the latest available month.`
  let periodError = null
  if (!current.start || !current.end) {
    periodError = 'Choose a start and an end month.'
  } else if (current.start < FIRST_MONTH || (latest && current.end > latest)) {
    periodError = range
  } else if (current.start > current.end) {
    periodError = 'The period must start before it ends.'
  }

  // Charts follow the catalog's order, whatever order the Variables were chosen in.
  const chosen = offered
    .filter((item) => current.chosen.includes(item.variable_id))
    .map((item) => item.variable_id)
  const place = area ? { rectangles: area } : regionId ? { regionId } : null
  const series = useExploreSeries(
    place,
    chosen,
    periodError ? null : { start: current.start, end: current.end },
    current.aggregation,
  )

  return {
    offered,
    unavailable,
    chosen,
    toggle,
    start: current.start,
    end: current.end,
    setStart: (start) => update({ start }),
    setEnd: (end) => update({ end }),
    aggregation: current.aggregation,
    setAggregation: (aggregation) => update({ aggregation }),
    latest,
    range,
    periodError,
    ...series,
  }
}
