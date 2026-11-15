import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  describeArea,
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
