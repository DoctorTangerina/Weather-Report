import { useState } from 'react'
import Chart from '../components/Chart.jsx'
import useSeries from '../useSeries.js'

function regionName(catalog, regionId) {
  return catalog.regions.find((region) => region.region_id === regionId)?.name ?? regionId
}

function HowDoWeKnow({ discovery, catalog }) {
  const evidence = discovery.narrative.how_do_we_know
  return (
    <aside className="evidence">
      <h3>How do we know?</h3>
      <p>
        Period analyzed: {evidence.period.start} to {evidence.period.end}.
      </p>
      <ul>
        {discovery.contrasts.flatMap((contrast) =>
          contrast.trends.map((trend) => (
            <li key={`${trend.region_id}-${trend.variable_id}`}>
              <strong>{regionName(catalog, trend.region_id)}</strong> — {trend.rate_per_decade}{' '}
              {trend.units_per_decade} (95% interval {trend.confidence_interval_95[0]} to{' '}
              {trend.confidence_interval_95[1]}). {trend.evidence_label}.
            </li>
          )),
        )}
      </ul>
      <ul>
        {evidence.sources.map((entry) => (
          <li key={`${entry.region_id}-${entry.variable_id}`}>
            Source: {entry.source.provider} — {entry.source.dataset} ({entry.source.variable})
          </li>
        ))}
      </ul>
      <p>{evidence.statistics_summary}</p>
      <p className="muted">Method: {evidence.method_citation}</p>
    </aside>
  )
}

export default function InvestigationScreen({ discovery, catalog, onBack }) {
  const [stepIndex, setStepIndex] = useState(0)
  const [guess, setGuess] = useState(null)
  const [showEvidence, setShowEvidence] = useState(false)

  const [predict, check, reason] = discovery.narrative.investigation.steps
  const { loading, series, error } = useSeries(check.series)

  return (
    <section>
      <button className="link" onClick={onBack}>
        ← Back
      </button>

      <h1>Become a Detective</h1>
      <ol className="steps">
        {['Predict', 'Check', 'Reason'].map((name, index) => (
          <li key={name} className={index === stepIndex ? 'current' : undefined}>
            {name}
          </li>
        ))}
      </ol>

      {stepIndex === 0 && (
        <div>
          <h2>{predict.question}</h2>
          <div className="actions">
            {predict.options.map((option) => (
              <button
                key={option.option_id}
                className={guess === option.option_id ? undefined : 'secondary'}
                onClick={() => setGuess(option.option_id)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button disabled={!guess} onClick={() => setStepIndex(1)}>
            Check the data
          </button>
        </div>
      )}

      {stepIndex === 1 && (
        <div>
          <h2>What the data show</h2>
          <p className={guess === predict.answer_option_id ? 'match' : 'mismatch'}>
            {guess === predict.answer_option_id
              ? 'Your guess matches the computed Trends.'
              : 'Your guess does not match the computed Trends.'}
          </p>
          <p>{check.comparison}</p>

          {error && <p className="error">{error.message}</p>}
          {loading && <p className="muted">Loading the series…</p>}
          {series.map((item) => (
            <Chart
              key={`${item.region_id}-${item.variable_id}`}
              series={item}
              label={regionName(catalog, item.region_id)}
            />
          ))}

          <button onClick={() => setStepIndex(2)}>Why might this happen?</button>
        </div>
      )}

      {stepIndex === 2 && (
        <div>
          <h2>{reason.prompt}</h2>
          <ul className="causes">
            {reason.possible_causes.map((cause) => (
              <li key={cause.text}>
                <span className="badge">Context from scientists</span> {cause.text}
              </li>
            ))}
          </ul>
          <button className="secondary" onClick={() => setShowEvidence((shown) => !shown)}>
            {showEvidence ? 'Hide' : 'How do we know?'}
          </button>
          {showEvidence && <HowDoWeKnow discovery={discovery} catalog={catalog} />}
        </div>
      )}
    </section>
  )
}
