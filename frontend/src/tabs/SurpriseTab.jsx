import { useEffect, useRef, useState } from 'react'
import { surpriseMe } from '../api.js'
import DiscoveryPanel from '../components/DiscoveryPanel.jsx'
import { Drawing, SessionComplete } from '../components/PanelStates.jsx'
import InvestigationScreen from '../screens/InvestigationScreen.jsx'
import { useShell, useTabDeclaration, useTabTimeline } from './shell.js'
import useDiscoveryView from './useDiscoveryView.js'

const NONE = []

// idle → drawing → discovery ⇄ investigation; drawing again from a Discovery
// keeps it on the globe until the next one arrives; complete when the session
// has seen every Discovery worth headlining.
export default function SurpriseTab() {
  const { catalog, session, recordDiscovery, resetSession } = useShell()
  const { timestamp, timeRange } = useTabTimeline()
  const [phase, setPhase] = useState('idle')
  const [discovery, setDiscovery] = useState(null)
  const [notice, setNotice] = useState(null)
  const [error, setError] = useState(null)
  const [step, setStep] = useState(0)
  const drawing = useRef(false)

  const showing = phase === 'discovery' && Boolean(discovery)
  const investigating = phase === 'investigation' && Boolean(discovery)
  const { series, highlights } = useDiscoveryView(
    catalog,
    discovery,
    showing ? 'discovery' : investigating ? 'investigation' : null,
  )

  // Every investigation starts at Predict, however the previous one ended.
  useEffect(() => {
    if (investigating) setStep(0)
  }, [investigating, discovery?.discovery_id])

  // Guards against a double click sending the same session history twice.
  const draw = () => {
    if (drawing.current) return
    drawing.current = true
    const settled = discovery ? 'discovery' : 'idle'
    setError(null)
    setPhase('drawing')
    surpriseMe(session)
      .then((response) => {
        setDiscovery(response.data)
        setNotice(response.notice)
        recordDiscovery(response.data)
        setPhase('discovery')
      })
      .catch((failure) => {
        if (failure.code === 'no_discovery_left_in_session') {
          setPhase('complete')
          return
        }
        setError(failure)
        setPhase(settled)
      })
      .finally(() => {
        drawing.current = false
      })
  }

  // While the next Discovery is drawn, the globe keeps the last one's Regions.
  const shown = useRef(NONE)
  if (phase !== 'drawing') shown.current = showing || investigating ? highlights : NONE
  // Before the student predicts, nothing may hint at the answer (BS-006).
  const timelineSeries =
    series.loading || (investigating && step !== 1) ? NONE : series.series
  useTabDeclaration({
    globe: { highlights: shown.current },
    timeline:
      showing || investigating || phase === 'drawing'
        ? {
            kind: 'series',
            key: `${phase}/${discovery?.discovery_id}`,
            series: timelineSeries,
            loading: series.loading,
          }
        : null,
  })

  return (
    <>
      {notice && (showing || investigating) && (
        <p className="notice" role="status">{notice.message}</p>
      )}
      {error && <p className="error" role="alert">{error.message}</p>}
      {series.error && showing && (
        <p className="error" role="alert">
          The analysis could not be loaded: {series.error.message}
        </p>
      )}
      {phase === 'idle' && (
        <article className="welcome" aria-labelledby="surprise-heading">
          <p className="eyebrow">Surprise Me!</p>
          <h2 id="surprise-heading">Let the engine pick a contrast it found in the data.</h2>
          <p className="welcome-lede">
            Each Discovery is two places changing in ways that contrast, with the evidence
            behind it. You will not see the same one twice in a session.
          </p>
          <div className="experiences">
            <button className="experience" onClick={draw}>
              <span className="experience-title">Surprise Me!</span>
              <span className="experience-text">Show me a Discovery and where it is.</span>
            </button>
          </div>
        </article>
      )}
      {phase === 'drawing' && <Drawing />}
      {phase === 'complete' && (
        <SessionComplete
          seen={session.shownDiscoveryIds.length}
          onNewSession={() => {
            resetSession()
            setDiscovery(null)
            setNotice(null)
            setPhase('idle')
          }}
        />
      )}
      {showing && (
        <DiscoveryPanel
          discovery={discovery}
          catalog={catalog}
          highlights={highlights}
          responses={series.responses}
          substituted={series.substituted}
          seriesError={series.error}
          series={series.series}
          seriesLoading={series.loading}
          timestamp={timestamp}
          timeRange={timeRange}
          onInvestigate={() => setPhase('investigation')}
          onSurprise={draw}
        />
      )}
      {investigating && (
        <InvestigationScreen
          key={discovery.discovery_id}
          discovery={discovery}
          catalog={catalog}
          highlights={highlights}
          onBack={() => setPhase('discovery')}
          stepIndex={step}
          onStepChange={setStep}
          loading={series.loading}
          responses={series.responses}
          substituted={series.substituted}
          error={series.error}
          timestamp={timestamp}
          timeRange={timeRange}
        />
      )}
    </>
  )
}
