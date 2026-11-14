export default function ExperienceScreen({ catalog, onSurprise, onBrowse, busy, error }) {
  return (
    <section>
      <h1>Earth System Trend Detective</h1>
      <p>
        The engine reads NASA Earth science series and looks for places that are changing in
        opposite directions. Pick where to start.
      </p>

      <div className="actions">
        <button onClick={onSurprise} disabled={busy}>
          {busy ? 'Looking for a Discovery…' : 'Surprise Me!'}
        </button>
        <button className="secondary" onClick={onBrowse} disabled={busy}>
          Become a Detective
        </button>
      </div>

      {error && <p className="error">{error.message}</p>}

      {catalog && (
        <p className="muted">
          {catalog.regions.length} Regions and {catalog.variables.length} Variables in the catalog.
        </p>
      )}
    </section>
  )
}
