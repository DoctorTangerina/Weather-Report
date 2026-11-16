import { createContext, useContext, useLayoutEffect, useSyncExternalStore } from 'react'

// The tab context contract (#114). The shell provides each tab the catalog, the
// shared session, the Selected area and a way to open another tab. A tab
// publishes what it wants on the globe and the timeline with useTabDeclaration;
// the shell draws only the active tab's declaration. Declarations go through a
// store, not React state, so a tab re-rendering never re-renders the others.

export const ShellContext = createContext(null)
export const TabIdContext = createContext(null)

const NO_TIMELINE = { timestamp: null, timeRange: null }

// Shallow, one level into `globe` and `timeline`. Functions match on presence
// only: the hosts call the latest one, so their identity never matters.
function sameFields(a, b) {
  const same = (x, y) => (typeof x === 'function' || typeof y === 'function'
    ? typeof x === typeof y
    : Object.is(x, y))
  for (const part of new Set([...Object.keys(a ?? {}), ...Object.keys(b ?? {})])) {
    const left = a?.[part]
    const right = b?.[part]
    if (left && right && typeof left === 'object' && typeof right === 'object' && !Array.isArray(left)) {
      for (const key of new Set([...Object.keys(left), ...Object.keys(right)])) {
        if (!same(left[key], right[key])) return false
      }
    } else if (!same(left, right)) {
      return false
    }
  }
  return true
}

// Per-tab values with subscribers. `get` returns a stable snapshot that changes
// only when its fields do; `latest` is the most recent value, for callbacks.
export function createTabStore() {
  const snapshots = new Map()
  const latest = new Map()
  const listeners = new Set()
  return {
    get: (id) => snapshots.get(id),
    latest: (id) => latest.get(id),
    set(id, value) {
      latest.set(id, value)
      if (snapshots.has(id) && sameFields(snapshots.get(id), value)) return
      snapshots.set(id, value)
      listeners.forEach((listener) => listener())
    },
    merge(id, patch) {
      this.set(id, { ...(latest.get(id) ?? {}), ...patch })
    },
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
}

export function useShell() {
  return useContext(ShellContext)
}

export function useTabId() {
  return useContext(TabIdContext)
}

// What this tab wants on the globe and timeline while it is the active tab:
//   globe: { highlights, fieldMap, onRegionClick, onAreaClick, editsArea, hint }
//   timeline: null | { kind: 'series', key, series, loading }
//                  | { kind: 'explore', key, view, series }
export function useTabDeclaration(declaration) {
  const id = useTabId()
  const { declarations } = useShell()
  useLayoutEffect(() => {
    declarations.set(id, declaration)
  })
}

// The timestamp and range the timeline last reported while this tab was active.
export function useTabTimeline() {
  const id = useTabId()
  const { timelines } = useShell()
  return useSyncExternalStore(timelines.subscribe, () => timelines.get(id)) ?? NO_TIMELINE
}
