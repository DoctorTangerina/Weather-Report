import { test } from 'node:test'
import assert from 'node:assert/strict'
import { seriesInRange } from './timeline.js'

const series = { period: { start: '2020-01', end: '2020-05' }, values: [1, 2, null, 4, 5], units: 'K' }

test('range includes both boundary months and preserves missing data', () => {
  const selected = seriesInRange(series, { start: '2020-02', end: '2020-04' })
  assert.deepEqual(selected.values, [2, null, 4])
  assert.deepEqual(selected.period, { start: '2020-02', end: '2020-04' })
  assert.deepEqual(series.values, [1, 2, null, 4, 5])
})

test('range can select one month or extend beyond a Series', () => {
  assert.deepEqual(seriesInRange(series, { start: '2020-04', end: '2020-04' }).values, [4])
  assert.deepEqual(seriesInRange(series, { start: '2019-01', end: '2021-01' }), series)
  assert.deepEqual(seriesInRange(series, { start: '2021-01', end: '2021-02' }).values, [])
  assert.deepEqual(seriesInRange(series, { start: '2019-01', end: '2019-02' }).values, [])
})
