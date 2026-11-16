import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  describeArea,
  handles,
  joinRectangle,
  resizeArea,
  resizeRectangle,
  rectangleFromBounds,
  rectangleFromCorners,
  unwrapped,
} from './selectedArea.js'

test('a drag gives the rectangle between its corners, whichever corner came first', () => {
  const expected = [10, -5, 30, 20]
  assert.deepEqual(rectangleFromCorners({ lat: -5, lng: 10 }, { lat: 20, lng: 30 }), expected)
  assert.deepEqual(rectangleFromCorners({ lat: 20, lng: 30 }, { lat: -5, lng: 10 }), expected)
})

test('a drag from 170°E to 170°W crosses the antimeridian the short way', () => {
  const rectangle = rectangleFromCorners({ lat: -10, lng: 170 }, { lat: 10, lng: -170 })
  assert.deepEqual(rectangle, [170, -10, -170, 10])
  assert.deepEqual(unwrapped(rectangle), [170, -10, 190, 10])
})

test('a click without width or height is not a rectangle', () => {
  assert.equal(rectangleFromCorners({ lat: 5, lng: 5 }, { lat: 5, lng: 9 }), null)
  assert.equal(rectangleFromCorners({ lat: 5, lng: 5 }, { lat: 9, lng: 5 }), null)
})

test('typed edges become a rectangle or say what is wrong', () => {
  assert.deepEqual(
    rectangleFromBounds({ west: '170', south: '-10', east: '-170', north: '10' }),
    { rectangle: [170, -10, -170, 10] },
  )
  assert.match(rectangleFromBounds({ west: '', south: '0', east: '1', north: '2' }).error, /all four/)
  assert.match(rectangleFromBounds({ west: '0', south: '5', east: '1', north: '2' }).error, /south below north/)
  assert.match(rectangleFromBounds({ west: '200', south: '0', east: '1', north: '2' }).error, /-180 to 180/)
})

test('an area is described in degrees north, south, east and west', () => {
  assert.equal(describeArea([[170, -10, -170, 10]]), '10°S to 10°N, 170°E to 170°W')
  assert.equal(describeArea([[0, 0, 10, 5]]), '0° to 5°N, 0° to 10°E')
})

// #81: joined rectangles and resize handles.

test('a rectangle that overlaps the Selected area joins it', () => {
  const area = [[0, 0, 20, 10]]
  assert.deepEqual(joinRectangle(area, [10, 5, 30, 15]), { area: [[0, 0, 20, 10], [10, 5, 30, 15]] })
})

test('a rectangle that only touches the Selected area along an edge joins it', () => {
  assert.deepEqual(joinRectangle([[0, 0, 20, 10]], [20, 0, 30, 10]).area?.length, 2)
  assert.deepEqual(joinRectangle([[0, 0, 20, 10]], [0, 10, 20, 15]).area?.length, 2)
})

test('rectangles meeting at the antimeridian touch, where 180° and -180° are one line', () => {
  assert.equal(joinRectangle([[170, -5, 180, 5]], [-180, -5, -170, 5]).area?.length, 2)
  assert.equal(joinRectangle([[170, -5, -170, 5]], [-175, 0, -160, 10]).area?.length, 2)
})

test('a rectangle that neither touches nor overlaps the Selected area is refused', () => {
  const { area, error } = joinRectangle([[0, 0, 20, 10]], [30, 0, 40, 10])
  assert.equal(area, undefined)
  assert.match(error, /must touch or overlap/)
  assert.match(joinRectangle([[0, 0, 20, 10]], [0, 11, 20, 15]).error, /must touch or overlap/)
  // Across 180° from 170°E–170°W, but 20° short of it.
  assert.match(joinRectangle([[170, -5, -170, 5]], [-150, -5, -140, 5]).error, /must touch or overlap/)
})

test('a rectangle may join any rectangle of the area, not only the first', () => {
  const area = [[0, 0, 10, 10], [10, 0, 20, 10]]
  assert.equal(joinRectangle(area, [20, 0, 30, 10]).area?.length, 3)
})

