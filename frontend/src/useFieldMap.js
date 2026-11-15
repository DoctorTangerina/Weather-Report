import { useEffect, useMemo, useState } from 'react'
import { ApiError, getExploreJob, getFieldMap } from './api.js'

// One Variable and one frame, with the backend's period-wide colour range.
export default function useFieldMap(place, view) {
  const placeKey = JSON.stringify(place)
  const [openedFor, setOpenedFor] = useState(null)
  const open = Boolean(place && openedFor === placeKey)
  useEffect(() => { setOpenedFor(null) }, [placeKey])
  const [choice, setChoice] = useState(null)
  const variableId = choice?.placeKey === placeKey && view.chosen.includes(choice.id)
    ? choice.id : view.chosen[0]
  const key = open && variableId && !view.periodError
    ? JSON.stringify([place, variableId, view.start, view.end, view.timeStep, view.aggregation]) : null
  const [state, setState] = useState({})
  const [position, setPosition] = useState({})
  const index = position.key === key ? position.index : 0

  useEffect(() => {
    if (!key) return undefined
    let cancelled = false
    let timer
    let wake
    setState({ key, loading: true })
    const load = async () => {
      let { data } = await getFieldMap(place, variableId,
        { start: view.start, end: view.end }, view.aggregation, view.timeStep)
      while (!cancelled && data.job) {
        const job = data.job
        if (job.status === 'failed') throw new ApiError(job.error.code, job.error.message)
        if (job.status === 'succeeded') { data = job.result; break }
        setState({ key, loading: true, progress: job.progress })
        await new Promise((resolve) => { wake = resolve; timer = setTimeout(resolve, 300) })
        if (cancelled) return
        ;({ data } = await getExploreJob(job.url))
      }
      if (!cancelled) setState({ key, data })
    }
    load().catch((error) => { if (!cancelled) setState({ key, error }) })
    return () => { cancelled = true; clearTimeout(timer); wake?.() }
  }, [key])

  const data = key && state.key === key ? state.data : null
  const frame = useMemo(() => data ? { ...data, index } : null, [data, index])
  return {
    open, toggle: () => {
      if (!open) { setChoice(null); setPosition({}) }
      setOpenedFor(open ? null : placeKey)
    }, variableId,
    setVariableId: (id) => setChoice({ placeKey, id }),
    index, setIndex: (next) => setPosition({ key, index: next }), data, frame,
    loading: Boolean(key && (state.key !== key || state.loading)),
    progress: state.key === key ? state.progress : null,
    error: state.key === key ? state.error : null,
  }
}
