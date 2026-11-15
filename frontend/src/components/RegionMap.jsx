import RegionGlobe from './Globe.jsx'

export default function RegionMap({ regions }) {
  return (
    <figure className="region-map">
      <div className="discovery-globe" role="group" aria-label={`Map highlighting ${regions.map((region) => region.name).join(' and ')}`}>
        <RegionGlobe regions={regions} />
      </div>
      <figcaption>
        <p className="muted">Drag to explore · Scroll or pinch to zoom. Highlights show the Region boundaries from the catalog.</p>
        <ol className="region-legend">
          {regions.map((region) => (
            <li key={region.region_id}>
              <strong>{region.name}</strong>
              <p>{region.description}</p>
            </li>
          ))}
        </ol>
      </figcaption>
    </figure>
  )
}
