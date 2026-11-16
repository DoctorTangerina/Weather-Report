import { test } from 'node:test'
import assert from 'node:assert/strict'
import { AGGREGATIONS, DEFAULT_AGGREGATION, describeAggregation } from './aggregations.js'

// #78: the view's Aggregation control offers exactly the seven Aggregations of
// spec #72, under the API's names, and starts at mean.
test('the seven Aggregations are offered in the spec order, defaulting to mean', () => {
  assert.deepEqual(
    AGGREGATIONS.map((item) => item.id),
    [
      'mean',
      'median',
      'minimum',
      'maximum',
      'root_mean_square',
      'standard_deviation',
      'mean_absolute_value',
    ],
  )
  assert.deepEqual(
    AGGREGATIONS.map((item) => item.label),
    [
      'Mean',
      'Median',
      'Minimum',
      'Maximum',
      'Root mean square',
      'Standard deviation',
      'Mean absolute value',
    ],
  )
  assert.equal(DEFAULT_AGGREGATION, 'mean')
})

test('the note says how cells are combined and which ones count by area', () => {
  assert.match(describeAggregation('mean'), /mean .*weighted by the area of each grid cell/)
  assert.match(describeAggregation('maximum'), /highest value among the grid cells of the area/)
  assert.match(describeAggregation('mean', 'monthly', 'Region'), /mean over the Region, weighted by the area of each grid cell/)
  assert.doesNotMatch(describeAggregation('median', 'daily', 'Region'), /over the area/)
  assert.doesNotMatch(describeAggregation('maximum'), /area of each/)
  assert.match(describeAggregation('standard_deviation'), /population standard deviation/)
  assert.match(describeAggregation('standard_deviation'), /in proportion to its area/)
})
