import { useMemo, useState } from 'react'
import ExploreMyWorld, { ExploreEntry } from '../components/ExploreMyWorld.jsx'
import FieldMap from '../components/FieldMap.jsx'
import SelectedAreaPanel from '../components/SelectedAreaPanel.jsx'
import { AREA_COLOR, REGION_COLORS } from '../palette.js'
import { describeArea } from '../selectedArea.js'
import useExploreView from '../useExploreView.js'
import useFieldMap from '../useFieldMap.js'
import { useShell, useTabDeclaration, useTabTimeline } from './shell.js'

const NONE = []

// Explore My World (#75-#83): a catalog Region or the Selected area, opened in
// one view. This is the tab that draws and edits the Selected area.
export default function ExploreTab() {
  const { catalog, available, area } = useShell()
  const { timestamp } = useTabTimeline()
  // { regionId } opens a Region; { area: true } opens the Selected area.
  const [target, setTarget] = useState(null)
  const exploredRegion = target?.regionId
    ? catalog.regions.find((item) => item.region_id === target.regionId)
    : null
  const exploredArea = target?.area ? area.selectedArea : null
  const open = (regionId) => setTarget(regionId ? { regionId } : { area: true })

  const view = useExploreView(catalog, exploredRegion, available, exploredArea)
  const field = useFieldMap(
    exploredArea ? { rectangles: exploredArea } : exploredRegion ? { regionId: exploredRegion.region_id } : null,
    view,
  )
  const highlights = useMemo(
    () => (exploredRegion ? [{ region: exploredRegion, color: REGION_COLORS[0] }] : NONE),
    [exploredRegion],
  )
  const series = useMemo(
    () => view.series.filter((item) => item.quality.included),
    [view.series],
  )
  const place = exploredRegion?.region_id ?? (exploredArea ? describeArea(exploredArea) : null)
  useTabDeclaration({
    globe: {
      highlights,
      fieldMap: field.frame,
      onRegionClick: open,
      onAreaClick: () => open(null),
      editsArea: true,
      hint: 'Click a Region to explore it',
    },
    timeline: place ? { kind: 'explore', key: place, view, series } : null,
  })

  const areaPanel = (
    <SelectedAreaPanel
      area={area.selectedArea}
      drawing={area.drawingArea}
      problem={area.areaProblem}
      onDraw={area.startDrawing}
      onStopDrawing={area.stopDrawing}
      onArea={area.placeRectangle}
      onExplore={exploredArea ? undefined : () => open(null)}
    />
  )

  if (!place) {
    return (
      <ExploreEntry catalog={catalog} onExplore={open}>
        {areaPanel}
      </ExploreEntry>
    )
  }
  return (
    <ExploreMyWorld
      catalog={catalog}
      title={exploredRegion?.name ?? 'Selected area'}
      description={
        exploredRegion?.description ??
        `${describeArea(exploredArea)}. It lasts until you reload the page.`
      }
      noun={exploredRegion ? 'Region' : 'area'}
      view={view}
      color={exploredRegion ? REGION_COLORS[0] : AREA_COLOR}
      timestamp={timestamp}
      onBack={() => setTarget(null)}
    >
      <FieldMap field={field} catalog={catalog} />
      {areaPanel}
    </ExploreMyWorld>
  )
}
