// The Discovery schema requires every screen that repeats a computed number to
// write it exactly as the engine's narrative does (engine/discovery.py `_number`):
// rounded half up to at most three decimals, in decimal arithmetic, with no
// trailing zeros, and 0 rather than -0.
//
// The engine rounds the shortest decimal that round-trips the float. JavaScript's
// toExponential() produces those same digits, and BigInt does the rounding, so no
// binary floating point is involved: 7.0625 becomes 7.063, never 7.062.
export function formatNumber(value) {
  if (!Number.isFinite(value)) return String(value)

  const [mantissa, exponent] = value.toExponential().split('e')
  const negative = mantissa.startsWith('-')
  const digits = mantissa.replace('-', '').replace('.', '')
  const shift = Number(exponent) - (digits.length - 1) + 3

  let thousandths = BigInt(digits)
  if (shift >= 0) {
    thousandths *= 10n ** BigInt(shift)
  } else {
    const divisor = 10n ** BigInt(-shift)
    const remainder = thousandths % divisor
    thousandths /= divisor
    if (remainder * 2n >= divisor) thousandths += 1n
  }
  if (thousandths === 0n) return '0'

  const padded = thousandths.toString().padStart(4, '0')
  const whole = padded.slice(0, -3)
  const fraction = padded.slice(-3).replace(/0+$/, '')
  return `${negative ? '-' : ''}${whole}${fraction ? `.${fraction}` : ''}`
}

export function formatRate(trend) {
  const [low, high] = trend.confidence_interval_95.map(formatNumber)
  return {
    rate: formatNumber(trend.rate_per_decade),
    interval: `${low} to ${high}`,
    units: trend.units_per_decade,
  }
}
