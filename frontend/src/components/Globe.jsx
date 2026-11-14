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

export default function RegionGlobe() {
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
    controls.autoRotate = !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    controls.autoRotateSpeed = 0.5
    controls.enableZoom = true
    const aspect = dimensions.width / dimensions.height
    globe.pointOfView({ altitude: Math.max(2.5, 2.5 / aspect) }, 0)
  }

  useEffect(() => {
    configureGlobe()
  }, [dimensions.width, dimensions.height])

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
          />
        )}
      </GlobeBoundary>
    </div>
  )
}
