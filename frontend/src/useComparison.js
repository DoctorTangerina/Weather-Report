import { useEffect, useState } from 'react'
import { getComparison } from './api.js'

const EMPTY = { loading: false, series: [], trends: [], notice: null, error: null }

export default function useComparison(regionA, regionB, variableId) {
  const key = `${regionA}/${regionB}/${variableId}`
  const [state, setState] = useState(EMPTY)

  useEffect(() => {
    if (!regionA || !regionB || !variableId) {
      setState({ ...EMPTY, key })
      return
    }
    let cancelled = false
    setState({ ...EMPTY, loading: true, key })
    getComparison(regionA, regionB, variableId)
      .then(({ data, notice }) => {
        if (!cancelled) setState({ ...EMPTY, ...data, notice, key })
      })
      .catch((error) => {
        if (!cancelled) setState({ ...EMPTY, error, key })
      })
    return () => { cancelled = true }
  }, [regionA, regionB, variableId])

  // Never display a previous pair beneath newly selected Region names.
  return state.key === key ? state : { ...EMPTY, loading: Boolean(regionA && regionB && variableId) }
}
