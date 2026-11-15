// Selected areas (#79): rectangles as [west, south, east, north] in degrees. A
// rectangle whose west edge lies east of its east edge crosses the antimeridian.

const round = (value) => Math.round(value * 100) / 100
const wrap = (lng) => ((((lng + 180) % 360) + 360) % 360) - 180

// The rectangle between two dragged corners. It takes the shorter way round in
// longitude, so dragging from 170°E to 170°W crosses the antimeridian instead of
// wrapping 340° the other way. Null when the corners do not span an area.
export function rectangleFromCorners(start, end) {
  const delta = wrap(end.lng - start.lng)
  const [west, east] = delta >= 0 ? [start.lng, end.lng] : [end.lng, start.lng]
  const rectangle = [
    round(wrap(west)),
    round(Math.min(start.lat, end.lat)),
    round(wrap(east)),
    round(Math.max(start.lat, end.lat)),
  ]
  // A drag with no width or height is a click, not a rectangle.
  if (rectangle[0] === rectangle[2] || rectangle[1] === rectangle[3]) return null
  return rectangle
}

// The same rectangle with east >= west, for drawing it continuously.
export function unwrapped([west, south, east, north]) {
  return [west, south, east > west ? east : east + 360, north]
}

// What the West, South, East and North fields describe, or the reason they do not.
export function rectangleFromBounds(bounds) {
  const values = ['west', 'south', 'east', 'north'].map((key) => Number(bounds[key]))
  if (['west', 'south', 'east', 'north'].some((key) => String(bounds[key]).trim() === '')
    || values.some((value) => !Number.isFinite(value))) {
    return { error: 'Give all four edges in degrees.' }
  }
  const [west, south, east, north] = values
  if (Math.abs(west) > 180 || Math.abs(east) > 180 || west === east) {
    return { error: 'West and east run from -180 to 180 and must differ.' }
  }
  if (Math.abs(south) > 90 || Math.abs(north) > 90 || south >= north) {
    return { error: 'South and north run from -90 to 90, with south below north.' }
  }
  return { rectangle: values }
}

const latitude = (value) => `${Math.abs(value)}°${value < 0 ? 'S' : value > 0 ? 'N' : ''}`
const longitude = (value) =>
  `${Math.abs(value)}°${value < 0 ? 'W' : value > 0 && value < 180 ? 'E' : ''}`

export function describeRectangle([west, south, east, north]) {
  return `${latitude(south)} to ${latitude(north)}, ${longitude(west)} to ${longitude(east)}`
}

export function describeArea(rectangles) {
  return rectangles.map(describeRectangle).join('; ')
}
