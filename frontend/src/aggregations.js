// The Aggregations of spec #72, under the API's names. The API combines the
// cells; this only names the choices and says what each one means (#78).
const BY_AREA = 'counting each grid cell in proportion to its area'

export const AGGREGATIONS = [
  // PLACE becomes "the Region" or "the area" (a Selected area) when described.
  { id: 'mean', label: 'Mean', note: 'the mean over PLACE, weighted by the area of each grid cell' },
  { id: 'median', label: 'Median', note: `the median over PLACE, ${BY_AREA}` },
  { id: 'minimum', label: 'Minimum', note: 'the lowest value among the grid cells of PLACE' },
  { id: 'maximum', label: 'Maximum', note: 'the highest value among the grid cells of PLACE' },
  { id: 'root_mean_square', label: 'Root mean square', note: `the root mean square over PLACE, ${BY_AREA}` },
  {
    id: 'standard_deviation',
    label: 'Standard deviation',
    note: `the population standard deviation across PLACE, ${BY_AREA}`,
  },
  { id: 'mean_absolute_value', label: 'Mean absolute value', note: `the mean absolute value over PLACE, ${BY_AREA}` },
]

export const DEFAULT_AGGREGATION = 'mean'

// Below a month, the area's values are combined first, then the Time step's (#80).
export function describeAggregation(id, timeStep = 'monthly', place = 'area') {
  const found = AGGREGATIONS.find((entry) => entry.id === id) ?? AGGREGATIONS[0]
  const item = { ...found, note: found.note.replace('PLACE', `the ${place}`) }
  if (timeStep === 'daily' || timeStep === '3-hourly') {
    const span = timeStep === 'daily' ? 'day' : '3 hours'
    const label = timeStep === 'daily' ? 'Daily' : '3-hourly'
    return `${label} values. Each is ${item.note} at each native time step, then combined over the ${span} by the same rule.`
  }
  return `Monthly values. Each is ${item.note}.`
}
