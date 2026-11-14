export default function ExperienceScreen({ catalog, onSurprise, onBrowse, loading, ready, busy, error, notice }) {
  return (
    <section aria-busy={loading || busy}>
      <p className="eyebrow">Explore our changing planet</p>
      <h1>Earth System Trend Detective</h1>
      <p>
        The engine reads NASA Earth science series and looks for Regions with contrasting
        Trends. Pick where to start.
      </p>
      <div className="actions">
        <button onClick={onSurprise} disabled={loading || !catalog || busy || error?.code === 'no_discovery_left_in_session'}>
          {busy ? 'Looking for a Discovery…' : 'Surprise Me!'}
        </button>
        <button className="secondary" onClick={onBrowse} disabled={!ready || busy}>
          Become a Detective
        </button>
      </div>
      <div role="status">
        {loading && <p className="muted">Loading the catalog…</p>}
        {busy && <p className="muted">Looking for a Discovery…</p>}
      </div>
      {notice && <p className="notice" role="status">{notice.message}</p>}
      {error && <p className="error" role="alert">{error.message}</p>}
      {catalog && <p className="muted">{catalog.regions.length} Regions and {catalog.variables.length} Variables in the catalog.</p>}
    </section>
  )
}
