import { FIRST_MONTH } from '../useExploreView.js'
import Timeline from './Timeline.jsx'

export default function ExploreTimeline({ view, series, onTimestampChange }) {
  const ready = Boolean(view.latest && view.start && view.end)

  return <Timeline
    series={series}
    loading={view.loading}
    domain={view.latest ? { start: FIRST_MONTH, end: view.latest } : null}
    range={ready ? { start: view.start, end: view.end } : null}
    onTimestampChange={onTimestampChange}
    onRangeChange={(range) => { if (ready && range) view.setPeriod(range) }}
    headingControls={
      <div className="timeline-time-step" role="group" aria-label="Time step">
        {['monthly', 'daily', '3-hourly'].map((step) => (
          <button key={step} type="button" aria-pressed={view.timeStep === step}
            onClick={() => view.setTimeStep(step)}>
            {step === '3-hourly' ? step : step[0].toUpperCase() + step.slice(1)}
          </button>
        ))}
      </div>
    }
  >
    {view.periodError && <p className="notice timeline-period-error" role="status">{view.periodError}</p>}
  </Timeline>
}
