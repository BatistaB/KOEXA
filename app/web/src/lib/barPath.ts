/** Rounded-top, square-bottom bar path — the project's fixed bar mark spec. */
export function roundedTopBarPath(x: number, y: number, width: number, height: number, radius = 3): string {
  if (height <= 0.5) {
    return `M ${x} ${y + Math.max(height, 0)} L ${x + width} ${y + Math.max(height, 0)} Z`;
  }
  const r = Math.min(radius, width / 2, height);
  return [
    `M ${x} ${y + height}`,
    `L ${x} ${y + r}`,
    `Q ${x} ${y} ${x + r} ${y}`,
    `L ${x + width - r} ${y}`,
    `Q ${x + width} ${y} ${x + width} ${y + r}`,
    `L ${x + width} ${y + height}`,
    "Z",
  ].join(" ");
}

/** Plain rectangle path (used for stacked interior segments — no rounding). */
export function rectPath(x: number, y: number, width: number, height: number): string {
  if (height <= 0) return "";
  return `M ${x} ${y + height} L ${x} ${y} L ${x + width} ${y} L ${x + width} ${y + height} Z`;
}
