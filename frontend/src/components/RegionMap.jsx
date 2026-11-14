const WIDTH = 520
const HEIGHT = 260

// Placeholder for the real map, which is ticket #14: an equirectangular box
// with each Region's bounding box drawn on it.
const x = (longitude) => ((longitude + 180) / 360) * WIDTH
const y = (latitude) => ((90 - latitude) / 180) * HEIGHT

export default function RegionMap({ regions }) {
  return (
    <svg className="map" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Regions compared">
      <rect className="map-ground" x="0" y="0" width={WIDTH} height={HEIGHT} />
      <line x1="0" y1={y(0)} x2={WIDTH} y2={y(0)} className="map-equator" />
      {regions.map((region) => (
        <g key={region.region_id}>
          <rect
            className="map-region"
            x={x(region.bbox.west)}
            y={y(region.bbox.north)}
            width={Math.max(x(region.bbox.east) - x(region.bbox.west), 3)}
            height={Math.max(y(region.bbox.south) - y(region.bbox.north), 3)}
          />
          <text x={x(region.bbox.west)} y={y(region.bbox.north) - 4}>
            {region.name}
          </text>
        </g>
      ))}
    </svg>
  )
}
