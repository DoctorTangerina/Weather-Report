import test from 'node:test'
import assert from 'node:assert/strict'
import { rectangleCentre, splitRectangle } from './areaGeometry.js'

test('antimeridian rectangles render on either side without changing their latitude', () => {
  const box = { west: 170, east: -170, south: -10, north: 20 }
  assert.deepEqual(splitRectangle(box), [{ west: 170, east: 180, south: -10, north: 20 }, { west: -180, east: -170, south: -10, north: 20 }])
  assert.deepEqual(rectangleCentre(box), { lat: 5, lng: -180 })
  assert.deepEqual(box, { west: 170, east: -170, south: -10, north: 20 })
})

test('ordinary rectangles keep their bounds and centre', () => {
  const box = { west: -70, east: -50, south: -10, north: 2 }
  assert.deepEqual(splitRectangle(box), [box])
  assert.deepEqual(rectangleCentre(box), { lat: -4, lng: -60 })
})
