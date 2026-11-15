import { useEffect, useState } from 'react'
import { DEFAULT_AGGREGATION } from './aggregations.js'
import { getExploreOptions } from './api.js'
import {
  DEFAULT_TIME_STEP,
  UTC_NOTE,
  describeLimits,
  periodLimitProblem,
  timeStepOf,
} from './timeSteps.js'
import useExploreSeries from './useExploreSeries.js'
import { monthIndex } from './timeline.js'

export const FIRST_MONTH = '2000-01'
export const MAX_VARIABLES = 5

// The month `count` months after `month`, both YYYY-MM.
function addMonths(month, count) {
  const index = Number(month.slice(0, 4)) * 12 + Number(month.slice(5, 7)) - 1 + count
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, '0')}`
}

// One Explore My World view: a catalog Region (#75) or a Selected area (#79), up
// to five Variables, one Aggregation (#78), one Time step (#80) and one period,
// the same for every chart. Monthly, a Region offers the Variables with stored
// data and a Selected area those the API can fetch for any area; below a month,
// only the Variables the API has data for at that Time step. The API supplies
// the last requestable month and the caps; a Region's initial period uses the
// seed set.
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
  const steps = options?.time_steps ?? null
  const offeredAt = (timeStep) =>
    candidates.filter((item) => {
      if (area && !options?.area_variable_ids.includes(item.variable_id)) return false
      if (timeStep !== 'monthly') {
        const step = steps?.find((entry) => entry.time_step === timeStep)
        return Boolean(step?.variable_ids.includes(item.variable_id))
      }
      return area || available.has(regionId, item.variable_id)
    })

  // Choices belong to one place; opening another starts from its defaults. Every
  // Selected-area Series is fetched from NASA, so its first period is one year.
  const [choice, setChoice] = useState(null)
  const current =
    choice?.placeKey === placeKey
      ? choice
      : {
          placeKey,
          chosen: offeredAt(DEFAULT_TIME_STEP).slice(0, 1).map((item) => item.variable_id),
          start: area && latest ? addMonths(latest, -11) : FIRST_MONTH,
          end: (area ? latest : available.latest) ?? '',
          aggregation: DEFAULT_AGGREGATION,
          timeStep: DEFAULT_TIME_STEP,
          removed: null,
        }
  const update = (change) => setChoice({ ...current, ...change })
  const offered = offeredAt(current.timeStep)
  const unavailable = candidates.filter((item) => !offered.includes(item))

  // A Variable without data at the new Time step leaves the view, with a note (Q33).
  const setTimeStep = (timeStep) => {
    const next = offeredAt(timeStep).map((item) => item.variable_id)
    const lost = candidates.filter(
      (item) => current.chosen.includes(item.variable_id) && !next.includes(item.variable_id),
    )
    update({
      timeStep,
      chosen: current.chosen.filter((id) => next.includes(id)),
      removed: lost.length
        ? `${lost.map((item) => item.name).join(', ')} ${lost.length > 1 ? 'were' : 'was'} removed: ${lost.length > 1 ? 'they have' : 'it has'} no ${timeStep} data.`
        : null,
    })
  }

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
  } else {
    periodError = periodLimitProblem(steps, current.timeStep, current.start, current.end)
  }

  const cap = { daily: [120, '10 years'], '3-hourly': [12, '1 year'] }[current.timeStep]
  if (!periodError && cap && monthIndex(current.end) - monthIndex(current.start) + 1 > cap[0]) {
    periodError = `${current.timeStep[0].toUpperCase()}${current.timeStep.slice(1)} periods are limited to ${cap[1]}.`
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
    current.timeStep,
  )

  return {
    offered,
    unavailable,
    chosen,
    toggle,
    start: current.start,
    end: current.end,
    setPeriod: (period) => update(period),
    aggregation: current.aggregation,
    setAggregation: (aggregation) => update({ aggregation }),
    timeStep: current.timeStep,
    timeStepLabel: timeStepOf(current.timeStep).label,
    setTimeStep,
    removed: current.removed,
    utcNote: UTC_NOTE,
    limits: describeLimits(steps),
    latest,
    range,
    periodError,
    ...series,
  }
}
