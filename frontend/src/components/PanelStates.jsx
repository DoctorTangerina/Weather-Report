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
