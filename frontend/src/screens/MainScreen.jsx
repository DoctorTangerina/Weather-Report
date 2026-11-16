import { Suspense, useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import ExploreTimeline from '../components/ExploreTimeline.jsx'
import RegionGlobe from '../components/Globe.jsx'
import { Drawing, Unreachable } from '../components/PanelStates.jsx'
import TabBar from '../components/TabBar.jsx'
import Timeline from '../components/Timeline.jsx'
import { joinRectangle } from '../selectedArea.js'
import { TABS, tabFromHash } from '../tabs/registry.js'
import { ShellContext, TabIdContext, createTabStore, useShell } from '../tabs/shell.js'
import useAvailableSeries from '../useAvailableSeries.js'

const NONE = []
const TAB_LIST = TABS.map(({ id, label, description, icon }) => ({ id, label, description, icon }))

// The shell (#114): header, globe, the tab bar and its panels, and the timeline.
// Each tab owns its flow and declares what the globe and timeline show while it
// is active; the shell renders only that. Tabs stay mounted, so their state
// survives switching away and back until the page is reloaded.
export default function MainScreen({ phase, catalog, notice, session, recordDiscovery, resetSession, onRetry }) {
  const [activeId, setActiveId] = useState(() => tabFromHash(window.location.hash))
  const declarations = useRef(createTabStore()).current
  const timelines = useRef(createTabStore()).current
  const available = useAvailableSeries()

  // The hash names the active tab; switching replaces it, so Back skips tabs.
  const openTab = useCallback((id) => {
    const next = tabFromHash(id)
    setActiveId(next)
    window.history.replaceState(null, '', `#${next}`)
  }, [])
  useEffect(() => {
    const follow = () => setActiveId(tabFromHash(window.location.hash))
    window.addEventListener('hashchange', follow)
    return () => window.removeEventListener('hashchange', follow)
  }, [])

  // At most one Selected area, kept only in memory (#79), shown in every tab and
  // edited only where a tab declares editsArea. 'new' replaces it, 'add' joins.
  const [selectedArea, setSelectedArea] = useState(null)
  const [drawingArea, setDrawingArea] = useState(null)
  const [areaProblem, setAreaProblem] = useState(null)
  const area = useMemo(() => ({
    selectedArea,
    drawingArea,
    areaProblem,
    startDrawing: (mode) => {
      setAreaProblem(null)
      setDrawingArea(mode)
    },
    stopDrawing: () => setDrawingArea(null),
    placeRectangle: (rectangle, mode) => {
      const { area: next, error } =
        mode === 'add' && selectedArea ? joinRectangle(selectedArea, rectangle) : { area: [rectangle] }
      if (next) setSelectedArea(next)
      setAreaProblem(error ?? null)
    },
    change: (next, problem) => {
      setSelectedArea(next)
      setAreaProblem(problem ?? null)
    },
  }), [selectedArea, drawingArea, areaProblem])

  const shell = useMemo(() => ({
    catalog,
    available,
    session,
    recordDiscovery,
    resetSession,
    area,
    tabs: TAB_LIST,
    activeId,
    openTab,
    declarations,
    timelines,
  }), [catalog, available, session, recordDiscovery, resetSession, area, activeId, openTab, declarations, timelines])

  const ready = phase === 'ready' && Boolean(catalog)
  const seen = session.shownDiscoveryIds.length
  return (
    <ShellContext.Provider value={shell}>
      <div className="main-screen">
        <header className="main-header">
          <h1 className="brand">
            <span className="brand-mark" aria-hidden="true" />
            Earth System Trend Detective
          </h1>
          {seen > 0 && (
            <p className="session-count" aria-live="polite">
              {seen === 1 ? '1 Discovery seen' : `${seen} Discoveries seen`}
            </p>
          )}
        </header>

        <GlobeHost catalog={ready ? catalog : null} activeId={activeId} />

        <aside className={`sidebar${ready ? ' has-tabs' : ''}`} aria-busy={phase === 'loading'}>
          {phase === 'loading' && <div className="sidebar-content"><Drawing /></div>}
          {phase === 'unreachable' && <div className="sidebar-content"><Unreachable onRetry={onRetry} /></div>}
          {ready && (
            <>
              <TabBar tabs={TAB_LIST} activeId={activeId} onSelect={openTab} />
              <div className="sidebar-content">
                {notice && <p className="notice" role="status">{notice.message}</p>}
                {TABS.map(({ id, Component }) => (
                  <section
                    key={id}
                    id={`panel-${id}`}
                    className="tab-panel"
                    role="tabpanel"
                    aria-labelledby={`tab-${id}`}
                    tabIndex={0}
                    hidden={id !== activeId}
                  >
                    <TabIdContext.Provider value={id}>
                      <Suspense fallback={null}>
                        <Component />
                      </Suspense>
                    </TabIdContext.Provider>
                  </section>
                ))}
              </div>
            </>
          )}
        </aside>

        {ready && <TimelineHost activeId={activeId} />}
      </div>
    </ShellContext.Provider>
  )
}

// The active tab's declaration; it changes only when a declared field does.
function useDeclaration(activeId) {
  const { declarations } = useShell()
  return useSyncExternalStore(declarations.subscribe, () => declarations.get(activeId))
}

// The globe, as the active tab declares it. The Selected area's outline shows
// in every tab; drawing, resizing and opening it only where editsArea is set.
function GlobeHost({ catalog, activeId }) {
  const { area, declarations } = useShell()
  const declaration = useDeclaration(activeId)
  const globe = declaration?.globe ?? {}
  const editable = Boolean(globe.editsArea)
  const clickable = Boolean(globe.onRegionClick) && Boolean(catalog)
  const latest = useCallback(
    (name) => (...args) => declarations.latest(activeId)?.globe?.[name]?.(...args),
    [declarations, activeId],
  )
  const onRegionClick = useMemo(() => (clickable ? latest('onRegionClick') : undefined), [clickable, latest])
  const onAreaClick = useMemo(() => (editable ? latest('onAreaClick') : undefined), [editable, latest])
  const hint = editable && area.drawingArea
    ? 'Drag from one corner to the opposite corner · Escape to stop'
    : `${globe.hint ? `${globe.hint} · ` : ''}${editable && area.selectedArea ? 'Drag a handle to resize · ' : ''}Drag to turn · Scroll or pinch to zoom`
  return (
    <section className="globe-panel" aria-label="Interactive Earth globe">
      <RegionGlobe
        fieldMap={globe.fieldMap ?? null}
        highlights={globe.highlights ?? NONE}
        regions={clickable ? catalog.regions : undefined}
        onRegionClick={onRegionClick}
        selectedArea={area.selectedArea}
        onAreaClick={onAreaClick}
        drawing={editable ? area.drawingArea : null}
        onDrawn={(rectangle) => {
          area.placeRectangle(rectangle, area.drawingArea)
          area.stopDrawing()
        }}
        onDrawCancel={area.stopDrawing}
        onAreaChange={editable ? area.change : undefined}
      />
      <p className="globe-hint">{hint}</p>
    </section>
  )
}

// The timeline, as the active tab declares it; what it reports goes back to
// that tab (useTabTimeline).
function TimelineHost({ activeId }) {
  const { timelines } = useShell()
  const timeline = useDeclaration(activeId)?.timeline
  const report = useMemo(() => ({
    timestamp: (timestamp) => timelines.merge(activeId, { timestamp }),
    range: (timeRange) => timelines.merge(activeId, { timeRange }),
  }), [timelines, activeId])
  if (!timeline) return null
  const key = `${activeId}/${timeline.key}`
  if (timeline.kind === 'explore') {
    return <ExploreTimeline key={key} view={timeline.view} series={timeline.series} onTimestampChange={report.timestamp} />
  }
  return (
    <Timeline
      key={key}
      series={timeline.series}
      loading={timeline.loading}
      onTimestampChange={report.timestamp}
      onRangeChange={report.range}
    />
  )
}
