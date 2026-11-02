/**
 * Dense gene x sample expression, read from the binary files `atlas app export-web` writes
 * (expression_tpm.bin / expression_counts.bin, little-endian float32, one row per gene; the row and
 * column order is in expression_index.json). Typed arrays keep ~4.6M values at ~18MB per matrix with no
 * JSON parsing, and a (gene, sample) lookup is two Map hits plus one array read.
 *
 * Counts are only shown in the gene view, so they load lazily (`ensureCounts`) and read as 0 until then.
 */
export class ExpressionMatrix {
  private readonly geneRow: Map<string, number>;
  private readonly sampleCol: Map<string, number>;
  private counts: Float32Array | null = null;
  private countsPromise: Promise<void> | null = null;

  readonly genes: string[];
  readonly samples: string[];
  readonly tpm: Float32Array;
  private readonly countsUrl: string | null;

  constructor(genes: string[], samples: string[], tpm: Float32Array, countsUrl: string | null) {
    this.genes = genes;
    this.samples = samples;
    this.tpm = tpm;
    this.countsUrl = countsUrl;
    this.geneRow = new Map(genes.map((g, i) => [g, i]));
    this.sampleCol = new Map(samples.map((s, i) => [s, i]));
  }

  get nSamples(): number {
    return this.samples.length;
  }

  rowOf(geneId: string): number | undefined {
    return this.geneRow.get(geneId);
  }

  colOf(sampleId: string): number | undefined {
    return this.sampleCol.get(sampleId);
  }

  tpmAt(geneId: string, sampleId: string): number {
    const r = this.geneRow.get(geneId);
    const c = this.sampleCol.get(sampleId);
    return r === undefined || c === undefined ? 0 : this.tpm[r * this.samples.length + c];
  }

  countsAt(geneId: string, sampleId: string): number {
    const r = this.geneRow.get(geneId);
    const c = this.sampleCol.get(sampleId);
    return !this.counts || r === undefined || c === undefined ? 0 : this.counts[r * this.samples.length + c];
  }

  get countsLoaded(): boolean {
    return this.counts !== null;
  }

  ensureCounts(): Promise<void> {
    if (this.counts || !this.countsUrl) return Promise.resolve();
    this.countsPromise ??= fetch(this.countsUrl)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load ${this.countsUrl}: ${res.status}`);
        return res.arrayBuffer();
      })
      .then((buf) => {
        this.counts = new Float32Array(buf);
      });
    return this.countsPromise;
  }
}

export const EMPTY_EXPRESSION = new ExpressionMatrix([], [], new Float32Array(0), null);

export async function loadExpressionMatrix(): Promise<ExpressionMatrix> {
  const [indexRes, tpmRes] = await Promise.all([fetch("/data/expression_index.json"), fetch("/data/expression_tpm.bin")]);
  if (!indexRes.ok || !tpmRes.ok) throw new Error("Failed to load the expression matrix");
  const index = (await indexRes.json()) as { genes: string[]; samples: string[] };
  const tpm = new Float32Array(await tpmRes.arrayBuffer());
  return new ExpressionMatrix(index.genes, index.samples, tpm, "/data/expression_counts.bin");
}
