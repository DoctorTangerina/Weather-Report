import { useEffect, useMemo, useRef, useState } from 'react'
import DiscoveryPanel from '../components/DiscoveryPanel.jsx'
import ExploreMyWorld, { ExploreEntry } from '../components/ExploreMyWorld.jsx'
import Explorer from '../components/Explorer.jsx'
import CorrelationExplorer from '../components/CorrelationExplorer.jsx'
import FieldMap from '../components/FieldMap.jsx'
import RegionGlobe from '../components/Globe.jsx'
import { Drawing, SessionComplete, Unreachable, Welcome } from '../components/PanelStates.jsx'
import SelectedAreaPanel from '../components/SelectedAreaPanel.jsx'
import Timeline from '../components/Timeline.jsx'
import { AREA_COLOR, REGION_COLORS } from '../palette.js'
import { describeArea, joinRectangle } from '../selectedArea.js'
import useAvailableSeries from '../useAvailableSeries.js'
import useComparison from '../useComparison.js'
import useExploreView from '../useExploreView.js'
import useFieldMap from '../useFieldMap.js'
import useSeries from '../useSeries.js'
import InvestigationScreen from './InvestigationScreen.jsx'

const NONE = []

export default function MainScreen({
  phase,
  catalog,
  discovery,
  highlights,
  notice,
  error,
  checkingDiscovery,
  seen,
  onSurprise,
  onDetective,
  onInvestigate,
  onBack,
  onHome,
  onNewSession,
  onRetry,
  exploreRegionId,
  onExplore,
  onCloseExplore,
}) {
  const [timeRange, setTimeRange] = useState(null)
  const [timestamp, setTimestamp] = useState(null)
  const [mapPoint, setMapPoint] = useState(null)
  const [pickingArea, setPickingArea] = useState(false)
  const [correlationBoxes, setCorrelationBoxes] = useState(null)
  const [regionId, setRegionId] = useState('')
  const [secondRegionId, setSecondRegionId] = useState('')
  const [variableId, setVariableId] = useState('')
  const [investigationStep, setInvestigationStep] = useState(0)
  // At most one Selected area, kept only in memory: a reload clears it (#79).
  const [selectedArea, setSelectedArea] = useState(null)
  // 'new' replaces the Selected area, 'add' joins a rectangle to it (#81).
  const [drawingArea, setDrawingArea] = useState(null)
  // Why the last rectangle drawn, typed or resized was not taken.
  const [areaProblem, setAreaProblem] = useState(null)
  const previousHighlights = useRef(NONE)

  const exploring = phase === 'welcome' && Boolean(catalog)
  const showing = phase === 'discovery' && Boolean(discovery)
  const investigating = phase === 'investigation' && Boolean(discovery)
  const exploredRegion =
    phase === 'explore' ? catalog?.regions.find((item) => item.region_id === exploreRegionId) : null
  // onExplore(null) opens the Selected area rather than a Region.
  const exploredArea =
    phase === 'explore' && exploreRegionId === null && catalog ? selectedArea : null
  const exploringPlace = Boolean(exploredRegion || exploredArea)

  // Every investigation starts at Predict, however the previous one ended.
  useEffect(() => {
    if (investigating) setInvestigationStep(0)
  }, [investigating, discovery?.discovery_id])

  const available = useAvailableSeries()
  const exploreView = useExploreView(catalog, exploredRegion, available, exploredArea)
  const field = useFieldMap(
    exploredArea ? { rectangles: exploredArea } : exploredRegion ? { regionId: exploredRegion.region_id } : null,
    exploreView,
  )
  const exploreHighlights = useMemo(
    () => (exploredRegion ? [{ region: exploredRegion, color: REGION_COLORS[0] }] : NONE),
    [exploredRegion],
  )
  const exploreSeries = useMemo(
    () => exploreView.series.filter((item) => item.quality.included),
    [exploreView.series],
  )
  const region = catalog?.regions.find((item) => item.region_id === regionId)
  const otherRegions =
    catalog?.regions.filter((item) => item.region_id !== region?.region_id) ?? NONE
  const secondRegion = otherRegions.find((item) => item.region_id === secondRegionId)
  const variables =
    catalog?.variables.filter(
      (item) =>
        region?.variable_ids.includes(item.variable_id) &&
        secondRegion?.variable_ids.includes(item.variable_id),
    ) ?? NONE
  const variable =
    variables.find((item) => item.variable_id === variableId) ??
    variables[0]

  // The investigation charts the Check step's series; the Discovery view charts
  // its lead Contrast. Both pairs come from the engine's narrative.
  const refs = useMemo(() => {
    if (investigating) return discovery.narrative.investigation.steps[1].series
    if (showing) {
      return discovery.contrasts[0].trends.map(({ region_id, variable_id }) => ({
        region_id,
        variable_id,
      }))
    }
    return NONE
  }, [investigating, showing, discovery])

  const explored = useMemo(
    () =>
      exploring
        ? [region, secondRegion]
            .filter(Boolean)
            .map((item, index) => ({ region: item, color: REGION_COLORS[index] }))
        : NONE,
    [exploring, region, secondRegion],
  )

  const discoverySeries = useSeries(
    refs,
    showing || investigating ? discovery.period : undefined,
  )
  // Wait for availability and an explicit pair before requesting a comparison.
  const comparing = exploring && available.settled
  const comparison = useComparison(
    comparing ? region?.region_id : null,
    comparing ? secondRegion?.region_id : null,
    comparing ? variable?.variable_id : null,
  )
  const { loading: seriesLoading, series, notice: seriesNotice, error: seriesError } =
    exploring ? comparison : discoverySeries
  // #13: when the API substitutes stored examples for the requested series, the
  // globe shows the Regions actually charted, not the ones that were asked for.
  const displayedHighlights =
    (showing || investigating) && discoverySeries.substituted
      ? [...new Set(series.map((item) => item.region_id))]
          .map((id, index) => ({
            region: catalog.regions.find((item) => item.region_id === id),
            color: REGION_COLORS[index % REGION_COLORS.length],
          }))
          .filter((item) => item.region)
      : highlights
  const correlationHighlights = correlationBoxes?.map((bbox, index) => ({
    region: { bbox, name: `Selected area ${index + 1}` },
    color: REGION_COLORS[index % REGION_COLORS.length],
  }))
  const globeHighlights = showing || investigating
    ? displayedHighlights
    : exploredRegion ? exploreHighlights : correlationHighlights ?? explored
  // Catalog Regions are clickable where a student is choosing what to look at.
  const pickable = exploring || exploringPlace
  // While the Correlation map panel picks corners on the globe, a click places a
  // corner instead of opening the Region under it.
  const correlationPicking = exploring && pickingArea
  const regionsClickable = pickable && !correlationPicking
  useEffect(() => {
    if (phase !== 'drawing') previousHighlights.current = globeHighlights
  }, [phase, globeHighlights])
  // Notices for a Discovery's series are shown beside each chart (SeriesResults),
  // so only the Explorer's notice goes in the banner.
  const banner = notice ?? (exploring ? seriesNotice : null)
  const detectiveError = exploring && ['result_not_available', 'incomplete_pair'].includes(error?.code)
    ? error
    : null
  const timelineKey = exploringPlace
    ? `explore/${exploredRegion?.region_id ?? describeArea(exploredArea)}/${exploreView.chosen}/${exploreView.start}/${exploreView.end}`
    : discovery && !exploring
      ? `${phase}/${discovery.discovery_id}`
      : `${region?.region_id}/${secondRegion?.region_id}/${variable?.variable_id}`

  // Before the student predicts, nothing may hint at the answer: the timeline
  // stays empty until the Check step shows the charts (BS-006).
  const timelineSeries = exploringPlace
    ? exploreView.loading ? NONE : exploreSeries
    : seriesLoading || (investigating && investigationStep !== 1) ? NONE : series

  // A new rectangle starts a new Selected area, or joins the one there is if it
  // touches or overlaps it. A refused one leaves the area as it was.
  const placeRectangle = (rectangle, mode) => {
    const { area, error } =
      mode === 'add' && selectedArea ? joinRectangle(selectedArea, rectangle) : { area: [rectangle] }
    if (area) setSelectedArea(area)
    setAreaProblem(error ?? null)
  }
  const startDrawing = (mode) => {
    setAreaProblem(null)
    setDrawingArea(mode)
  }

  const areaPanel = (
    <SelectedAreaPanel
      area={selectedArea}
      drawing={drawingArea}
      problem={areaProblem}
      onDraw={startDrawing}
      onStopDrawing={() => setDrawingArea(null)}
      onArea={placeRectangle}
      onExplore={exploredArea ? undefined : () => onExplore(null)}
    />
  )

  return (
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

      <section className="globe-panel" aria-label="Interactive Earth globe">
        <RegionGlobe
          fieldMap={field.frame}
          highlights={phase === 'drawing' ? previousHighlights.current : globeHighlights}
          regions={regionsClickable ? catalog.regions : undefined}
          onRegionClick={regionsClickable ? onExplore : undefined}
          selectedArea={pickable ? selectedArea : null}
          onAreaClick={pickable ? () => onExplore(null) : undefined}
          drawing={pickable ? drawingArea : null}
          onDrawn={(rectangle) => {
            placeRectangle(rectangle, drawingArea)
            setDrawingArea(null)
          }}
          onDrawCancel={() => setDrawingArea(null)}
          onPick={correlationPicking
            ? point => setMapPoint({ ...point, clickId: Date.now() })
            : undefined}
          onAreaChange={
            pickable
              ? (area, problem) => {
                  setSelectedArea(area)
                  setAreaProblem(problem ?? null)
                }
              : undefined
          }
        />
        <p className="globe-hint">
          {pickable && drawingArea
            ? 'Drag from one corner to the opposite corner · Escape to stop'
            : `${pickable ? 'Click a Region to explore it · ' : ''}${
                pickable && selectedArea ? 'Drag a handle to resize · ' : ''
              }Drag to turn · Scroll or pinch to zoom`}
        </p>
      </section>

      <aside
        className="sidebar"
        tabIndex={0}
        aria-label={investigating ? 'Become a Detective' : undefined}
        aria-busy={phase === 'loading' || phase === 'drawing' || seriesLoading || exploreView.loading}
      >
        {catalog && (
          <button
            className="home-button"
            aria-label="Home"
            title="Home — choose Regions"
            disabled={phase === 'drawing' || exploring}
            onClick={onHome}
          >
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9" />
            </svg>
          </button>
        )}
        {banner && (
          <p className="notice" role="status">
            {banner.message}
          </p>
        )}
        {error && !detectiveError && (
          <p className="error" role="alert">
            {error.message}
          </p>
        )}
        {seriesError && showing && (
          <p className="error" role="alert">
            The analysis could not be loaded: {seriesError.message}
          </p>
        )}

        {phase === 'loading' && <Drawing />}
        {phase === 'unreachable' && <Unreachable onRetry={onRetry} />}
        {exploring && (
          <>
            <Welcome
              catalog={catalog}
              detectiveError={detectiveError}
              checkingDiscovery={checkingDiscovery}
              onSurprise={onSurprise}
              onDetective={() => onDetective([region, secondRegion].filter(Boolean).map((item) => item.region_id))}
            />
            <ExploreEntry catalog={catalog} onExplore={onExplore}>
              {areaPanel}
            </ExploreEntry>
            <CorrelationExplorer catalog={catalog} mapPoint={mapPoint} onPicking={setPickingArea} onAreaPreview={setCorrelationBoxes} />
            <Explorer
              disabled={checkingDiscovery}
              catalog={catalog}
              region={region}
              secondRegion={secondRegion}
              variable={variable}
              variables={variables}
              onRegion={setRegionId}
              onSecondRegion={setSecondRegionId}
              onVariable={setVariableId}
              hasData={available.has}
              series={series}
              seriesLoading={seriesLoading}
              error={comparison.error}
              timestamp={timestamp}
              timeRange={timeRange}
              highlights={explored}
              trends={comparison.trends}
            />
          </>
        )}
        {exploringPlace && (
          <ExploreMyWorld
            catalog={catalog}
            title={exploredRegion?.name ?? 'Selected area'}
            description={
              exploredRegion?.description ??
              `${describeArea(exploredArea)}. It lasts until you reload the page.`
            }
            noun={exploredRegion ? 'Region' : 'area'}
            view={exploreView}
            color={exploredRegion ? REGION_COLORS[0] : AREA_COLOR}
            timestamp={timestamp}
            onBack={onCloseExplore}
          >
            <FieldMap field={field} view={exploreView} catalog={catalog} />
            {areaPanel}
          </ExploreMyWorld>
        )}
        {phase === 'drawing' && <Drawing />}
        {phase === 'complete' && <SessionComplete seen={seen} onNewSession={onNewSession} />}
        {showing && (
          <DiscoveryPanel
            discovery={discovery}
            catalog={catalog}
            highlights={displayedHighlights}
            responses={discoverySeries.responses}
            substituted={discoverySeries.substituted}
            seriesError={seriesError}
            series={series}
            seriesLoading={seriesLoading}
            timestamp={timestamp}
            timeRange={timeRange}
            onInvestigate={onInvestigate}
            onSurprise={onSurprise}
          />
        )}
        {investigating && (
          <InvestigationScreen
            key={discovery.discovery_id}
            discovery={discovery}
            catalog={catalog}
            highlights={displayedHighlights}
            onBack={onBack}
            stepIndex={investigationStep}
            onStepChange={setInvestigationStep}
            loading={seriesLoading}
            responses={discoverySeries.responses}
            substituted={discoverySeries.substituted}
            error={seriesError}
            timestamp={timestamp}
            timeRange={timeRange}
          />
        )}
      </aside>

      {(showing || exploring || investigating || exploringPlace || phase === 'drawing') && (
        <Timeline
          key={timelineKey}
          series={timelineSeries}
          loading={exploringPlace ? exploreView.loading : seriesLoading}
          onTimestampChange={setTimestamp}
          onRangeChange={setTimeRange}
        />
      )}
    </div>
  )
}
