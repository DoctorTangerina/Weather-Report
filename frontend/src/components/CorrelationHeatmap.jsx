import { useState } from 'react'

const scoreText = value => Number(value.toFixed(6)).toString()
const validScore = value => typeof value === 'number' && Number.isFinite(value) && value >= -1 && value <= 1

export default function CorrelationHeatmap({ result }) {
  const [selected, setSelected] = useState(null)
  const undefinedPairs = []
  return (
    <div className="correlation-result">
      <p>{result.observation_count} observations · {result.settings.time_step} · {result.settings.timezone}</p>
      <p className="muted">{result.settings.period.start} to {result.settings.period.end}</p>
      <p className="correlation-legend">Scale: −1 to +1</p>
      <div className="correlation-scroll">
        <table className="correlation-matrix" aria-label="Pearson correlation matrix">
          <thead><tr><th scope="col">Variable and area</th>{result.inputs.map(input => <th scope="col" key={input.id}>{input.label}</th>)}</tr></thead>
          <tbody>{result.inputs.map((left, i) => (
            <tr key={left.id}><th scope="row">{left.label}</th>{result.inputs.map((right, j) => {
              const score = result.matrix[i]?.[j]
              if (!validScore(score)) {
                if (i < j) undefinedPairs.push(`${left.label} and ${right.label}: correlation is undefined.`)
                return <td key={right.id} aria-label={`${left.label} and ${right.label}: undefined`}>—</td>
              }
              const filled = result.filled_pair_counts?.[i]?.[j] ?? 0
              return <td key={right.id}><button
                className="correlation-cell"
                style={{ backgroundColor: score >= 0 ? `hsl(202 65% ${97 - score * 55}%)` : `hsl(24 80% ${97 + score * 47}%)`, color: Math.abs(score) > 0.65 ? '#fff' : '#152b3c' }}
                aria-label={`${left.label} and ${right.label}: ${scoreText(score)}`}
                onClick={() => setSelected({ left: left.label, right: right.label, score, filled })}
              >{scoreText(score)}</button></td>
            })}</tr>
          ))}</tbody>
        </table>
      </div>
      {selected && <p role="status" aria-label="Selected comparison">{selected.left} and {selected.right}: {scoreText(selected.score)}{selected.filled > 0 ? ` · ${selected.filled} observations used filled values` : ''}</p>}
      {undefinedPairs.length > 0 && <section aria-label="Undefined correlations"><h4>Undefined correlations</h4><ul>{undefinedPairs.map(text => <li key={text}>{text}</li>)}</ul></section>}
      <details><summary>Sources and processing history</summary>{result.inputs.map(input => <div key={input.id}><h4>{input.label}</h4><pre>{JSON.stringify(input.metadata, null, 2)}</pre></div>)}</details>
    </div>
  )
}
