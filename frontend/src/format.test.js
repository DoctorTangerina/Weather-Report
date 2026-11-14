import assert from 'node:assert/strict'
import { test } from 'node:test'
import { formatNumber } from './format.js'

test('rounds half up in decimal, not binary', () => {
  // 7.0625 is exact in binary, so half-even rounding would give 7.062.
  assert.equal(formatNumber(7.0625), '7.063')
  assert.equal(formatNumber(-1.2345), '-1.235')
  assert.equal(formatNumber(2.0005), '2.001')
})

test('drops trailing zeros', () => {
  assert.equal(formatNumber(5.5), '5.5')
  assert.equal(formatNumber(8.625), '8.625')
  assert.equal(formatNumber(3), '3')
  assert.equal(formatNumber(120), '120')
})

test('writes a value that rounds to zero as 0, never -0', () => {
  assert.equal(formatNumber(-0.0004), '0')
  assert.equal(formatNumber(0.0004), '0')
  assert.equal(formatNumber(-0), '0')
  assert.equal(formatNumber(0), '0')
})

test('handles values JavaScript writes in exponent form', () => {
  assert.equal(formatNumber(1e-7), '0')
  assert.equal(formatNumber(0.0005), '0.001')
  assert.equal(formatNumber(1.5e21), '1500000000000000000000')
})
