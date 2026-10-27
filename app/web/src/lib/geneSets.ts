/** "secreted" -> "Secreted", "cell_wall" -> "Cell wall": one label shared by the filter buttons and the chart subtitles. */
export function geneSetLabel(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, " ");
}
