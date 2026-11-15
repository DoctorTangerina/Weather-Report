import { useState } from 'react'
import useExploreSeries from './useExploreSeries.js'

export const FIRST_MONTH = '2000-01'
export const MAX_VARIABLES = 5

// One Explore My World view (#75): a catalog Region, up to five Variables and one
// period. Only Variables with stored data are offered. A period outside 2000-01 to
// the latest available month is refused here, before anything is requested.
export default function useExploreView(catalog, region, available) {
  const regionId = region?.region_id ?? null
  const ofRegion = catalog && region
    ? catalog.variables.filter((item) => region.variable_ids.includes(item.variable_id))
    : []
  const offered = ofRegion.filter((item) => available.has(regionId, item.variable_id))
  const unavailable = ofRegion.filter((item) => !offered.includes(item))
  const latest = available.latest

  // Choices belong to one Region; opening another starts from its defaults.
  const [choice, setChoice] = useState(null)
  const current =
    choice?.regionId === regionId
      ? choice
      : {
          regionId,
          chosen: offered.slice(0, 1).map((item) => item.variable_id),
          start: FIRST_MONTH,
          end: latest ?? '',
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
  const series = useExploreSeries(
    regionId,
    chosen,
    periodError ? null : { start: current.start, end: current.end },
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
    latest,
    range,
    periodError,
    ...series,
  }
}
