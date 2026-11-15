import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  DEFAULT_TIME_STEP,
  TIME_STEPS,
  describeLimits,
  monthAt,
  periodLimitProblem,
  stepRange,
} from './timeSteps.js'

// The API's /api/explore/options `time_steps` (#80).
const OPTIONS = [
  { time_step: '3-hourly', variable_ids: ['temperature'], max_months: 12, limit: '1 year' },
  { time_step: 'daily', variable_ids: ['temperature'], max_months: 120, limit: '10 years' },
  { time_step: 'monthly', variable_ids: ['temperature', 'vegetation-index'], max_months: null, limit: null },
]

test('the three Time steps of spec #72 are offered, defaulting to monthly', () => {
  assert.deepEqual(TIME_STEPS.map((item) => item.id), ['3-hourly', 'daily', 'monthly'])
  assert.equal(DEFAULT_TIME_STEP, 'monthly')
})

test('the caps are explained from the API options', () => {
  assert.equal(
    describeLimits(OPTIONS),
    '3-hourly periods are limited to 1 year and daily periods to 10 years.',
  )
  assert.equal(describeLimits(null), null)
})

test('a period longer than the cap of its Time step is a problem; one at the cap is not', () => {
  assert.equal(periodLimitProblem(OPTIONS, '3-hourly', '2010-01', '2010-12'), null)
  assert.equal(
    periodLimitProblem(OPTIONS, '3-hourly', '2010-01', '2011-01'),
    '3-hourly periods are limited to 1 year.',
  )
  assert.equal(periodLimitProblem(OPTIONS, 'daily', '2001-01', '2010-12'), null)
  assert.equal(
    periodLimitProblem(OPTIONS, 'daily', '2000-12', '2010-12'),
    'Daily periods are limited to 10 years.',
  )
  assert.equal(periodLimitProblem(OPTIONS, 'monthly', '2000-01', '2024-12'), null)
})

test('each value falls in its UTC month, whatever the Time step', () => {
  const period = { start: '2010-01', end: '2010-02' }
  const january = 2010 * 12
  assert.equal(monthAt(period, 'monthly', 1), january + 1)
  assert.equal(monthAt(period, 'daily', 30), january)
  assert.equal(monthAt(period, 'daily', 31), january + 1)
  assert.equal(monthAt(period, '3-hourly', 31 * 8 - 1), january)
  assert.equal(monthAt(period, '3-hourly', 31 * 8), january + 1)
})

test('the range names the first and last Time step, in UTC below a month', () => {
  assert.equal(stepRange({ start: '2010-01', end: '2010-12' }, 'monthly', 12), '2010-01 to 2010-12')
  assert.equal(stepRange({ start: '2010-01', end: '2010-01' }, 'daily', 31), '2010-01-01 to 2010-01-31 UTC')
  assert.equal(
    stepRange({ start: '2010-01', end: '2010-01' }, '3-hourly', 248),
    '2010-01-01 00:00 to 2010-01-31 21:00 UTC',
  )
})
