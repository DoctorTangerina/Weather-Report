import { useEffect, useRef, useState } from 'react'

const NARROW = '(max-width: 760px)'

// The WAI-ARIA tabs pattern: arrow keys move between tabs, Home and End jump to
// the first and last, and Tab moves on into the panel. A vertical rail on wide
// screens, a horizontal scrolling row on narrow ones.
export default function TabBar({ tabs, activeId, onSelect }) {
  const buttons = useRef({})
  const [narrow, setNarrow] = useState(() => window.matchMedia(NARROW).matches)
  useEffect(() => {
    const query = window.matchMedia(NARROW)
    const change = () => setNarrow(query.matches)
    query.addEventListener('change', change)
    return () => query.removeEventListener('change', change)
  }, [])

  const onKeyDown = (event) => {
    const index = tabs.findIndex((tab) => tab.id === activeId)
    const target = {
      ArrowDown: index + 1,
      ArrowRight: index + 1,
      ArrowUp: index - 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: tabs.length - 1,
    }[event.key]
    if (target === undefined) return
    event.preventDefault()
    const tab = tabs[(target + tabs.length) % tabs.length]
    onSelect(tab.id)
    buttons.current[tab.id]?.focus()
  }

  return (
    <div
      className="tab-bar"
      role="tablist"
      aria-label="Tools"
      aria-orientation={narrow ? 'horizontal' : 'vertical'}
      onKeyDown={onKeyDown}
    >
      {tabs.map((tab) => {
        const active = tab.id === activeId
        return (
          <button
            key={tab.id}
            ref={(element) => { buttons.current[tab.id] = element }}
            id={`tab-${tab.id}`}
            className="tab"
            role="tab"
            type="button"
            aria-selected={active}
            aria-controls={`panel-${tab.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onSelect(tab.id)}
          >
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={tab.icon} />
            </svg>
            <span className="tab-label">{tab.label}</span>
          </button>
        )
      })}
    </div>
  )
}