test('every rectangle has a handle at each corner and on each edge', () => {
  const placed = handles([170, -10, -170, 10])
  assert.deepEqual(placed.map(({ handle }) => handle), ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'])
  const at = Object.fromEntries(placed.map(({ handle, lat, lng }) => [handle, [lat, lng]]))
  assert.deepEqual(at.nw, [10, 170])
  assert.deepEqual(at.n, [10, 180])
  assert.deepEqual(at.se, [-10, 190])
  assert.deepEqual(at.w, [0, 170])
})

test('dragging a corner handle moves its two edges and keeps the opposite corner', () => {
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 'ne', { lat: 15, lng: 25 }), [0, 0, 25, 15])
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 'sw', { lat: -5, lng: -3 }), [-3, -5, 20, 10])
})

test('dragging an edge handle moves only that edge', () => {
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 'n', { lat: 12.345, lng: 99 }), [0, 0, 20, 12.35])
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 'w', { lat: 99, lng: -5 }), [-5, 0, 20, 10])
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 's', { lat: -2, lng: 99 }), [0, -2, 20, 10])
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 'e', { lat: 99, lng: 30 }), [0, 0, 30, 10])
})

test('dragging the east edge past 180° makes the rectangle cross the antimeridian', () => {
  assert.deepEqual(resizeRectangle([160, 0, 175, 10], 'e', { lat: 5, lng: -170 }), [160, 0, -170, 10])
  // And back again.
  assert.deepEqual(resizeRectangle([160, 0, -170, 10], 'e', { lat: 5, lng: 170 }), [160, 0, 170, 10])
})

test('a rectangle wider than half the globe keeps its width while an edge moves', () => {
  // The east edge is nearer the new point going on round, not back west.
  assert.deepEqual(resizeRectangle([-100, 0, 120, 10], 'e', { lat: 5, lng: 130 }), [-100, 0, 130, 10])
})

test('dragging an edge across the opposite one flips the rectangle', () => {
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 'n', { lat: -4, lng: 0 }), [0, -4, 20, 0])
  assert.deepEqual(resizeRectangle([0, 0, 20, 10], 'e', { lat: 0, lng: -6 }), [-6, 0, 0, 10])
})

test('a drag that leaves no width or height is not a rectangle', () => {
  assert.equal(resizeRectangle([0, 0, 20, 10], 'n', { lat: 0, lng: 5 }), null)
  assert.equal(resizeRectangle([0, 0, 20, 10], 'w', { lat: 5, lng: 20 }), null)
})

test('resizing a rectangle of the area keeps the others and its place in the area', () => {
  const area = [[0, 0, 10, 10], [10, 0, 20, 10]]
  assert.deepEqual(resizeArea(area, 1, 'e', { lat: 5, lng: 25 }), {
    area: [[0, 0, 10, 10], [10, 0, 25, 10]],
  })
})

test('a resize that would part the area from itself is refused', () => {
  const area = [[0, 0, 10, 10], [10, 0, 20, 10]]
  const { area: resized, error } = resizeArea(area, 1, 'w', { lat: 5, lng: 12 })
  assert.equal(resized, undefined)
  assert.match(error, /must touch or overlap/)
})

test('a resize that leaves no width is refused without a message', () => {
  assert.deepEqual(resizeArea([[0, 0, 10, 10]], 0, 'w', { lat: 5, lng: 10 }), {})
})

test('a resized edge keeps two decimals after wrapping round the globe', () => {
  const decimals = (value) => (String(value).split('.')[1] ?? '').length
  for (const lng of [34.67, -10.53, 179.99, -179.99, 120.31]) {
    for (const handle of ['e', 'w']) {
      const resized = resizeRectangle([-20, 0, 20, 25], handle, { lat: 0, lng })
      if (resized) for (const edge of resized) assert.ok(decimals(edge) <= 2, `${handle} ${lng}: ${resized}`)
    }
  }
  assert.equal(resizeRectangle([-20, 0, 20, 25], 'e', { lat: 0, lng: 34.67 })[2], 34.67)
})
