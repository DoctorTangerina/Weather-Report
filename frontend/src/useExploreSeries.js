import { useEffect, useState } from 'react'
import { ApiError, getExploreJob, getExploreSeries } from './api.js'

const EMPTY = { loading: false, series: [], error: null }

// The Series for one Explore My World view. The API builds every value; this
// only asks for them, and never shows an earlier answer under new settings.
// `place` is { regionId } or { rectangles }, and null with nothing open.
// `period` is null while the chosen period is invalid, so nothing is requested.
export default function useExploreSeries(place, variableIds, period, aggregation, timeStep = 'monthly') {
  const placeKey = place?.regionId ?? JSON.stringify(place?.rectangles ?? null)
  const key =
    place && period && variableIds.length > 0
      ? `${placeKey}/${variableIds.join(',')}/${period.start}/${period.end}/${aggregation}/${timeStep}`
      : null
  const [state, setState] = useState(EMPTY)

  useEffect(() => {
    if (!key) {
      setState({ ...EMPTY, key })
      return
    }
    let cancelled = false
    setState({ ...EMPTY, loading: true, key })
    let timer
    let wake
    const wait = () => new Promise((resolve) => {
      wake = resolve
      timer = setTimeout(resolve, 300)
    })
    const load = async () => {
      let { data } = await getExploreSeries(place, variableIds, period, aggregation, timeStep)
      while (!cancelled && data.job) {
        const job = data.job
        if (job.status === 'failed') throw new ApiError(job.error.code, job.error.message)
        if (job.status === 'succeeded') {
          data = job.result
          break
        }
        setState({ ...EMPTY, loading: true, progress: job.progress, key })
        await wait()
        if (cancelled) return
        ;({ data } = await getExploreJob(job.url))
      }
      if (!cancelled) setState({ ...EMPTY, series: data.series, key })
    }
    load()
      .catch((error) => {
        if (!cancelled) setState({ ...EMPTY, error, key })
      })
    return () => {
      cancelled = true
      clearTimeout(timer)
      wake?.()
    }
    // `key` encodes every argument, so it is the only dependency needed.
  }, [key])

  return state.key === key ? state : { ...EMPTY, loading: Boolean(key) }
}
