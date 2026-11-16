import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createTabStore } from './shell.js'

test('a declaration with the same fields does not notify, and keeps its snapshot', () => {
  const store = createTabStore()
  let notified = 0
  store.subscribe(() => { notified += 1 })
  const highlights = []
  store.set('explore', { globe: { highlights, onRegionClick: () => 1 } })
  const snapshot = store.get('explore')
  store.set('explore', { globe: { highlights, onRegionClick: () => 2 } })
  assert.equal(notified, 1)
  assert.equal(store.get('explore'), snapshot)
  assert.equal(store.latest('explore').globe.onRegionClick(), 2)
})

test('a changed field notifies and replaces the snapshot', () => {
  const store = createTabStore()
  let notified = 0
  store.subscribe(() => { notified += 1 })
  store.set('compare', { timeline: { kind: 'series', series: [] } })
  store.set('compare', { timeline: { kind: 'series', series: [1] } })
  store.set('compare', { timeline: null })
  assert.equal(notified, 3)
  assert.equal(store.get('compare').timeline, null)
})

test('merge keeps the other fields', () => {
  const store = createTabStore()
  store.merge('surprise', { timestamp: '2010-01' })
  store.merge('surprise', { timeRange: { start: 0, end: 5 } })
  assert.deepEqual(store.get('surprise'), { timestamp: '2010-01', timeRange: { start: 0, end: 5 } })
})
