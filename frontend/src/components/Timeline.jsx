import { useEffect, useMemo, useState } from 'react'
import { timelineMonths } from '../timeline.js'

export default function Timeline({ series, loading, onTimestampChange }) {
  const months = useMemo(() => timelineMonths(series), [series])
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const enabled = !loading && months.length > 0
  const timestamp = enabled ? months[Math.min(index, months.length - 1)] : null

  useEffect(() => {
    onTimestampChange(timestamp)
  }, [timestamp, onTimestampChange])

  useEffect(() => {
    if (!playing || !enabled) return
    const timer = window.setInterval(() => {
      setIndex((current) => Math.min(current + 1, months.length - 1))
    }, 700)
    return () => window.clearInterval(timer)
  }, [playing, enabled, months.length])

  useEffect(() => {
    if (index >= months.length - 1 || !enabled) setPlaying(false)
  }, [index, months.length, enabled])

  const togglePlayback = () => {
    if (!playing && index === months.length - 1) setIndex(0)
    setPlaying((current) => !current)
  }

  return (
    <section className="timeline-panel" aria-labelledby="timeline-heading">
      <div className="timeline-heading">
        <h2 id="timeline-heading">Time series</h2>
        <output className="timeline-timestamp" htmlFor="series-timeline" aria-label="Selected timestamp">
          {timestamp ? <time dateTime={timestamp}>{timestamp}</time> : loading ? 'Loading…' : 'No series available'}
        </output>
      </div>
      <div className="timeline-controls">
        <button className="playback-button" onClick={togglePlayback}
          disabled={!enabled || months.length < 2}
          aria-label={playing ? 'Pause time series' : 'Play time series'} aria-pressed={playing}>
          <span aria-hidden="true">{playing ? 'Ⅱ' : '▶'}</span> {playing ? 'Pause' : 'Play'}
        </button>
        <div className="timeline-track">
          <label className="sr-only" htmlFor="series-timeline">Select month</label>
          <input id="series-timeline" type="range" min="0" max={Math.max(0, months.length - 1)} step="1"
            value={enabled ? Math.min(index, months.length - 1) : 0}
            disabled={!enabled || months.length < 2} aria-valuetext={timestamp ?? 'No data'}
            onChange={(event) => { setPlaying(false); setIndex(Number(event.target.value)) }} />
          <div className="timeline-endpoints" aria-hidden="true">
            <span>{months[0] ?? '—'}</span><span>{months.at(-1) ?? '—'}</span>
          </div>
        </div>
      </div>
    </section>
  )
}
