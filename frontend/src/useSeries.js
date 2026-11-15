import { useEffect, useState } from 'react'
import { getSeries } from './api.js'

export default function useSeries(refs, period) {
  const key = JSON.stringify([refs, period])
  const [state, setState] = useState({ key: null, responses: [], error: null })

  useEffect(() => {
    let cancelled = false
    const [requestedRefs, requestedPeriod] = JSON.parse(key)
    Promise.all(requestedRefs.map((ref) => getSeries(ref.region_id, ref.variable_id, requestedPeriod)))
      .then((responses) => {
        if (!cancelled) setState({ key, responses, error: null })
      })
      .catch((error) => {
        if (!cancelled) setState({ key, responses: [], error })
      })
    return () => { cancelled = true }
  }, [key])

  const loading = state.key !== key
  const responses = loading ? [] : state.responses
  const substituted = responses.some(({ data, notice }, index) =>
    notice?.code === 'live_data_unavailable' ||
    data.region_id !== refs[index].region_id ||
    data.variable_id !== refs[index].variable_id ||
    (period && (data.period.start !== period.start || data.period.end !== period.end)),
  )
  return {
    loading,
    responses,
    series: responses.map(({ data }) => data),
    notice: responses.map(({ notice }) => notice).find(Boolean) ?? null,
    substituted,
    error: loading ? null : state.error,
  }
}
