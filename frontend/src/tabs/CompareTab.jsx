import { useMemo, useState } from 'react'
import Explorer from '../components/Explorer.jsx'
import { REGION_COLORS } from '../palette.js'
import useComparison from '../useComparison.js'
import { useShell, useTabDeclaration, useTabTimeline } from './shell.js'

const NONE = []

// Two Regions side by side on one Variable, with their Trends and series.
export default function CompareTab() {
  const { catalog, available } = useShell()
  const { timestamp, timeRange } = useTabTimeline()
  const [regionId, setRegionId] = useState('')
  const [secondRegionId, setSecondRegionId] = useState('')
  const [variableId, setVariableId] = useState('')

  const region = catalog.regions.find((item) => item.region_id === regionId)
  const secondRegion = catalog.regions
    .filter((item) => item.region_id !== region?.region_id)
    .find((item) => item.region_id === secondRegionId)
  const variables = catalog.variables.filter(
    (item) =>
      region?.variable_ids.includes(item.variable_id) &&
      secondRegion?.variable_ids.includes(item.variable_id),
  )
  const variable = variables.find((item) => item.variable_id === variableId) ?? variables[0]

  // Wait for availability and an explicit pair before requesting a comparison.
  const comparison = useComparison(
    available.settled ? region?.region_id : null,
    available.settled ? secondRegion?.region_id : null,
    available.settled ? variable?.variable_id : null,
  )
  const highlights = useMemo(
    () => [region, secondRegion]
      .filter(Boolean)
      .map((item, index) => ({ region: item, color: REGION_COLORS[index] })),
    [region, secondRegion],
  )
  // A Region clicked on the globe fills the next empty slot.
  const choose = (id) => {
    if (!regionId) setRegionId(id)
    else if (id !== regionId) setSecondRegionId(id)
  }
  useTabDeclaration({
    globe: { highlights, onRegionClick: choose, hint: 'Click a Region to choose it' },
    timeline: {
      kind: 'series',
      key: `${region?.region_id}/${secondRegion?.region_id}/${variable?.variable_id}`,
      series: comparison.loading ? NONE : comparison.series,
      loading: comparison.loading,
    },
  })

  return (
    <>
      {comparison.notice && <p className="notice" role="status">{comparison.notice.message}</p>}
      <Explorer
        catalog={catalog}
        region={region}
        secondRegion={secondRegion}
        variable={variable}
        variables={variables}
        onRegion={setRegionId}
        onSecondRegion={setSecondRegionId}
        onVariable={setVariableId}
        hasData={available.has}
        series={comparison.series}
        seriesLoading={comparison.loading}
        error={comparison.error}
        timestamp={timestamp}
        timeRange={timeRange}
        highlights={highlights}
        trends={comparison.trends}
      />
    </>
  )
}
