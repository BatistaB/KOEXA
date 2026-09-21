import type { Condition, Dataset, Gene, Sample, SampleQcMetrics } from "../../data/types";
import { StatusBadge } from "../common/StatusBadge";
import { DatasetLink } from "../common/DatasetLink";
import { formatCounts, formatPercent, formatReadCount, formatTpm } from "../../lib/format";
import "./RightPanel.css";

export interface GeneSummary {
  gene: Gene;
  sampleCount: number;
  conditionCount: number;
  datasetCount: number;
  detectionRate: number;
  medianTpm: number;
}

export interface AtlasSummary {
  geneCount: number;
  sampleCount: number;
  conditionCount: number;
  datasetCount: number;
}

export interface DatasetDetail {
  dataset: Dataset;
  sampleCount: number;
  conditionCount: number;
}

interface SelectedSampleDetail {
  sample: Sample;
  condition: Condition;
  dataset: Dataset | undefined;
  qc: SampleQcMetrics | undefined;
  tpm: number;
  estimatedCounts: number;
}

interface RightPanelProps {
  geneSummary: GeneSummary | null;
  selection: SelectedSampleDetail | null;
  atlasSummary?: AtlasSummary;
  datasetDetail: DatasetDetail | null;
  onCloseDataset: () => void;
  onSelectDataset: (bioproject: string) => void;
}

const CONDITION_FIELDS: { key: keyof Condition; label: string }[] = [
  { key: "medium", label: "Medium" },
  { key: "culture_mode", label: "Culture mode" },
  { key: "carbon_source", label: "Carbon source" },
  { key: "nitrogen_source", label: "Nitrogen source" },
  { key: "substrate", label: "Substrate" },
  { key: "temperature_C", label: "Temperature" },
  { key: "pH", label: "pH" },
  { key: "stress", label: "Stress" },
  { key: "developmental_stage", label: "Stage" },
];

