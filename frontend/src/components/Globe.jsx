import { Component, memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Globe from 'react-globe.gl'
import { fieldColor } from './FieldMap.jsx'
import { AREA_COLOR, withAlpha } from '../palette.js'
import { handles, rectangleFromCorners, resizeArea, unwrapped } from '../selectedArea.js'
import { rectangleCentre } from '../areaGeometry.js'

const FLIGHT_MS = 1600
const polygonSideColor = ({ properties: { kind, color } }) =>
  kind === 'field' ? 'transparent' : withAlpha(color, kind === 'catalog' ? 0.06 : 0.18)
const polygonStrokeColor = ({ properties: { kind, color } }) =>
  kind === 'field' ? 'transparent' : kind === 'catalog' ? withAlpha(color, 0.6) : color
const polygonLabel = ({ properties }) => properties.name
const ringColor = (ring) => (t) => withAlpha(ring.color, Math.max(0, 0.85 - t))
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

class GlobeBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    return this.state.failed ? (
      <p className="globe-fallback" role="status">
        The 3D globe is unavailable. Enable WebGL in your browser to explore it. The
        Discovery data is still available alongside.
      </p>
    ) : (
      this.props.children
    )
  }
}

// A bounding box drawn edge by edge, one degree at a time, so its sides follow
// lines of latitude and longitude on the sphere instead of cutting across them.
//
// Wound clockwise. three-globe triangulates on the sphere with d3-geo, which
// takes the opposite winding to RFC 7946: a counter-clockwise ring is read as
// the whole Earth *except* the box, which tints the globe and swaps the colours.
//
// `east` may exceed 180 so that a box crossing the antimeridian stays continuous.
function boxPolygon([west, south, east, north], properties) {
  const ring = []
  for (let lat = south; lat < north; lat += 1) ring.push([west, lat])
  for (let lng = west; lng < east; lng += 1) ring.push([lng, north])
  for (let lat = north; lat > south; lat -= 1) ring.push([east, lat])
  for (let lng = east; lng > west; lng -= 1) ring.push([lng, south])
  ring.push([west, south])
  return { type: 'Feature', properties, geometry: { type: 'Polygon', coordinates: [ring] } }
}

const bounds = ({ bbox }) => [bbox.west, bbox.south, bbox.east, bbox.north]
// A box whose west edge lies east of its east edge crosses the antimeridian.
const regionPolygon = (region, color, kind) =>
  boxPolygon(unwrapped(bounds(region)), { color, kind, regionId: region.region_id, name: region.name })

function centre({ bbox }) {
  return rectangleCentre(bbox)
}

function toVector({ lat, lng }) {
  const phi = (lat * Math.PI) / 180
  const lambda = (lng * Math.PI) / 180
  return [Math.cos(phi) * Math.cos(lambda), Math.cos(phi) * Math.sin(lambda), Math.sin(phi)]
}

// The camera looks at the midpoint of the great circle between the two Regions,
// from high enough to keep both in view. A portrait viewport sees less from side
// to side, so the camera backs off further there.
function framing(points, aspect) {
  const [a, b] = points.map(toVector)
  const sum = a.map((value, index) => value + b[index])
  const length = Math.hypot(...sum) || 1
  const [x, y, z] = sum.map((value) => value / length)
  const separation = (Math.acos(Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])) * 180) / Math.PI
  return {
    lat: (Math.asin(z) * 180) / Math.PI,
    lng: (Math.atan2(y, x) * 180) / Math.PI,
    altitude: Math.min(3.2, Math.max(1.35, 0.75 + separation / 55) * Math.max(1, 1 / aspect) ** 0.6),
  }
}

function labelElement({ region, color }) {
  const element = document.createElement('div')
  element.setAttribute('aria-hidden', 'true')
  element.className = region.region_id ? 'globe-label' : 'globe-label globe-label-area'
  element.style.setProperty('--region', color)
  element.textContent = region.name
  return element
}

