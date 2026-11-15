// The Aggregations of spec #72, under the API's names. The API combines the
// cells; this only names the choices and says what each one means (#78).
const BY_AREA = 'counting each grid cell in proportion to its area'

export const AGGREGATIONS = [
  { id: 'mean', label: 'Mean', note: 'the mean over the area, weighted by the area of each grid cell' },
  { id: 'median', label: 'Median', note: `the median over the area, ${BY_AREA}` },
  { id: 'minimum', label: 'Minimum', note: "the lowest value among the area's grid cells" },
  { id: 'maximum', label: 'Maximum', note: "the highest value among the area's grid cells" },
  { id: 'root_mean_square', label: 'Root mean square', note: `the root mean square over the area, ${BY_AREA}` },
  {
    id: 'standard_deviation',
    label: 'Standard deviation',
    note: `the population standard deviation across the area, ${BY_AREA}`,
  },
  { id: 'mean_absolute_value', label: 'Mean absolute value', note: `the mean absolute value over the area, ${BY_AREA}` },
]

export const DEFAULT_AGGREGATION = 'mean'

export function describeAggregation(id) {
  const item = AGGREGATIONS.find((entry) => entry.id === id) ?? AGGREGATIONS[0]
  return `Monthly values. Each is ${item.note}.`
}
