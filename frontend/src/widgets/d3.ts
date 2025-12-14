import { scaleLinear } from 'd3-scale'

export function computeLinearScale(domain: [number, number], range: [number, number]) {
  return scaleLinear(domain, range)
}
