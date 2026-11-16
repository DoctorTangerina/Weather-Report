import { useEffect, useRef, useState } from 'react'
import { getCorrelationMap } from '../api.js'
import { describeArea } from '../selectedArea.js'
import CorrelationHeatmap from './CorrelationHeatmap.jsx'
import MissingDataDialog from './MissingDataDialog.jsx'

const AGGREGATIONS = ['mean', 'sum', 'median', 'minimum', 'maximum', 'root mean square', 'standard deviation', 'mean absolute value']
const incomplete = item => item.code === 'incomplete_output_timeline'
const selectionKey = ({ variable, area, source_time_step, aggregation }) => JSON.stringify({ variable, area, source_time_step, aggregation })
// The shared Selected area (#79/#81) keeps rectangles as [west, south, east, north].
const toBounds = ([west, south, east, north]) => ({ west, east, south, north })

// Selected areas come from the shared Selected area: drawn, joined and resized on
// the globe or typed in Your own area, never a separate rectangle tool (#60).
export default function CorrelationExplorer({ catalog, selectedArea, onAreaPreview }) {
  const [areaId, setAreaId] = useState(catalog.regions[0]?.region_id ?? '')
  const [custom, setCustom] = useState(false)
  const [areaName, setAreaName] = useState('Selected area')
  const [chosen, setChosen] = useState([])
  const [inputs, setInputs] = useState([])
  const [derived, setDerived] = useState([])
  const [expression, setExpression] = useState('')
  const [derivedName, setDerivedName] = useState('')
  const [scale, setScale] = useState('expression')
  const [acknowledgeUnits, setAcknowledgeUnits] = useState(false)
  const [start, setStart] = useState('2000-01-01')
  const [end, setEnd] = useState('2024-12-31')
  const [step, setStep] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [result, setResult] = useState(null)
  const [failure, setFailure] = useState(null)
  const [loading, setLoading] = useState(false)
  const [popup, setPopup] = useState(null)
  const [message, setMessage] = useState('')
  const sequence = useRef(0)
  const version = useRef(0)
  const controller = useRef(null)
  const region = catalog.regions.find(item => item.region_id === areaId)
  const variables = custom ? catalog.variables : catalog.variables.filter(item => region?.variable_ids.includes(item.variable_id))

  function clearResult() {
    version.current++
    controller.current?.abort()
    setResult(null)
    setFailure(null)
    setPopup(null)
    setLoading(false)
  }
  useEffect(() => () => controller.current?.abort(), [])
  function addSelections() {
    if (!chosen.length || (custom && !selectedArea?.length)) {
      setMessage(custom && !selectedArea?.length ? 'Draw a Selected area in Your own area first.' : 'Choose an area and at least one Variable.')
      return
    }
    const area = custom ? { name: areaName || 'Selected area', rectangles: selectedArea.map(toBounds) } : areaId
    const areaLabel = custom ? areaName || 'Selected area' : region.name
    const additions = chosen.map(variable => ({ variable, area, label: `${catalog.variables.find(item => item.variable_id === variable).name} — ${areaLabel}`, id: `input_${sequence.current++}` }))
    const seen = new Set(inputs.map(selectionKey))
    const unique = additions.filter(item => { const key = selectionKey(item); if (seen.has(key)) return false; seen.add(key); return true })
    setInputs([...inputs, ...unique])
    clearResult()
    setMessage(unique.length < additions.length ? 'Exact duplicates were omitted.' : 'Inputs added. Choose another area or build the map.')
  }

  function addDerived() {
    if (!inputs.length || !derivedName.trim() || !expression.trim()) { setMessage('Name the calculation and provide its expression or input ID.'); return }
    const id = `derived_${sequence.current++}`
    const operation = scale === 'expression' ? { id: 'result', expression, acknowledge_unit_difference: acknowledgeUnits } : { id: 'result', operation: scale, input: expression.trim(), ...(scale === 'zscore' ? { ddof: 0 } : {}) }
    setDerived([...derived, { id, inputs: Object.fromEntries(inputs.map(item => [item.id, item])), operations: [operation], output: 'result' }])
    setInputs([...inputs, { id, variable: id, area: 'derived', label: derivedName.trim() }])
    clearResult()
    setMessage('Prepared calculation added; its inputs will load when you build the map.')
  }

  async function build(event) {
    event.preventDefault()
    clearResult()
    if (inputs.length < 2 || !start || !end || start > end) { setMessage('Choose at least two inputs and an ordered common period.'); return }
    const current = version.current
    const abort = new AbortController()
    controller.current = abort
    setLoading(true)
    setMessage('')
    try {
      const response = await getCorrelationMap({ variables: inputs, derived, timezone, period: { start, end }, ...(step ? { time_step: step } : {}) }, abort.signal)
      if (version.current !== current) return
      setResult(response.data)
      const gaps = response.data.excluded.filter(incomplete)
      if (gaps.length) setPopup(gaps)
    } catch (error) {
      if (version.current !== current || error.name === 'AbortError') return
      setFailure(error)
      const gaps = (error.details?.excluded ?? []).filter(incomplete)
      if (gaps.length) setPopup(gaps)
    } finally {
      if (version.current === current) setLoading(false)
    }
  }

  const exclusions = result?.excluded ?? failure?.details?.excluded ?? []
  const warnings = result?.warnings ?? failure?.details?.warnings ?? []
  return (
    <section className="explorer correlation-explorer" aria-labelledby="correlation-heading" aria-busy={loading}>
      <h3 id="correlation-heading">Correlation map</h3>
      <p className="muted">Explore My World: choose Variables independently for each area, then compare their series.</p>
      <label><input type="checkbox" checked={custom} onChange={event => { setCustom(event.target.checked); setChosen([]); onAreaPreview?.(event.target.checked ? null : region && [region.bbox]) }} /> Use my Selected area</label>
      {!custom ? <div className="catalog-controls"><label htmlFor="correlation-area">Area with acquired data</label><select id="correlation-area" value={areaId} onChange={event => { setAreaId(event.target.value); setChosen([]); const next = catalog.regions.find(item => item.region_id === event.target.value); onAreaPreview?.([next.bbox]) }}>{catalog.regions.map(item => <option key={item.region_id} value={item.region_id}>{item.name}</option>)}</select></div> : (
        <fieldset><legend>Selected area</legend>
          {selectedArea?.length
            ? <p aria-label="Selected area for correlation"><strong>Rectangles:</strong> {describeArea(selectedArea)}</p>
            : <p className="notice">Draw a Selected area in Your own area above. It can join touching rectangles, be resized by its handles and cross 180°.</p>}
          <label>Area name <input value={areaName} onChange={event => setAreaName(event.target.value)} /></label>
          <p className="muted">Inputs keep the rectangles they were added with; redraw or resize the area, then add Variables again to compare another shape. The area needs acquired coverage.</p>
        </fieldset>
      )}
      <fieldset><legend>Variables for this area</legend>{variables.map(item => <label className="correlation-variable" key={item.variable_id}><input type="checkbox" checked={chosen.includes(item.variable_id)} onChange={event => setChosen(event.target.checked ? [...chosen, item.variable_id] : chosen.filter(value => value !== item.variable_id))} />{item.name}</label>)}</fieldset>
      <button type="button" onClick={addSelections}>Add selected Variables</button>
      <ol aria-label="Correlation inputs" className="correlation-inputs">{inputs.map(item => <li key={item.id}>
        <strong>{item.label}</strong> <code>{item.id}</code>
        <button type="button" aria-label={`Remove ${item.label}`} onClick={() => { setInputs(inputs.filter(value => value.id !== item.id)); clearResult() }}>Remove</button>
        {item.area !== 'derived' && <div className="correlation-input-settings">
          <label>Source Time step for {item.label}<select value={item.source_time_step ?? ''} onChange={event => { const { source_time_step, ...rest } = item; setInputs(inputs.map(value => value.id === item.id ? event.target.value ? { ...rest, source_time_step: event.target.value } : rest : value)); clearResult() }}><option value="">Available native Time step</option>{['hourly', '3-hourly', 'daily', 'monthly'].map(value => <option key={value}>{value}</option>)}</select></label>
          <label>Aggregation for {item.label}<select value={item.aggregation ?? ''} onChange={event => { const { aggregation, ...rest } = item; setInputs(inputs.map(value => value.id === item.id ? event.target.value ? { ...rest, aggregation: event.target.value } : rest : value)); clearResult() }}><option value="">Use Series' own Aggregation</option>{AGGREGATIONS.map(value => <option key={value}>{value}</option>)}</select></label>
        </div>}
      </li>)}</ol>
      <details><summary>Add a prepared calculation</summary>
        <p>Use the input IDs above. Calculations keep their sources and processing history.</p>
        <label>Calculation name <input value={derivedName} onChange={event => setDerivedName(event.target.value)} /></label>
        <label>Calculation type <select value={scale} onChange={event => setScale(event.target.value)}><option value="expression">Arithmetic expression</option><option value="minmax">Min–Max [0, 1]</option><option value="zscore">Z-score (population)</option></select></label>
        <label>Expression or input ID <input value={expression} onChange={event => setExpression(event.target.value)} placeholder="2 * input_0" /></label>
        <label><input type="checkbox" checked={acknowledgeUnits} onChange={event => setAcknowledgeUnits(event.target.checked)} />Continue with different additive units (convert compatible units; otherwise label mixed units)</label>
        <button type="button" onClick={addDerived}>Add prepared calculation</button>
      </details>
      <form onSubmit={build} className="catalog-controls">
        <label htmlFor="correlation-start">Analysis start</label><input id="correlation-start" type="date" required value={start} onChange={event => { setStart(event.target.value); clearResult() }} />
        <label htmlFor="correlation-end">Analysis end</label><input id="correlation-end" type="date" required value={end} onChange={event => { setEnd(event.target.value); clearResult() }} />
        <label htmlFor="correlation-step">Common output Time step</label><select id="correlation-step" value={step} onChange={event => { setStep(event.target.value); clearResult() }}><option value="">Keep matching native Time steps</option>{['3-hourly', 'daily', 'monthly', 'year'].map(value => <option key={value}>{value}</option>)}</select>
        <label htmlFor="correlation-timezone">Aggregation time zone</label><input id="correlation-timezone" value={timezone} required onChange={event => { setTimezone(event.target.value); clearResult() }} />
        <p className="muted">Use UTC for acquired Time-step series. Legacy-frequency data, and prepared calculations resampled in a local time zone, use that zone, such as America/Sao_Paulo. Coarser resampling uses each Series' own Aggregation. No automatic filling or upsampling.</p>
        <button className="primary" type="submit" disabled={loading}>{loading ? 'Building correlation map…' : 'Build correlation map'}</button>
      </form>
      {message && <p role="status">{message}</p>}
      {loading && <p role="status">Loading selected series and calculating correlations…</p>}
      {failure && <p className="error" role="alert">{failure.message}</p>}
      {result && result.inputs.length >= 2 && <CorrelationHeatmap key={JSON.stringify(result.settings) + result.inputs.map(item => item.id).join('/')} result={result} />}
      {warnings.map((item, i) => <p className="notice" role="status" key={i}>{item.message}</p>)}
      {exclusions.length > 0 && <section aria-label="Excluded inputs"><h4>Excluded inputs</h4><ul>{exclusions.map((item, i) => <li key={item.id ?? i}><strong>{item.label ?? item.variable}</strong>: {item.message}</li>)}</ul></section>}
      {popup && <MissingDataDialog inputs={popup} onDismiss={() => setPopup(null)} />}
    </section>
  )
}
