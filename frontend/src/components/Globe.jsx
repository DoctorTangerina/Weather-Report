import { Component, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Globe from 'react-globe.gl'
import { withAlpha } from '../palette.js'

const FLIGHT_MS = 1600
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
function boxPolygon({ region, color }) {
  const { west, east, south, north } = region.bbox
  const ring = []
  for (let lat = south; lat < north; lat += 1) ring.push([west, lat])
  for (let lng = west; lng < east; lng += 1) ring.push([lng, north])
  for (let lat = north; lat > south; lat -= 1) ring.push([east, lat])
  for (let lng = east; lng > west; lng -= 1) ring.push([lng, south])
  ring.push([west, south])
  return {
    type: 'Feature',
    properties: { color },
    geometry: { type: 'Polygon', coordinates: [ring] },
  }
}

function centre({ bbox }) {
  return { lat: (bbox.south + bbox.north) / 2, lng: (bbox.west + bbox.east) / 2 }
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
  element.className = 'globe-label'
  element.style.setProperty('--region', color)
  element.textContent = region.name
  return element
}

export default function RegionGlobe({ highlights: requestedHighlights = [] }) {
  // Equivalent highlights can arrive in new arrays as series requests settle.
  // Keep polygons, labels and the camera flight stable across those renders.
  const highlightKey = JSON.stringify(requestedHighlights)
  const highlights = useMemo(() => JSON.parse(highlightKey), [highlightKey])
  const globeRef = useRef(null)
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const [ready, setReady] = useState(false)

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

  const polygons = useMemo(() => highlights.map(boxPolygon), [highlights])
  const labels = useMemo(
    () =>
      highlights.map((highlight) => ({
        ...highlight,
        lat: highlight.region.bbox.north,
        lng: centre(highlight.region).lng,
      })),
    [highlights],
  )
  const rings = useMemo(
    () =>
      reducedMotion()
        ? []
        : highlights.map((highlight) => ({ ...centre(highlight.region), color: highlight.color })),
    [highlights],
  )

  const aim = useCallback(() => {
    const globe = globeRef.current
    if (!globe || !ready) return
    const controls = globe.controls()
    controls.enableZoom = true
    controls.autoRotateSpeed = 0.45
    controls.autoRotate = highlights.length === 0 && !reducedMotion()

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
    } else {
      globe.pointOfView({ lat: 12, altitude: Math.max(2.5, 2.5 / aspect) }, duration)
    }
  }, [highlights, ready, dimensions.width, dimensions.height])

  useEffect(() => {
    aim()
  }, [aim])

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
            polygonCapColor={(feature) => withAlpha(feature.properties.color, 0.42)}
            polygonSideColor={(feature) => withAlpha(feature.properties.color, 0.18)}
            polygonStrokeColor={(feature) => feature.properties.color}
            polygonAltitude={0.012}
            polygonsTransitionDuration={reducedMotion() ? 0 : 700}
            htmlElementsData={labels}
            htmlElement={labelElement}
            htmlAltitude={0.02}
            ringsData={rings}
            ringColor={(ring) => (t) => withAlpha(ring.color, Math.max(0, 0.85 - t))}
            ringMaxRadius={4.5}
            ringPropagationSpeed={2.2}
            ringRepeatPeriod={1500}
          />
        )}
      </GlobeBoundary>
    </div>
  )
}
