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

// #81: a Selected area is one shape, so each rectangle must touch or overlap
// another. The API refuses an area that is not (src/api/explore.py), with the
// same rule: edges that meet count, and 180° and -180° are one line.
const TOUCH_HINT = 'Rectangles must touch or overlap the Selected area.'

function touches(a, b) {
  if (Math.max(a[1], b[1]) > Math.min(a[3], b[3])) return false
  const [aWest, , aEast] = unwrapped(a)
  const [bWest, , bEast] = unwrapped(b)
  return [-360, 0, 360].some((turn) => Math.max(aWest, bWest + turn) <= Math.min(aEast, bEast + turn))
}

function isJoined(rectangles) {
  const reached = new Set([0])
  let grew = true
  while (grew) {
    grew = false
    rectangles.forEach((rectangle, index) => {
      if (!reached.has(index) && [...reached].some((other) => touches(rectangle, rectangles[other]))) {
        reached.add(index)
        grew = true
      }
    })
  }
  return reached.size === rectangles.length
}

// The area with `rectangle` added, or the reason it cannot be.
export function joinRectangle(area, rectangle) {
  if (area.some((other) => touches(rectangle, other))) return { area: [...area, rectangle] }
  return { error: `${TOUCH_HINT} Draw the new one against it, or draw a new area.` }
}

// Where a rectangle's resize handles sit: each corner and the middle of each
// edge, clockwise from the north-west corner. Longitudes are unwrapped, like the
// rectangle as drawn, so the handles of one crossing 180° stay on it.
export function handles(rectangle) {
  const [west, south, east, north] = unwrapped(rectangle)
  const lat = (south + north) / 2
  const lng = (west + east) / 2
  return [
    { handle: 'nw', lat: north, lng: west },
    { handle: 'n', lat: north, lng },
    { handle: 'ne', lat: north, lng: east },
    { handle: 'e', lat, lng: east },
    { handle: 'se', lat: south, lng: east },
    { handle: 's', lat: south, lng },
    { handle: 'sw', lat: south, lng: west },
    { handle: 'w', lat, lng: west },
  ]
}

// The longitude `lng` names that lies nearest `reference`, as an edge moves.
const nearest = (lng, reference) => lng + 360 * Math.round((reference - lng) / 360)
// East edges keep 180° as 180°, so a rectangle ending there does not cross it.
const wrapEast = (lng) => (wrap(lng) === -180 ? 180 : wrap(lng))

// The rectangle after its `handle` ('n', 'ne', 'e', … 'nw') is dragged to
// `point`. Only the edges the handle stands on move, each to the point's nearer
// side, so a rectangle can grow across 180° and one wider than half the globe
// keeps its width. Null when no width or height is left.
export function resizeRectangle(rectangle, handle, { lat, lng }) {
  let [west, south, east, north] = unwrapped(rectangle)
  const latitude = round(Math.max(-90, Math.min(90, lat)))
  if (handle.includes('n')) north = latitude
  if (handle.includes('s')) south = latitude
  if (handle.includes('e')) east = round(nearest(lng, east))
  if (handle.includes('w')) west = round(nearest(lng, west))
  const [low, high] = [Math.min(west, east), Math.max(west, east)]
  if (south === north || low === high || high - low >= 360) return null
  // Round after wrapping: the wrap's arithmetic adds float noise (34.67000000000007).
  return [round(wrap(low)), Math.min(south, north), round(wrapEast(high)), Math.max(south, north)]
}

// The area after one of its rectangles is resized; the reason it cannot be if
// that would part it; neither when the drag leaves the rectangle no width.
export function resizeArea(area, index, handle, point) {
  const resized = resizeRectangle(area[index], handle, point)
  if (!resized) return {}
  const next = area.map((rectangle, at) => (at === index ? resized : rectangle))
  if (!isJoined(next)) return { error: `${TOUCH_HINT} A rectangle cannot be resized away from the rest.` }
  return { area: next }
}
