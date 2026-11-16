import { lazy } from 'react'

// The sidebar's tools, in display order (#114). Adding a tool is one component
// plus one entry here: no edits to MainScreen, App or the Start tab. `id` is
// also the URL hash that opens the tab; `icon` is SVG path data on a 24x24 grid.
// Components load lazily so this file stays plain JavaScript (and testable).
export const TABS = [
  {
    id: 'start',
    label: 'Start',
    description: 'What this is, and every tool in one place.',
    icon: 'M3 10.5 12 3l9 7.5M5 9v12h5v-6h4v6h5V9',
    Component: lazy(() => import('./StartTab.jsx')),
  },
  {
    id: 'surprise',
    label: 'Surprise Me!',
    description: 'The engine picks a contrast it found in the data and shows you where.',
    icon: 'M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
    Component: lazy(() => import('./SurpriseTab.jsx')),
  },
  {
    id: 'detective',
    label: 'Become a Detective',
    description: 'Pick two Regions or let the engine pick, guess first, then check the evidence.',
    icon: 'M10.5 4a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13Zm4.6 11.1L21 21',
    Component: lazy(() => import('./DetectiveTab.jsx')),
  },
  {
    id: 'explore',
    label: 'Explore My World',
    description: 'Chart several Variables for any Region or an area you draw, at any Time step.',
    icon: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-9 9h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3Z',
    Component: lazy(() => import('./ExploreTab.jsx')),
  },
  {
    id: 'compare',
    label: 'Compare Regions',
    description: 'Put two Regions side by side on one Variable, with their Trends and series.',
    icon: 'M4 20V10m6 10V4m4 16v-7m6 7V8',
    Component: lazy(() => import('./CompareTab.jsx')),
  },
]

export const DEFAULT_TAB = TABS[0].id

// The tab a URL hash names, or the default for a missing or unknown one.
export function tabFromHash(hash) {
  const id = String(hash ?? '').replace(/^#/, '')
  return TABS.some((tab) => tab.id === id) ? id : DEFAULT_TAB
}
