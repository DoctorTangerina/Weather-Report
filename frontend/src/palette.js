// One colour per Region of a Discovery, in region_ids order, shared by the globe
// and the charts so a student can match a shape on the Earth to its line.
// Both read on the dark globe and on the light sidebar.
export const REGION_COLORS = ['#17a9c2', '#ec7a3c']

export function withAlpha(hex, alpha) {
  const value = Number.parseInt(hex.slice(1), 16)
  return `rgba(${value >> 16}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`
}
