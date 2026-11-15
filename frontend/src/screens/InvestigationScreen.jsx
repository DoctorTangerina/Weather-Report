import { useState } from 'react'
import Chart from '../components/Chart.jsx'
import Evidence from '../components/Evidence.jsx'

function regionName(catalog, regionId) {
  return catalog.regions.find((region) => region.region_id === regionId)?.name ?? regionId
}

// When the evidence is not strong, the feedback says so in the student's own
// terms, so a matching guess is never read as a settled answer (#10, Q7).
const EVIDENCE_CAVEAT = {
  'Some evidence':
    'Evidence label: Some evidence. The data lean this way, but not strongly enough to be sure.',
  'Not enough evidence yet':
    'Evidence label: Not enough evidence yet. The data cannot yet tell this difference apart from chance.',
}

export default function InvestigationScreen({ discovery, catalog, highlights = [], onBack, stepIndex, onStepChange, loading, series, error, timestamp }) {
  const [guess, setGuess] = useState(null)

  const [predict, check, reason] = discovery.narrative.investigation.steps
  const caveat = EVIDENCE_CAVEAT[discovery.evidence_label]
  const colorOf = (regionId) => highlights.find((h) => h.region.region_id === regionId)?.color

  return (
    <section>
      <button className="link" onClick={onBack}>
        ← Back
      </button>

      <h2>Become a Detective</h2>
      <ol className="steps">
        {['Predict', 'Check', 'Reason'].map((name, index) => (
          <li key={name} className={index === stepIndex ? 'current' : undefined} aria-current={index === stepIndex ? 'step' : undefined}>
            {name}
          </li>
        ))}
      </ol>

      {stepIndex === 0 && (
        <div>
          <h3>{predict.question}</h3>
          <div className="actions">
            {predict.options.map((option) => (
              <button
                key={option.option_id}
                className={guess === option.option_id ? 'primary' : 'secondary'}
                aria-pressed={guess === option.option_id}
                onClick={() => setGuess(option.option_id)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button className="primary" disabled={!guess} onClick={() => onStepChange(1)}>
            Check the data
          </button>
        </div>
      )}

      {stepIndex === 1 && (
        <div>
          <h3>What the data show</h3>
          <p className={guess === predict.answer_option_id ? 'match' : 'mismatch'} role="status">
            {guess === predict.answer_option_id
              ? 'Your guess matches the computed Trends.'
              : 'Your guess does not match the computed Trends.'}
            {caveat && <span className="feedback-caveat"> {caveat}</span>}
          </p>
          <p>{check.comparison}</p>

          {error && <p className="error" role="alert">{error.message}</p>}
          {loading && <p className="muted" role="status">Loading the series…</p>}
          {series.map((item) => (
            <Chart
              key={`${item.region_id}-${item.variable_id}`}
              series={item}
              timestamp={timestamp}
              color={colorOf(item.region_id)}
              label={regionName(catalog, item.region_id)}
            />
          ))}
          {!loading && !error && <p className="muted">Each chart has its own vertical scale. Use the rates above to compare how fast the Regions are changing.</p>}

          <button onClick={() => onStepChange(2)}>Why might this happen?</button>
        </div>
      )}

      {stepIndex === 2 && (
        <div>
          <h3>{reason.prompt}</h3>
          <p>These possible causes are context from scientists. The data show changes, but do not establish what caused them.</p>
          <ul className="causes">
            {reason.possible_causes.map((cause) => (
              <li key={cause.text}>
                <span className="badge">Context from scientists</span> {cause.text}
              </li>
            ))}
          </ul>
        </div>
      )}
      {stepIndex > 0 && <Evidence discovery={discovery} catalog={catalog} />}
    </section>
  )
}
