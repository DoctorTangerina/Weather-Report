// Keep antimeridian geometry intact: render its two longitude intervals.
export function splitRectangle(box) {
  if (box.west < box.east) return [box]
  return [
    ...(box.west < 180 ? [{ ...box, east: 180 }] : []),
    ...(box.east > -180 ? [{ ...box, west: -180 }] : []),
  ]
}

export function rectangleCentre({ west, east, south, north }) {
  const longitude = (west + (east < west ? east + 360 : east)) / 2
  return { lat: (south + north) / 2, lng: ((longitude + 180) % 360) - 180 }
}