export function RightPanel({
  geneSummary,
  selection,
  atlasSummary,
  datasetDetail,
  onCloseDataset,
  onSelectDataset,
}: RightPanelProps) {
  if (datasetDetail) {
    const { dataset, sampleCount, conditionCount } = datasetDetail;
    return (
      <aside className="right-panel">
        <div className="right-panel__title-row">
          <div className="right-panel__title">Study</div>
          <button type="button" className="right-panel__close" onClick={onCloseDataset} aria-label="Close study detail">
            ✕
          </button>
        </div>

        <div className="right-panel__section">
          <div className="right-panel__sample-id mono">{dataset.bioproject}</div>
          <div className="right-panel__sample-sub">
            {dataset.source_repository}
            {dataset.geo_accession ? ` · ${dataset.geo_accession}` : ""}
          </div>
        </div>

        <div className="right-panel__section">
          <div className="right-panel__stat-grid">
            <div className="right-panel__stat">
              <span className="right-panel__stat-value">{sampleCount}</span>
              <span className="right-panel__stat-label">samples</span>
            </div>
            <div className="right-panel__stat">
              <span className="right-panel__stat-value">{conditionCount}</span>
              <span className="right-panel__stat-label">conditions</span>
            </div>
          </div>
        </div>

        <div className="right-panel__section">
          <div className="right-panel__section-label">Publication</div>
          <p className="right-panel__prose">{dataset.publication_title}</p>
          <div className="right-panel__row">
            <span className="right-panel__row-label">DOI</span>
            <span className="right-panel__row-value mono">{dataset.publication_doi ?? "Not yet published"}</span>
          </div>
        </div>

        <div className="right-panel__section">
          <div className="right-panel__section-label">Design</div>
          <p className="right-panel__prose">{dataset.study_description}</p>
          <div className="right-panel__row">
            <span className="right-panel__row-label">Organism</span>
            <span className="right-panel__row-value">{dataset.organism}</span>
          </div>
          <div className="right-panel__row">
            <span className="right-panel__row-label">Strain</span>
            <span className="right-panel__row-value">{dataset.strain}</span>
          </div>
        </div>

        <p className="right-panel__empty">
          Illustrative fixture data — will link to the real dataset record once Milestone 6 lands.
        </p>
      </aside>
    );
  }

  if (!geneSummary) {
    return (
      <aside className="right-panel">
        <div className="right-panel__title">Atlas</div>
        {atlasSummary && (
          <div className="right-panel__section">
            <div className="right-panel__stat-grid">
              <div className="right-panel__stat">
                <span className="right-panel__stat-value">{atlasSummary.geneCount}</span>
                <span className="right-panel__stat-label">genes</span>
              </div>
              <div className="right-panel__stat">
                <span className="right-panel__stat-value">{atlasSummary.sampleCount}</span>
                <span className="right-panel__stat-label">samples</span>
              </div>
              <div className="right-panel__stat">
                <span className="right-panel__stat-value">{atlasSummary.conditionCount}</span>
                <span className="right-panel__stat-label">conditions</span>
              </div>
              <div className="right-panel__stat">
                <span className="right-panel__stat-value">{atlasSummary.datasetCount}</span>
                <span className="right-panel__stat-label">studies</span>
              </div>
            </div>
          </div>
        )}
        <p className="right-panel__empty">
          Click a bar in the ranking, or search a gene, to see its expression
          summary and sample metadata.
        </p>
      </aside>
    );
  }

  if (selection) {
    const { sample, condition, dataset, qc } = selection;
    return (
      <aside className="right-panel">
        <div className="right-panel__title">Selected sample</div>

        <div className="right-panel__section">
          <div className="right-panel__sample-id mono">{sample.sample_id}</div>
          <div className="right-panel__sample-sub">
            <DatasetLink bioproject={dataset?.bioproject ?? sample.bioproject} onSelect={onSelectDataset} />
            {" · replicate "}
            {sample.biological_replicate}
          </div>
          <StatusBadge status={sample.qc_status} />
        </div>

        <div className="right-panel__section">
          <div className="right-panel__section-label">Expression ({geneSummary.gene.gene_symbol})</div>
          <div className="right-panel__row">
            <span className="right-panel__row-label">TPM</span>
            <span className="right-panel__row-value mono">{formatTpm(selection.tpm)}</span>
          </div>
          <div className="right-panel__row">
            <span className="right-panel__row-label">Estimated counts</span>
            <span className="right-panel__row-value mono">{formatCounts(selection.estimatedCounts)}</span>
          </div>
        </div>

        <div className="right-panel__section">
          <div className="right-panel__section-label">Condition</div>
          <div className="right-panel__row">
            <span className="right-panel__row-label">Label</span>
            <span className="right-panel__row-value">{condition.condition_label}</span>
          </div>
          {CONDITION_FIELDS.map(({ key, label }) => {
            const value = condition[key];
            if (value === null || value === undefined || value === "") return null;
            const display =
              key === "temperature_C" ? `${value}°C` : key === "pH" ? `pH ${value}` : String(value);
            return (
              <div className="right-panel__row" key={key}>
                <span className="right-panel__row-label">{label}</span>
                <span className="right-panel__row-value">{display}</span>
              </div>
            );
          })}
        </div>

        <div className="right-panel__section">
          <div className="right-panel__section-label">Library</div>
          <div className="right-panel__row">
            <span className="right-panel__row-label">Strategy</span>
            <span className="right-panel__row-value">{sample.library_strategy} · {sample.library_layout}</span>
          </div>
          <div className="right-panel__row">
            <span className="right-panel__row-label">Reads</span>
            <span className="right-panel__row-value mono">{formatReadCount(sample.read_count)}</span>
          </div>
        </div>

        {qc && (
          <div className="right-panel__section">
            <div className="right-panel__section-label">QC metrics</div>
            <div className="right-panel__row">
              <span className="right-panel__row-label">Mapping rate</span>
              <span className="right-panel__row-value mono">{formatPercent(qc.mapping_rate)}</span>
            </div>
            <div className="right-panel__row">
              <span className="right-panel__row-label">Q30</span>
              <span className="right-panel__row-value mono">{formatPercent(qc.q30_rate)}</span>
            </div>
            <div className="right-panel__row">
              <span className="right-panel__row-label">Duplication</span>
              <span className="right-panel__row-value mono">{formatPercent(qc.duplication_rate)}</span>
            </div>
            <div className="right-panel__row">
              <span className="right-panel__row-label">Genes detected</span>
              <span className="right-panel__row-value mono">{formatCounts(qc.genes_detected)}</span>
            </div>
          </div>
        )}
      </aside>
    );
  }

  const { gene } = geneSummary;
  return (
    <aside className="right-panel">
      <div className="right-panel__title">Gene summary</div>

      <div className="right-panel__section">
        <div className="right-panel__stat-grid">
          <div className="right-panel__stat">
            <span className="right-panel__stat-value">{geneSummary.sampleCount}</span>
            <span className="right-panel__stat-label">samples detected</span>
          </div>
          <div className="right-panel__stat">
            <span className="right-panel__stat-value">{geneSummary.conditionCount}</span>
            <span className="right-panel__stat-label">conditions</span>
          </div>
          <div className="right-panel__stat">
            <span className="right-panel__stat-value">{geneSummary.datasetCount}</span>
            <span className="right-panel__stat-label">studies</span>
          </div>
          <div className="right-panel__stat">
            <span className="right-panel__stat-value">{formatPercent(geneSummary.detectionRate)}</span>
            <span className="right-panel__stat-label">detected (TPM&gt;0)</span>
          </div>
        </div>
      </div>

      <div className="right-panel__section">
        <div className="right-panel__section-label">Identity</div>
        <div className="right-panel__row">
          <span className="right-panel__row-label">Canonical ID</span>
          <span className="right-panel__row-value mono">{gene.canonical_gene_id}</span>
        </div>
        <div className="right-panel__row">
          <span className="right-panel__row-label">Chromosome</span>
          <span className="right-panel__row-value mono">
            {gene.chromosome.replace("_A_oryzae_RIB40", "")}:{gene.start.toLocaleString("en-US")}-{gene.end.toLocaleString("en-US")} ({gene.strand})
          </span>
        </div>
        <div className="right-panel__row">
          <span className="right-panel__row-label">Biotype</span>
          <span className="right-panel__row-value">{gene.biotype}</span>
        </div>
        <div className="right-panel__row">
          <span className="right-panel__row-label">Median TPM</span>
          <span className="right-panel__row-value mono">{formatTpm(geneSummary.medianTpm)}</span>
        </div>
      </div>

      <div className="right-panel__section">
        <div className="right-panel__section-label">Provenance</div>
        <div className="right-panel__row">
          <span className="right-panel__row-label">Reference</span>
          <span className="right-panel__row-value">{gene.reference_version}</span>
        </div>
      </div>

      <p className="right-panel__empty">
        Hover or click a sample in the chart or table to inspect its
        metadata.
      </p>
    </aside>
  );
}
