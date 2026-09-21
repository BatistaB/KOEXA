import type { Condition } from "../data/types";

/** Short axis-tick label for a condition — the full structured breakdown
 * lives in the right panel and sample table; the chart only needs enough
 * to distinguish bands at a glance. */
export function shortConditionLabel(c: Condition): string {
  const bits: string[] = [];
  if (c.stress) bits.push(c.stress);
  else if (c.substrate) bits.push(c.substrate);
  else if (c.carbon_source) bits.push(c.carbon_source);
  if (c.time_value) bits.push(`${c.time_value}${c.time_unit}`);
  let label = bits.join(" · ") || c.condition_label;
  if (c.strain !== "RIB40") label += ` — ${c.strain}`;
  return label;
}
