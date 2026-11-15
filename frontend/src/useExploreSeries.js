import { useEffect, useState } from 'react'
import { getExploreSeries } from './api.js'

const EMPTY = { loading: false, series: [], error: null }

// The Series for one Explore My World view. The API builds every value; this
// only asks for them, and never shows an earlier answer under new settings.
// `period` is null while the chosen period is invalid, so nothing is requested.
export default function useExploreSeries(regionId, variableIds, period) {
  const key =
    regionId && period && variableIds.length > 0
      ? `${regionId}/${variableIds.join(',')}/${period.start}/${period.end}`
      : null
  const [state, setState] = useState(EMPTY)

  useEffect(() => {
    if (!key) {
      setState({ ...EMPTY, key })
      return
    }
    let cancelled = false
    setState({ ...EMPTY, loading: true, key })
    getExploreSeries(regionId, variableIds, period)
      .then(({ data }) => {
        if (!cancelled) setState({ ...EMPTY, series: data.series, key })
      })
      .catch((error) => {
        if (!cancelled) setState({ ...EMPTY, error, key })
      })
    return () => {
      cancelled = true
    }
    // `key` encodes every argument, so it is the only dependency needed.
  }, [key])

  return state.key === key ? state : { ...EMPTY, loading: Boolean(key) }
}
