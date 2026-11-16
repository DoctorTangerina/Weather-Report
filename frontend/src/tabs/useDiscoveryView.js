import { useMemo } from 'react'
import { REGION_COLORS } from '../palette.js'
import useSeries from '../useSeries.js'

const NONE = []

// A Discovery's series and globe highlights, shared by Surprise Me! and Become a
// Detective. `mode` is 'discovery' (its lead Contrast), 'investigation' (the
// Check step's series) or null (nothing shown).
export default function useDiscoveryView(catalog, discovery, mode) {
  const refs = useMemo(() => {
    if (!discovery || !mode) return NONE
    if (mode === 'investigation') return discovery.narrative.investigation.steps[1].series
    return discovery.contrasts[0].trends.map(({ region_id, variable_id }) => ({ region_id, variable_id }))
  }, [discovery, mode])
  const series = useSeries(refs, mode && discovery ? discovery.period : undefined)

  const highlights = useMemo(() => {
    if (!discovery || !catalog) return NONE
    return discovery.region_ids
      .map((id, index) => ({
        region: catalog.regions.find((region) => region.region_id === id),
        color: REGION_COLORS[index],
      }))
      .filter((highlight) => highlight.region)
  }, [discovery, catalog])

  // #13: when the API substitutes stored examples for the requested series, the
  // globe shows the Regions actually charted, not the ones that were asked for.
  const shown = useMemo(() => {
    if (!mode || !series.substituted) return highlights
    return [...new Set(series.series.map((item) => item.region_id))]
      .map((id, index) => ({
        region: catalog.regions.find((item) => item.region_id === id),
        color: REGION_COLORS[index % REGION_COLORS.length],
      }))
      .filter((item) => item.region)
  }, [mode, series.substituted, series.series, highlights, catalog])

  return { series, highlights: shown }
}
