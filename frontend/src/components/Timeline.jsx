import { useEffect, useMemo, useState } from 'react'
import { monthIndex, monthTimestamp, timelineMonths } from '../timeline.js'

export default function Timeline({ series, loading, onTimestampChange, onRangeChange, domain, range, headingControls, children }) {
  const months = useMemo(() => {
    if (!domain) return timelineMonths(series)
    const first = monthIndex(domain.start)
    return Array.from({ length: monthIndex(domain.end) - first + 1 }, (_, i) => monthTimestamp(first + i))
  }, [series, domain?.start, domain?.end])
  const [index, setIndex] = useState(0)
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(null)
  const last = Math.max(0, months.length - 1)
  // Request timelines use calendar months independently of the loaded Series.
  const offset = domain ? monthIndex(domain.start) : 0
  const rangeEnd = range ? Math.max(0, Math.min(monthIndex(range.end) - monthIndex(domain.start), last)) : Math.min(end ?? last, last)
  const rangeStart = range ? Math.max(0, Math.min(monthIndex(range.start) - monthIndex(domain.start), rangeEnd)) : Math.min(start, rangeEnd)
  const selectedIndex = Math.max(rangeStart, Math.min(index - offset, rangeEnd))
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const rangeEnabled = months.length > 0 && (Boolean(domain) || !loading)
  const enabled = !loading && months.length > 0
  const timestamp = enabled ? months[selectedIndex] : null
  const startTimestamp = rangeEnabled ? months[rangeStart] : null
  const endTimestamp = rangeEnabled ? months[rangeEnd] : null

  useEffect(() => {
    onTimestampChange(timestamp)
  }, [timestamp, onTimestampChange])

  useEffect(() => {
    // Series can arrive as a new array on every parent render. Notify only
    // when the selected dates change, otherwise setting a new range object
    // in the parent starts a render loop.
    if (range) return
    onRangeChange(startTimestamp && endTimestamp ? { start: startTimestamp, end: endTimestamp } : null)
  }, [startTimestamp, endTimestamp, onRangeChange, range])

  useEffect(() => {
    if (!playing || !enabled) return
    const timer = window.setInterval(() => {
      setIndex((current) => Math.min(Math.max(current - offset, rangeStart) + 1, rangeEnd) + offset)
    }, 700 / speed)
    return () => window.clearInterval(timer)
  }, [playing, enabled, rangeStart, rangeEnd, speed, offset])

  useEffect(() => {
    if (selectedIndex >= rangeEnd || !enabled) setPlaying(false)
  }, [selectedIndex, rangeEnd, enabled])

  const togglePlayback = () => {
    if (!playing && selectedIndex === rangeEnd) setIndex(rangeStart + offset)
    setPlaying((current) => !current)
  }

  return (
    <section className={`timeline-panel${domain ? ' has-request-period' : ''}`} aria-labelledby="timeline-heading">
      <div className={`timeline-heading${headingControls ? ' has-time-step' : ''}`}>
        <div className="timeline-title">
          <h2 id="timeline-heading">Time series</h2>
          {headingControls}
        </div>
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
              setIndex(Math.max(rangeStart, Math.min(next, rangeEnd)) + offset)
              setPlaying(false)
            }} />
            <label className="sr-only" htmlFor="series-timeline">Select month</label>
            <input id="series-timeline" className="timeline-playhead" type="range" min={rangeStart} max={rangeEnd} step="1"
              style={{ left: `calc(${last ? rangeStart / last * 100 : 0}% - 10px)`, width: `calc(${last ? (rangeEnd - rangeStart) / last * 100 : 0}% + 20px)` }}
              value={enabled ? selectedIndex : 0}
              disabled={!enabled || rangeStart === rangeEnd} aria-valuetext={timestamp ?? 'No data'}
              onChange={(event) => { setPlaying(false); setIndex(Number(event.target.value) + offset) }} />
            <input className="timeline-boundary timeline-boundary-start" aria-label="Range start" type="range" min="0" max={last} step="1"
              value={rangeStart} disabled={!rangeEnabled || last === 0} aria-valuetext={months[rangeStart] ?? 'No data'}
              onChange={(event) => {
                const next = Math.min(Number(event.target.value), rangeEnd)
                if (range) onRangeChange({ start: months[next], end: range.end })
                setStart(next); setIndex(Math.max(selectedIndex, next) + offset); setPlaying(false)
              }} />
            <input className="timeline-boundary timeline-boundary-end" aria-label="Range end" type="range" min="0" max={last} step="1"
              value={rangeEnd} disabled={!rangeEnabled || last === 0} aria-valuetext={months[rangeEnd] ?? 'No data'}
              onChange={(event) => {
                const next = Math.max(Number(event.target.value), rangeStart)
                if (range) onRangeChange({ start: range.start, end: months[next] })
                setEnd(next); setIndex(Math.min(selectedIndex, next) + offset); setPlaying(false)
              }} />
          </div>
          <div className="timeline-track-footer">
            <div className="timeline-endpoints" aria-hidden="true">
              <span>{months[0] ?? '—'}</span><span>{months.at(-1) ?? '—'}</span>
            </div>
            {children}
          </div>
        </div>
      </div>
    </section>
  )
}
