export function Welcome({ catalog, onSurprise, onDetective, detectiveError, checkingDiscovery }) {
  return (
    <article className="welcome" aria-labelledby="welcome-heading">
      <p className="eyebrow">NASA Earth science · Trend detective</p>
      <h2 id="welcome-heading">The same planet changes differently from place to place.</h2>
      <p className="welcome-lede">
        The engine compares {catalog.regions.length} Regions across {catalog.variables.length}{' '}
        Variables measured by NASA missions and models, and looks for places changing in ways
        that contrast. Pick how you want to start.
      </p>
      <div className="experiences">
        <button className="experience" onClick={onSurprise} disabled={checkingDiscovery}>
          <span className="experience-title">Surprise Me!</span>
          <span className="experience-text">
            The engine picks a contrast it found in the data and shows you where.
          </span>
        </button>
        <button className="experience experience-quiet" onClick={onDetective} disabled={checkingDiscovery} aria-busy={checkingDiscovery} aria-describedby={detectiveError ? 'detective-error' : undefined}>
          <span className="experience-title">Become a Detective</span>
          <span className="experience-text">
            Make a guess first, then check it against the evidence.
          </span>
        </button>
        {detectiveError && <p id="detective-error" className="error" role="alert">{detectiveError.message}</p>}
      </div>
    </article>
  )
}

export function Drawing() {
  return (
    <div className="drawing" role="status" aria-live="polite">
      <p className="eyebrow">Searching the planet</p>
      <p className="drawing-text">Picking a Discovery you have not seen yet…</p>
      <div className="skeleton skeleton-title" aria-hidden="true" />
      <div className="skeleton skeleton-line" aria-hidden="true" />
      <div className="skeleton skeleton-card" aria-hidden="true" />
      <div className="skeleton skeleton-card" aria-hidden="true" />
    </div>
  )
}

export function SessionComplete({ seen, onNewSession }) {
  return (
    <article className="session-complete" aria-labelledby="complete-heading">
      <p className="eyebrow">Session complete</p>
      <h2 id="complete-heading">You have seen every Discovery the engine has for now.</h2>
      <p>
        {seen === 1 ? 'One Discovery' : `${seen} Discoveries`} in this session, and the engine
        never showed you the same one twice. Start again to see them in a new order.
      </p>
      <div className="panel-actions">
        <button className="primary" onClick={onNewSession}>
          Start a new session
        </button>
      </div>
    </article>
  )
}

export function Unreachable({ onRetry }) {
  return (
    <article className="unreachable" role="alert">
      <p className="eyebrow">No connection</p>
      <h2>The Discovery engine is not answering.</h2>
      <p>Check that the API is running, then try again.</p>
      <div className="panel-actions">
        <button className="primary" onClick={onRetry}>
          Try again
        </button>
      </div>
    </article>
  )
}
