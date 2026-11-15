import { useEffect, useMemo, useRef, useState } from 'react'
import DiscoveryPanel from '../components/DiscoveryPanel.jsx'
import ExploreMyWorld, { ExploreEntry } from '../components/ExploreMyWorld.jsx'
import Explorer from '../components/Explorer.jsx'
import RegionGlobe from '../components/Globe.jsx'
import { Drawing, SessionComplete, Unreachable, Welcome } from '../components/PanelStates.jsx'
import SelectedAreaPanel from '../components/SelectedAreaPanel.jsx'
import Timeline from '../components/Timeline.jsx'
import { AREA_COLOR, REGION_COLORS } from '../palette.js'
import { describeArea } from '../selectedArea.js'
import useAvailableSeries from '../useAvailableSeries.js'
import useComparison from '../useComparison.js'
import useExploreView from '../useExploreView.js'
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
  seen,
  onSurprise,
  onDetective,
  onInvestigate,
  onBack,
  onNewSession,
  onRetry,
  exploreRegionId,
  onExplore,
  onCloseExplore,
}) {
  const [timestamp, setTimestamp] = useState(null)
  const [regionId, setRegionId] = useState('')
  const [secondRegionId, setSecondRegionId] = useState('')
  const [variableId, setVariableId] = useState('')
  const [investigationStep, setInvestigationStep] = useState(0)
  // At most one Selected area, kept only in memory: a reload clears it (#79).
  const [selectedArea, setSelectedArea] = useState(null)
  const [drawingArea, setDrawingArea] = useState(false)
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
  const globeHighlights =
    showing || investigating ? displayedHighlights : exploredRegion ? exploreHighlights : explored
  // Catalog Regions are clickable where a student is choosing what to look at.
  const pickable = exploring || exploringPlace
  useEffect(() => {
    if (phase !== 'drawing') previousHighlights.current = globeHighlights
  }, [phase, globeHighlights])
  // Notices for a Discovery's series are shown beside each chart (SeriesResults),
  // so only the Explorer's notice goes in the banner.
  const banner = notice ?? (exploring ? seriesNotice : null)
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

  const areaPanel = (
    <SelectedAreaPanel
      area={selectedArea}
      drawing={drawingArea}
      onDraw={() => setDrawingArea(true)}
      onStopDrawing={() => setDrawingArea(false)}
      onArea={(rectangle) => setSelectedArea([rectangle])}
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
          highlights={phase === 'drawing' ? previousHighlights.current : globeHighlights}
          regions={pickable ? catalog.regions : undefined}
          onRegionClick={pickable ? onExplore : undefined}
          selectedArea={pickable ? selectedArea : null}
          onAreaClick={pickable ? () => onExplore(null) : undefined}
          drawing={pickable && drawingArea}
          onDrawn={(rectangle) => {
            setSelectedArea([rectangle])
            setDrawingArea(false)
          }}
          onDrawCancel={() => setDrawingArea(false)}
        />
        <p className="globe-hint">
          {pickable && drawingArea
            ? 'Drag from one corner to the opposite corner · Escape to stop'
            : `${pickable ? 'Click a Region to explore it · ' : ''}Drag to turn · Scroll or pinch to zoom`}
        </p>
      </section>

      <aside
        className="sidebar"
        tabIndex={0}
        aria-label={investigating ? 'Become a Detective' : undefined}
        aria-busy={phase === 'loading' || phase === 'drawing' || seriesLoading || exploreView.loading}
      >
        {banner && (
          <p className="notice" role="status">
            {banner.message}
          </p>
        )}
        {error && (
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
              onSurprise={onSurprise}
              onDetective={() => onDetective([region, secondRegion].filter(Boolean).map((item) => item.region_id))}
            />
            <ExploreEntry catalog={catalog} onExplore={onExplore}>
              {areaPanel}
            </ExploreEntry>
            <Explorer
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
          />
        )}
      </aside>

      {(showing || exploring || investigating || exploringPlace || phase === 'drawing') && (
        <Timeline
          key={timelineKey}
          series={timelineSeries}
          loading={exploringPlace ? exploreView.loading : seriesLoading}
          onTimestampChange={setTimestamp}
        />
      )}
    </div>
  )
}
