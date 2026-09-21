export function niceLinearTicks(max: number, count = 5): number[] {
  if (max <= 0) return [0];
  const rough = max / count;
  const mag = 10 ** Math.floor(Math.log10(rough));
  const norm = rough / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const ticks: number[] = [];
  for (let t = 0; t <= max + step * 0.5; t += step) {
    ticks.push(Math.round(t * 100) / 100);
  }
  return ticks;
}

const LOG_CANDIDATES = [0, 1, 10, 100, 1000, 10000, 100000];

export function logTicks(max: number): number[] {
  const ticks = LOG_CANDIDATES.filter((t) => t <= max * 1.15);
  return ticks.length >= 2 ? ticks : [0, Math.ceil(max)];
}
