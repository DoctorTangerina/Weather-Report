import { useEffect, useMemo, useState } from 'react'
import { timelineMonths } from '../timeline.js'

export default function Timeline({ series, loading, onTimestampChange, onRangeChange }) {
  const months = useMemo(() => timelineMonths(series), [series])
  const [index, setIndex] = useState(0)
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(null)
  const last = Math.max(0, months.length - 1)
  const rangeEnd = Math.min(end ?? last, last)
  const rangeStart = Math.min(start, rangeEnd)
  const selectedIndex = Math.max(rangeStart, Math.min(index, rangeEnd))
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const enabled = !loading && months.length > 0
  const timestamp = enabled ? months[selectedIndex] : null
  const startTimestamp = enabled ? months[rangeStart] : null
  const endTimestamp = enabled ? months[rangeEnd] : null

  useEffect(() => {
    onTimestampChange(timestamp)
  }, [timestamp, onTimestampChange])

  useEffect(() => {
    // Series can arrive as a new array on every parent render. Notify only
    // when the selected dates change, otherwise setting a new range object
    // in the parent starts a render loop.
    onRangeChange(startTimestamp && endTimestamp ? { start: startTimestamp, end: endTimestamp } : null)
  }, [startTimestamp, endTimestamp, onRangeChange])

  useEffect(() => {
    if (!playing || !enabled) return
    const timer = window.setInterval(() => {
      setIndex((current) => Math.min(Math.max(current, rangeStart) + 1, rangeEnd))
    }, 700 / speed)
    return () => window.clearInterval(timer)
  }, [playing, enabled, rangeStart, rangeEnd, speed])

  useEffect(() => {
    if (selectedIndex >= rangeEnd || !enabled) setPlaying(false)
  }, [selectedIndex, rangeEnd, enabled])

  const togglePlayback = () => {
    if (!playing && selectedIndex === rangeEnd) setIndex(rangeStart)
    setPlaying((current) => !current)
  }

  return (
    <section className="timeline-panel" aria-labelledby="timeline-heading">
      <div className="timeline-heading">
        <h2 id="timeline-heading">Time series</h2>
        <output className="timeline-timestamp" htmlFor="series-timeline" aria-label="Selected timestamp">
          {timestamp ? <><span className="timeline-viewing-label">Viewing</span> <time dateTime={timestamp}>{timestamp}</time></> : loading ? 'Loading…' : 'No series available'}
        </output>
      </div>
      <div className="timeline-controls">
        <div className="timeline-playback">
          <button className="playback-button" onClick={togglePlayback}
            disabled={!enabled || rangeStart === rangeEnd}
            aria-label={playing ? 'Pause time series' : 'Play time series'} aria-pressed={playing}>
            <span aria-hidden="true">{playing ? '❚❚' : '▶'}</span> {playing ? 'Pause' : 'Play'}
          </button>
          <div className="timeline-speed" role="group" aria-label="Playback speed">
            {[1, 1.5, 2].map((rate) => (
              <button key={rate} type="button" aria-pressed={speed === rate}
                onClick={() => setSpeed(rate)}>{rate}×</button>
            ))}
          </div>
        </div>
        <div className="timeline-track">
          <div className={`timeline-range${rangeStart === rangeEnd ? ' is-collapsed' : ''}`} style={{ '--start': `${last ? rangeStart / last * 100 : 0}%`, '--end': `${last ? rangeEnd / last * 100 : 100}%` }}>
            <span className="timeline-handle-label timeline-start-label">From {startTimestamp ?? '—'}</span>
            <span className="timeline-handle-label timeline-end-label">To {endTimestamp ?? '—'}</span>
            <div className="timeline-range-rail" aria-hidden="true" onPointerDown={(event) => {
              if (!enabled || rangeStart === rangeEnd) return
              const bounds = event.currentTarget.getBoundingClientRect()
              const next = Math.round((event.clientX - bounds.left) / bounds.width * last)
              setIndex(Math.max(rangeStart, Math.min(next, rangeEnd)))
              setPlaying(false)
            }} />
            <label className="sr-only" htmlFor="series-timeline">Select month</label>
            <input id="series-timeline" className="timeline-playhead" type="range" min={rangeStart} max={rangeEnd} step="1"
              style={{ left: `calc(${last ? rangeStart / last * 100 : 0}% - 10px)`, width: `calc(${last ? (rangeEnd - rangeStart) / last * 100 : 0}% + 20px)` }}
              value={enabled ? selectedIndex : 0}
              disabled={!enabled || rangeStart === rangeEnd} aria-valuetext={timestamp ?? 'No data'}
              onChange={(event) => { setPlaying(false); setIndex(Number(event.target.value)) }} />
            <input className="timeline-boundary timeline-boundary-start" aria-label="Range start" type="range" min="0" max={last} step="1"
              value={rangeStart} disabled={!enabled || last === 0} aria-valuetext={months[rangeStart] ?? 'No data'}
              onChange={(event) => {
                const next = Math.min(Number(event.target.value), rangeEnd)
                setStart(next); setIndex(Math.max(selectedIndex, next)); setPlaying(false)
              }} />
            <input className="timeline-boundary timeline-boundary-end" aria-label="Range end" type="range" min="0" max={last} step="1"
              value={rangeEnd} disabled={!enabled || last === 0} aria-valuetext={months[rangeEnd] ?? 'No data'}
              onChange={(event) => {
                const next = Math.max(Number(event.target.value), rangeStart)
                setEnd(next); setIndex(Math.min(selectedIndex, next)); setPlaying(false)
              }} />
          </div>
          <div className="timeline-endpoints" aria-hidden="true">
            <span>{months[0] ?? '—'}</span><span>{months.at(-1) ?? '—'}</span>
          </div>
        </div>
      </div>
    </section>
  )
}
