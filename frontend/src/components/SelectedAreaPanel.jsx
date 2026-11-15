import { useState } from 'react'
import { describeArea, rectangleFromBounds } from '../selectedArea.js'

const EDGES = [
  ['west', 'West', -180, 180],
  ['south', 'South', -90, 90],
  ['east', 'East', -180, 180],
  ['north', 'North', -90, 90],
]

const DRAWING_HINT = {
  new: 'Drag on the globe from one corner of the area to the opposite corner.',
  add: 'Drag a rectangle that touches or overlaps the Selected area.',
}

// Draw one Selected area on the globe (#79), or type its edges. Drawing a new
// area replaces it; it lasts until the page is reloaded. More rectangles that
// touch or overlap it join it into one shape, and each can be resized by its
// handles on the globe (#81). `problem` says why the last one was not taken.
export default function SelectedAreaPanel({
  area,
  drawing,
  problem,
  onDraw,
  onStopDrawing,
  onArea,
  onExplore,
}) {
  const [edges, setEdges] = useState({ west: '', south: '', east: '', north: '' })
  const [edgesProblem, setEdgesProblem] = useState(null)

  const useEdges = (event) => {
    event.preventDefault()
    const { rectangle, error } = rectangleFromBounds(edges)
    setEdgesProblem(error ?? null)
    // The button pressed says whether the edges start a new area or join it.
    if (rectangle) onArea(rectangle, event.nativeEvent.submitter?.value ?? 'new')
  }

  return (
    <section className="area-panel" aria-labelledby="area-panel-heading">
      <h4 id="area-panel-heading">Your own area</h4>
      <p className="muted">
        Draw a rectangle on the globe for a place the Region catalog does not cover. It may cross
        the 180° meridian, and it lasts until you reload the page. Add rectangles that touch or
        overlap it to make one shape, and drag a corner or edge handle to resize one.
      </p>
      {drawing ? (
        <div className="actions">
          <p className="notice" role="status">
            {DRAWING_HINT[drawing]} Press Escape to stop.
          </p>
          <button className="link" onClick={onStopDrawing}>Stop drawing</button>
        </div>
      ) : (
        <div className="area-actions">
          <button className="ghost" onClick={() => onDraw('new')}>
            {area ? 'Draw a new area' : 'Draw an area'}
          </button>
          {area && (
            <button className="ghost" onClick={() => onDraw('add')}>Add a rectangle</button>
          )}
        </div>
      )}
      {problem && <p className="notice area-problem" role="status">{problem}</p>}
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
          <div className="area-actions">
            <button className="ghost" type="submit" value="new">Use these edges</button>
            {area && (
              <button className="ghost" type="submit" value="add">Add these edges</button>
            )}
          </div>
        </form>
        <p className="chart-note">A west edge east of the east edge crosses the 180° meridian.</p>
        {edgesProblem && <p className="notice" role="status">{edgesProblem}</p>}
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
