import { useEffect, useState } from 'react'
import { getSeries } from './api.js'

export default function useSeries(refs) {
  const [state, setState] = useState({ loading: true, series: [], notice: null, error: null })
  const key = refs.map((ref) => `${ref.region_id}/${ref.variable_id}`).join('|')

  useEffect(() => {
    let cancelled = false
    setState({ loading: true, series: [], notice: null, error: null })

    Promise.all(refs.map((ref) => getSeries(ref.region_id, ref.variable_id)))
      .then((responses) => {
        if (cancelled) return
        setState({
          loading: false,
          series: responses.map((response) => response.data),
          notice: responses.map((response) => response.notice).find(Boolean) ?? null,
          error: null,
        })
      })
      .catch((error) => {
        if (!cancelled) setState({ loading: false, series: [], notice: null, error })
      })

    return () => {
      cancelled = true
    }
  }, [key])

  return state
}
