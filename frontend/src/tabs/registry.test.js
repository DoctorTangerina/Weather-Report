import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_TAB, TABS, tabFromHash } from './registry.js'

test('tab ids are unique and usable as a URL hash', () => {
  const ids = TABS.map((tab) => tab.id)
  assert.equal(new Set(ids).size, ids.length)
  for (const id of ids) assert.match(id, /^[a-z][a-z-]*$/)
})

test('every tab has all of its fields', () => {
  for (const tab of TABS) {
    for (const field of ['id', 'label', 'description', 'icon']) {
      assert.equal(typeof tab[field], 'string', `${tab.id}.${field}`)
      assert.ok(tab[field].trim().length > 0, `${tab.id}.${field}`)
    }
    assert.ok(tab.Component, `${tab.id}.Component`)
  }
})

test('the tabs are the five of #114, in order, starting with Start', () => {
  assert.deepEqual(TABS.map((tab) => tab.id), ['start', 'surprise', 'detective', 'explore', 'compare'])
  assert.equal(DEFAULT_TAB, 'start')
})

test('a URL hash opens its tab; a missing or unknown one opens Start', () => {
  assert.equal(tabFromHash('#explore'), 'explore')
  assert.equal(tabFromHash('compare'), 'compare')
  assert.equal(tabFromHash(''), 'start')
  assert.equal(tabFromHash('#nope'), 'start')
  assert.equal(tabFromHash(undefined), 'start')
})
