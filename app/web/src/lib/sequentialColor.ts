/**
 * Sequential (magnitude) color scale for the chromosome expression map --
 * one hue, light -> dark, over `--seq-100..--seq-600` (see tokens.css).
 * Domain is the observed log10(mean TPM + 1) range so the ramp always
 * spans the data actually present, rather than a fixed guess.
 *
 * `sequentialColorIndex` is exported separately (not just used inside
 * `sequentialColor`) so the legend can filter bins by the exact same
 * bucket boundaries used to paint them -- the legend swatches ARE the 5
 * discrete buckets, not a decorative gradient, so "click a swatch" and
 * "which bucket is this bin in" must never drift apart.
 */
export const RAMP_STEPS = ["var(--seq-100)", "var(--seq-200)", "var(--seq-350)", "var(--seq-450)", "var(--seq-600)"];

export function sequentialColorIndex(value: number, domainMax: number): number {
  if (domainMax <= 0) return 0;
  const t = Math.min(1, Math.max(0, value / domainMax));
  return Math.min(RAMP_STEPS.length - 1, Math.floor(t * RAMP_STEPS.length));
}

export function sequentialColor(value: number, domainMax: number): string {
  return RAMP_STEPS[sequentialColorIndex(value, domainMax)];
}
