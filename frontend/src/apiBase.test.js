import { test } from 'node:test'
import assert from 'node:assert/strict'
import { withBase } from './apiBase.js'

test('without a base the path stays relative, for the dev proxy', () => {
  assert.equal(withBase('', '/api/catalog'), '/api/catalog')
  assert.equal(withBase(undefined, '/api/catalog'), '/api/catalog')
})

test('a deployed API host prefixes every path', () => {
  assert.equal(
    withBase('https://api.example', '/api/explore/jobs/7'),
    'https://api.example/api/explore/jobs/7',
  )
})

test('trailing slashes on the base do not double up', () => {
  assert.equal(withBase('https://api.example//', '/api/catalog'), 'https://api.example/api/catalog')
})
