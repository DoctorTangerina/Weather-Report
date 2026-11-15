export class ApiError extends Error {
  constructor(code, message) {
    super(message)
    this.code = code
  }
}

async function request(path, options) {
  const response = await fetch(path, options)
  const body = await response.json()
  if (!response.ok) {
    const error = body?.error ?? {}
    throw new ApiError(error.code ?? 'unknown', error.message ?? response.statusText)
  }
  return body
}

export const getCatalog = () => request('/api/catalog')

export const getDiscoveries = () => request('/api/discoveries')

export const getComparison = (regionA, regionB, variableId) =>
  request(`/api/comparison?${new URLSearchParams({ region_a: regionA, region_b: regionB, variable_id: variableId })}`)

export const getExploreOptions = () => request('/api/explore/options')

export const getExploreJob = (url) => request(url)

export const getAvailableSeries = () => request('/api/series/available')

export const getSeries = (regionId, variableId, period) => {
  const params = new URLSearchParams({ region_id: regionId, variable_id: variableId })
  if (period) {
    params.set('period_start', period.start)
    params.set('period_end', period.end)
  }
  return request(`/api/series?${params}`)
}

// Explore My World: the Series of a catalog Region (`regionId`) or a
// Selected area (`rectangles`): monthly means, returned directly or through a
// background job.
export const getExploreSeries = (place, variableIds, period) => {
  const params = new URLSearchParams({
    aggregation: 'mean',
    time_step: 'monthly',
    period_start: period.start,
    period_end: period.end,
  })
  if (place.regionId) params.set('region_id', place.regionId)
  for (const rectangle of place.rectangles ?? []) params.append('rectangle', rectangle.join(','))
  for (const variableId of variableIds) params.append('variable_id', variableId)
  return request(`/api/explore/series?${params}`)
}

export const surpriseMe = (session) =>
  request('/api/discoveries/surprise', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      shown_discovery_ids: session.shownDiscoveryIds,
      shown_region_ids: session.shownRegionIds,
    }),
  })
