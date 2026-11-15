import { useState } from 'react'
import { describeArea, rectangleFromBounds } from '../selectedArea.js'

const EDGES = [
  ['west', 'West', -180, 180],
  ['south', 'South', -90, 90],
  ['east', 'East', -180, 180],
  ['north', 'North', -90, 90],
]

// Draw one Selected area on the globe (#79), or type its edges. Drawing again
// replaces it; it lasts until the page is reloaded.
export default function SelectedAreaPanel({ area, drawing, onDraw, onStopDrawing, onArea, onExplore }) {
  const [edges, setEdges] = useState({ west: '', south: '', east: '', north: '' })
  const [problem, setProblem] = useState(null)

  const useEdges = (event) => {
    event.preventDefault()
    const { rectangle, error } = rectangleFromBounds(edges)
    setProblem(error ?? null)
    if (rectangle) onArea(rectangle)
  }

  return (
    <section className="area-panel" aria-labelledby="area-panel-heading">
      <h4 id="area-panel-heading">Your own area</h4>
      <p className="muted">
        Draw a rectangle on the globe for a place the Region catalog does not cover. It may cross
        the 180° meridian, and it lasts until you reload the page.
      </p>
      {drawing ? (
        <div className="actions">
          <p className="notice" role="status">
            Drag on the globe from one corner of the area to the opposite corner. Press Escape to
            stop.
          </p>
          <button className="link" onClick={onStopDrawing}>Stop drawing</button>
        </div>
      ) : (
        <button className="ghost" onClick={onDraw}>
          {area ? 'Draw a new area' : 'Draw an area'}
        </button>
      )}
      <details className="area-edges">
        <summary>Or type its edges in degrees</summary>
        <form onSubmit={useEdges}>
          {EDGES.map(([key, label, min, max]) => (
            <label key={key}>
              {label}
              <input
                type="number"
                step="any"
                min={min}
                max={max}
                value={edges[key]}
                onChange={(event) => setEdges({ ...edges, [key]: event.target.value })}
              />
            </label>
          ))}
          <button className="ghost" type="submit">Use these edges</button>
        </form>
        <p className="chart-note">A west edge east of the east edge crosses the 180° meridian.</p>
        {problem && <p className="notice" role="status">{problem}</p>}
      </details>
      {area && (
        <div className="area-summary">
          <p>
            <span className="area-swatch" aria-hidden="true" />
            <strong>Selected area:</strong> {describeArea(area)}
          </p>
          {onExplore && <button className="primary" onClick={onExplore}>Explore this area</button>}
        </div>
      )}
    </section>
  )
}
