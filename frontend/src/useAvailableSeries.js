import { useEffect, useState } from 'react'
import { getAvailableSeries } from './api.js'

const key = (regionId, variableId) => `${regionId}/${variableId}`

// Which Region-Variable series the service holds. If the list cannot be
// fetched, every pair is treated as possibly available, so nothing is ever
// marked missing by mistake.
export default function useAvailableSeries() {
  const [state, setState] = useState({ settled: false, pairs: null })

  useEffect(() => {
    let cancelled = false
    getAvailableSeries()
      .then(({ data }) => {
        if (!cancelled) {
          const pairs = new Set(data.map((s) => key(s.region_id, s.variable_id)))
          setState({ settled: true, pairs })
        }
      })
      .catch(() => {
        if (!cancelled) setState({ settled: true, pairs: null })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const has = (regionId, variableId) =>
    state.pairs === null || state.pairs.has(key(regionId, variableId))

  // The first catalog Variable that two catalog Regions both hold, so the
  // Explorer opens on a comparison that can actually be drawn.
  const defaultPair = (catalog) => {
    if (!state.pairs || !catalog) return null
    for (const variable of catalog.variables) {
      const held = catalog.regions.filter(
        (region) =>
          region.variable_ids.includes(variable.variable_id) &&
          state.pairs.has(key(region.region_id, variable.variable_id)),
      )
      if (held.length >= 2) {
        return [held[0].region_id, held[1].region_id, variable.variable_id]
      }
    }
    return null
  }

  return { settled: state.settled, has, defaultPair }
}
