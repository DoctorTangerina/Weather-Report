import { Component, useEffect, useRef, useState } from 'react'
import Globe from 'react-globe.gl'

class GlobeBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    return this.state.failed
      ? <p className="globe-fallback" role="status">The 3D globe is unavailable. Enable WebGL in your browser to explore it. The Discovery data is still available alongside.</p>
      : this.props.children
  }
}

export default function RegionGlobe({ regions = [] }) {
  const globeRef = useRef(null)
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setDimensions({ width: Math.floor(width), height: Math.floor(height) })
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  const configureGlobe = () => {
    const globe = globeRef.current
    if (!globe) return
    const controls = globe.controls()
    controls.autoRotate = regions.length === 0 && !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    controls.autoRotateSpeed = 0.5
    controls.enableZoom = true
    const aspect = dimensions.width / dimensions.height
    const centers = regions.map(({ bbox }) => ({
      lat: (bbox.north + bbox.south) / 2,
      lng: (bbox.west + bbox.east) / 2,
    }))
    globe.pointOfView({
      lat: centers.length ? centers.reduce((sum, center) => sum + center.lat, 0) / centers.length : 0,
      lng: centers.length ? centers.reduce((sum, center) => sum + center.lng, 0) / centers.length : 0,
      altitude: Math.max(2.5, 2.5 / aspect),
    }, 0)
  }

  useEffect(() => {
    configureGlobe()
  }, [dimensions.width, dimensions.height, regions])

  const polygons = regions.map((region, index) => ({
    ...region,
    color: index === 0 ? '#8bd9ed' : '#ffb579',
    geometry: {
      type: 'Polygon',
      coordinates: [[
        [region.bbox.west, region.bbox.south],
        [region.bbox.west, region.bbox.north],
        [region.bbox.east, region.bbox.north],
        [region.bbox.east, region.bbox.south],
        [region.bbox.west, region.bbox.south],
      ]],
    },
  }))

  return (
    <div ref={containerRef} className="globe-viewport">
      <GlobeBoundary>
        {dimensions.width > 0 && dimensions.height > 0 && (
          <Globe
            ref={globeRef}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor="#070e1d"
            globeImageUrl="https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
            bumpImageUrl="https://unpkg.com/three-globe/example/img/earth-topology.png"
            showAtmosphere
            atmosphereColor="#4A90E2"
            atmosphereAltitude={0.18}
            animateIn={false}
            onGlobeReady={configureGlobe}
            polygonsData={polygons}
            polygonCapColor={(region) => region.color}
            polygonSideColor={() => '#ffffff33'}
            polygonStrokeColor={() => '#ffffff'}
            polygonAltitude={0.012}
            polygonsTransitionDuration={0}
            labelsData={regions}
            labelLat={({ bbox }) => bbox.north + 3}
            labelLng={({ bbox }) => (bbox.west + bbox.east) / 2}
            labelText="name"
            labelColor={() => '#ffffff'}
            labelSize={1.25}
            labelDotRadius={0.35}
            labelResolution={2}
          />
        )}
      </GlobeBoundary>
    </div>
  )
}
