import { formatNumber } from '../format.js'

// Shared by the globe and its accessible cell table. Missing values are transparent.
export function fieldColor(value, minimum, maximum) {
  if (value == null) return 'transparent'
  const ratio = maximum === minimum ? 0.5 : (value - minimum) / (maximum - minimum)
  return `hsl(${240 - ratio * 240}, 85%, 55%)`
}

export default function FieldMap({ field, catalog }) {
  const data = field.data
  return (
    <section className="field-map" aria-label="Field map">
      <button className="ghost" onClick={field.toggle}>
        {field.open ? 'Close Field map' : 'Open Field map'}
      </button>
      {field.open && <>
        <label htmlFor="field-variable">Field map Variable</label>
        <select id="field-variable" value={field.variableId ?? ''}
          disabled={field.variableIds.length === 0}
          onChange={(event) => field.setVariableId(event.target.value)}>
          {field.variableIds.map((id) => <option key={id} value={id}>
            {catalog.variables.find((item) => item.variable_id === id)?.name}
          </option>)}
        </select>
        {field.variableIds.length === 0 && (
          <p className="chart-note">None of the chosen Variables has a Field map yet.</p>
        )}
        {field.loading && <div role="status">
          Obtaining the Field map: {field.progress ?? 0}%
          <progress aria-label="Field map acquisition progress" value={field.progress ?? 0} max="100" />
        </div>}
        {field.error && <p role="status">{field.error.message}</p>}
        {data && <>
          <div aria-label="Field map legend" className="field-legend">
            <span className="field-gradient" aria-hidden="true" />
            <span>{data.minimum == null ? 'No valid data' : `${formatNumber(data.minimum)} to ${formatNumber(data.maximum)} ${data.units}`}</span>
            <span className="field-no-data" aria-hidden="true" /> no data
          </div>
          <label htmlFor="field-time">Field map time</label>
          <input id="field-time" type="range" min="0" max={data.timestamps.length - 1} step="1"
            value={field.index} aria-valuetext={data.timestamps[field.index]}
            onChange={(event) => field.setIndex(Number(event.target.value))} />
          <output htmlFor="field-time">{data.timestamps[field.index]}</output>
          <details>
            <summary>Cell values</summary>
            <table>
              <caption>Native grid cells · {data.timestamps[field.index]} · UTC</caption>
              <thead><tr><th>West, south, east, north (°)</th><th>Value</th></tr></thead>
              <tbody>{data.cells.map((cell, index) => {
                const value = data.frames[field.index][index]
                return <tr key={index}>
                  <td>{cell.bbox.map(formatNumber).join(', ')}</td>
                  <td><span className="field-cell-swatch" style={{ background: fieldColor(value, data.minimum, data.maximum) }} />
                    {value == null ? 'no data' : `${formatNumber(value)} ${data.units}`}</td>
                </tr>
              })}</tbody>
            </table>
          </details>
        </>}
      </>}
    </section>
  )
}