// Catalog Regions are drawn faintly, under any highlight, when `onRegionClick` is
// given: clicking one opens it in Explore My World (#75).
// A Selected area is drawn in its own colour on top; while `drawing`, a drag on
// the globe sketches a new rectangle instead of turning the globe (#79).
// When `onAreaChange` is given, every rectangle of the area has a handle at each
// corner and on each edge. Dragging one resizes that rectangle on the globe, and
// only on release is the area handed back, so a drag asks the API for nothing
// until it ends. A resize that would part the area is held at its last joined
// shape, and the reason comes with the area (#81).
const CATALOG_COLOR = '#cfe3ee'
const NO_REGIONS = []
// Catalog boxes stay faint until hovered; the others are always clearly visible.
const CAP_ALPHA = { highlight: 0.42, area: 0.3, sketch: 0.2 }
const ALTITUDE = { catalog: 0.006, highlight: 0.012, area: 0.016, sketch: 0.018 }
const polygonAltitude = ({ properties: { kind } }) => kind === 'field' ? 0.022 : ALTITUDE[kind]

function RegionGlobe({
  highlights: requestedHighlights = [],
  regions = NO_REGIONS,
  onRegionClick,
  selectedArea = null,
  fieldMap = null,
  onAreaClick,
  drawing = false,
  onDrawn,
  onDrawCancel,
  onAreaChange,
}) {
  // Equivalent highlights can arrive in new arrays as series requests settle.
  // Keep polygons, labels and the camera flight stable across those renders.
  const highlightKey = JSON.stringify(requestedHighlights)
  const highlights = useMemo(() => JSON.parse(highlightKey), [highlightKey])
  const globeRef = useRef(null)
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const [ready, setReady] = useState(false)
  const [hovered, setHovered] = useState(null)
  const [sketch, setSketch] = useState(null)
  // { index, handle, area, problem } while a handle is dragged; `area` is shown.
  const [resizing, setResizing] = useState(null)
  const resizingRef = useRef(null)
  resizingRef.current = resizing
  const shownArea = resizing?.area ?? selectedArea
  const still = highlights.length > 0 || Boolean(selectedArea) || drawing || reducedMotion()

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      const next = { width: Math.floor(width), height: Math.floor(height) }
      setDimensions((current) =>
        current.width === next.width && current.height === next.height ? current : next,
      )
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  const layerCache = useRef(new Map())
  const highlightLayers = useMemo(() => {
    const next = new Map()
    const result = highlights.map((highlight) => {
      const key = JSON.stringify(highlight)
      // Keep an unchanged Region's geometry, label and ring alive when the
      // other Region changes. Replacing them restarts their entrance animation.
      const layer = layerCache.current.get(key) ?? {
        polygon: regionPolygon(highlight.region, highlight.color, 'highlight'),
        label: { ...highlight, lat: highlight.region.bbox.north, lng: centre(highlight.region).lng },
        ring: { ...centre(highlight.region), color: highlight.color },
      }
      next.set(key, layer)
      return layer
    })
    layerCache.current = next
    return result
  }, [highlights])
  // Likewise keep each catalog box's geometry across highlight changes.
  const catalogPolygons = useMemo(
    () => regions.map((region) => regionPolygon(region, CATALOG_COLOR, 'catalog')),
    [regions],
  )

  const sketched = sketch && rectangleFromCorners(...sketch)
  const sketchKey = sketched?.join() ?? ''
  const polygons = useMemo(() => {
    const highlighted = new Set(highlights.map(({ region }) => region.region_id))
    const cells = fieldMap ? fieldMap.cells.flatMap((cell, index) => {
      const value = fieldMap.frames[fieldMap.index][index]
      if (value == null) return []
      return [boxPolygon(cell.bbox, {
        kind: 'field', color: fieldColor(value, fieldMap.minimum, fieldMap.maximum),
        name: `${value} ${fieldMap.units}`,
      })]
    }) : []
    return [
      ...cells,
      ...catalogPolygons.filter(({ properties }) => !highlighted.has(properties.regionId)),
      ...highlightLayers.map((layer) => layer.polygon),
      ...(shownArea ?? []).map((rectangle) =>
        boxPolygon(unwrapped(rectangle), { color: AREA_COLOR, kind: 'area', name: 'Selected area' }),
      ),
      ...(sketchKey
        ? [boxPolygon(unwrapped(sketchKey.split(',').map(Number)), { color: AREA_COLOR, kind: 'sketch' })]
        : []),
    ]
  }, [highlights, highlightLayers, catalogPolygons, selectedArea, sketchKey, fieldMap])
  const resizable = Boolean(onAreaChange) && !drawing
  const labels = useMemo(() => {
    const regionLabels = highlightLayers.map((layer) => layer.label)
    if (!shownArea) return regionLabels
    const [west, , east, north] = unwrapped(shownArea[0])
    const area = { region: { name: 'Selected area' }, color: AREA_COLOR }
    const grips = resizable
      ? shownArea.flatMap((rectangle, index) =>
          handles(rectangle).map((place) => ({ ...place, index, kind: 'handle' })),
        )
      : []
    return [...regionLabels, { ...area, lat: north, lng: (west + east) / 2 }, ...grips]
  }, [highlightLayers, shownArea, resizable])
  const rings = useMemo(
    () => (reducedMotion() ? [] : highlightLayers.map((layer) => layer.ring)),
    [highlightLayers],
  )
  const polygonCapColor = useCallback(
    ({ properties: { kind, color, regionId } }) =>
      fieldMap && kind !== 'field' ? 'transparent' : kind === 'field' ? color : withAlpha(color, CAP_ALPHA[kind] ?? (regionId === hovered ? 0.4 : 0.12)),
    [hovered, fieldMap],
  )

  // A new Selected area may be on the far side, as typed edges often are: face
  // it. Joining a rectangle keeps the first one, so the camera stays; so does
  // resizing, which happens where the user is already looking.
  const resizedTo = useRef('')
  const [facing, setFacing] = useState('')
  useEffect(() => {
    if (!selectedArea) setFacing('')
    else if (JSON.stringify(selectedArea) !== resizedTo.current) {
      setFacing(JSON.stringify(selectedArea[0]))
    }
  }, [selectedArea])
  const areaCentre = useMemo(() => {
    if (!facing) return null
    const [west, south, east, north] = unwrapped(JSON.parse(facing))
    return { lat: (south + north) / 2, lng: (west + east) / 2 }
  }, [facing])

  const aim = useCallback(() => {
    const globe = globeRef.current
    if (!globe || !ready) return
    const controls = globe.controls()
    controls.enableZoom = true
    controls.autoRotateSpeed = 0.45
    controls.autoRotate = !still

    const duration = reducedMotion() ? 0 : FLIGHT_MS
    const aspect = dimensions.width / Math.max(1, dimensions.height)
    // globe.gl ends an in-flight tween at its old destination when a new
    // pointOfView starts. Restore the visible position synchronously first,
    // so selecting another Region redirects the flight without a snap.
    const currentView = globe.pointOfView()
    globe.pointOfView(currentView, 0)
    if (highlights.length === 2) {
      const centres = highlights.map(({ region }) => centre(region))
      globe.pointOfView(framing(centres, aspect), duration)
    } else if (highlights.length === 1) {
      const altitude = 1.9 * Math.max(1, 1 / aspect) ** 0.6
      globe.pointOfView({ ...centre(highlights[0].region), altitude }, duration)
    } else if (areaCentre) {
      globe.pointOfView({ ...areaCentre, altitude: Math.max(2.5, 2.5 / aspect) }, duration)
    } else {
      globe.pointOfView({ lat: 12, altitude: Math.max(2.5, 2.5 / aspect) }, duration)
    }
  }, [highlights, areaCentre, still, ready, dimensions.width, dimensions.height])

  useEffect(() => {
    aim()
  }, [aim])

  // While drawing, a drag sketches a rectangle and Escape stops drawing.
  useEffect(() => {
    const globe = globeRef.current
    if (globe && ready) globe.controls().enabled = !drawing
    if (!drawing) {
      setSketch(null)
      return undefined
    }
    const cancel = (event) => event.key === 'Escape' && onDrawCancel?.()
    window.addEventListener('keydown', cancel)
    return () => window.removeEventListener('keydown', cancel)
  }, [drawing, ready, onDrawCancel])

  // While a handle is dragged the globe holds still, and the pointer is followed
  // anywhere on the page: the handle under it is redrawn as the area changes.
  const dragging = Boolean(resizing)
  useEffect(() => {
    const globe = globeRef.current
    if (!dragging) return undefined
    if (globe) globe.controls().enabled = false
    const move = (event) => {
      const point = pointAt(event)
      const current = resizingRef.current
      if (!point || !current) return
      const { area, error } = resizeArea(current.area, current.index, current.handle, point)
      setResizing({ ...current, area: area ?? current.area, problem: error ?? null })
    }
    const end = () => {
      const current = resizingRef.current
      setResizing(null)
      if (!current) return
      resizedTo.current = JSON.stringify(current.area)
      onAreaChange?.(current.area, current.problem)
    }
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', end)
    window.addEventListener('pointercancel', end)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', end)
      window.removeEventListener('pointercancel', end)
      if (globe) globe.controls().enabled = !drawing
    }
    // Runs once per drag: pointAt reads only refs, and onAreaChange only calls
    // state setters (see the memo below).
  }, [dragging])

  const startResize = useRef(null)
  startResize.current = (index, handle) =>
    selectedArea && setResizing({ index, handle, area: selectedArea, problem: null })
  const htmlElement = useCallback((item) => {
    if (item.kind !== 'handle') return labelElement(item)
    const element = document.createElement('div')
    element.className = `area-handle area-handle-${item.handle}`
    element.dataset.handle = item.handle
    element.dataset.rectangle = String(item.index)
    element.setAttribute('aria-hidden', 'true')
    element.style.setProperty('--region', AREA_COLOR)
    element.addEventListener('pointerdown', (event) => {
      event.preventDefault()
      event.stopPropagation()
      startResize.current?.(item.index, item.handle)
    })
    return element
  }, [])

  const pointAt = (event) => {
    const box = containerRef.current.getBoundingClientRect()
    return globeRef.current?.toGlobeCoords(event.clientX - box.left, event.clientY - box.top)
  }
  const sketchStart = (event) => {
    const point = pointAt(event)
    if (!point) return
    event.currentTarget.setPointerCapture(event.pointerId)
    setSketch([point, point])
  }
  const sketchMove = (event) => {
    const point = sketch && pointAt(event)
    if (point) setSketch([sketch[0], point])
  }
  const sketchEnd = () => {
    if (sketched) onDrawn?.(sketched)
    setSketch(null)
  }

  // Hold the globe still under the pointer, so the Region being aimed at stays put.
  const hover = (feature) => {
    setHovered(feature?.properties.regionId ?? null)
    const globe = globeRef.current
    if (globe) globe.controls().autoRotate = !feature && !still
  }
  const click = ({ properties }) => {
    if (properties.kind === 'area') onAreaClick?.()
    else if (properties.regionId) onRegionClick?.(properties.regionId)
  }
  const clickable = Boolean(onRegionClick || onAreaClick)

  return (
    <div ref={containerRef} className="globe-viewport">
      <GlobeBoundary>
        {dimensions.width > 0 && dimensions.height > 0 && (
          <Globe
            ref={globeRef}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor="#070e1d"
            globeImageUrl="/textures/earth-blue-marble.jpg"
            bumpImageUrl="/textures/earth-topology.png"
            showAtmosphere
            atmosphereColor="#4A90E2"
            atmosphereAltitude={0.18}
            animateIn={false}
            onGlobeReady={() => setReady(true)}
            polygonsData={polygons}
            polygonCapColor={polygonCapColor}
            polygonSideColor={polygonSideColor}
            polygonStrokeColor={polygonStrokeColor}
            polygonAltitude={polygonAltitude}
            polygonLabel={clickable ? polygonLabel : undefined}
            onPolygonHover={clickable ? hover : undefined}
            onPolygonClick={clickable ? click : undefined}
            polygonsTransitionDuration={fieldMap || reducedMotion() ? 0 : 700}
            htmlElementsData={labels}
            htmlElement={htmlElement}
            htmlAltitude={0.02}
            ringsData={rings}
            ringColor={ringColor}
            ringMaxRadius={4.5}
            ringPropagationSpeed={2.2}
            ringRepeatPeriod={1500}
          />
        )}
      </GlobeBoundary>
      {drawing && (
        <div
          className="globe-draw"
          data-testid="globe-draw"
          onPointerDown={sketchStart}
          onPointerMove={sketchMove}
          onPointerUp={sketchEnd}
          onPointerCancel={() => setSketch(null)}
        />
      )}
    </div>
  )
}

// Timeline playback and filtering do not change what the globe shows. Avoid
// restarting globe layer transitions when only the surrounding controls update.
// Callers pass fresh callback closures each render; those only call state
// setters, so the globe compares whether each is given, not its identity.
const CALLBACKS = ['onRegionClick', 'onAreaClick', 'onDrawn', 'onDrawCancel', 'onAreaChange']
const sameJson = (a, b) => JSON.stringify(a) === JSON.stringify(b)
export default memo(RegionGlobe, (previous, next) =>
  sameJson(previous.highlights, next.highlights) &&
  previous.regions === next.regions &&
  previous.fieldMap === next.fieldMap &&
  sameJson(previous.selectedArea, next.selectedArea) &&
  previous.drawing === next.drawing &&
  CALLBACKS.every((name) => Boolean(previous[name]) === Boolean(next[name])),
)
