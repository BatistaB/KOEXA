export function formatTpm(value: number): string {
  if (value < 10) return value.toFixed(1);
  return Math.round(value).toLocaleString("en-US");
}

export function formatCounts(value: number): string {
  return Math.round(value).toLocaleString("en-US");
}

export function formatPercent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatReadCount(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
  return String(value);
}
