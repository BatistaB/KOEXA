import { useMemo, useState } from "react";
import type { ChartPoint } from "./chartTypes";
import { StatusBadge } from "../common/StatusBadge";
import { DatasetLink } from "../common/DatasetLink";
import { formatCounts, formatTpm } from "../../lib/format";
import { downloadCsv } from "../../lib/csv";
import "./SampleTable.css";

type SortKey = "sample_id" | "bioproject" | "condition" | "replicate" | "tpm" | "counts";

interface SampleTableProps {
  geneSymbol: string;
  points: ChartPoint[];
  selectedSampleId: string | null;
  hoveredSampleId: string | null;
  onHoverSample: (id: string | null) => void;
  onSelectSample: (id: string) => void;
  onSelectDataset: (bioproject: string) => void;
}

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "sample_id", label: "Sample" },
  { key: "bioproject", label: "Study" },
  { key: "condition", label: "Condition" },
  { key: "replicate", label: "Replicate", numeric: true },
  { key: "tpm", label: "TPM", numeric: true },
  { key: "counts", label: "Counts", numeric: true },
];

export function SampleTable({
  geneSymbol,
  points,
  selectedSampleId,
  hoveredSampleId,
  onHoverSample,
  onSelectSample,
  onSelectDataset,
}: SampleTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("bioproject");
  const [sortDir, setSortDir] = useState<1 | -1>(1);

  const sorted = useMemo(() => {
    const copy = [...points];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "sample_id":
          cmp = a.sample.sample_id.localeCompare(b.sample.sample_id);
          break;
        case "bioproject":
          cmp = a.sample.bioproject.localeCompare(b.sample.bioproject);
          break;
        case "condition":
          cmp = a.condition.condition_label.localeCompare(b.condition.condition_label);
          break;
        case "replicate":
          cmp = a.sample.biological_replicate - b.sample.biological_replicate;
          break;
        case "tpm":
          cmp = a.tpm - b.tpm;
          break;
        case "counts":
          cmp = a.estimatedCounts - b.estimatedCounts;
          break;
      }
      return cmp * sortDir;
    });
    return copy;
  }, [points, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  };

  const handleDownload = () => {
    downloadCsv(
      `${geneSymbol}_expression.csv`,
      ["sample_id", "bioproject", "condition_id", "condition_label", "strain", "biological_replicate", "TPM", "estimated_counts", "qc_status"],
      sorted.map((p) => [
        p.sample.sample_id,
        p.sample.bioproject,
        p.condition.condition_id,
        p.condition.condition_label,
        p.sample.strain,
        p.sample.biological_replicate,
        p.tpm,
        p.estimatedCounts,
        p.sample.qc_status,
      ]),
    );
  };

  return (
    <div className="sample-table-section">
      <div className="sample-table-section__header">
        <span className="sample-table-section__title">
          Samples ({points.length})
        </span>
        <button type="button" className="sample-table-section__download" onClick={handleDownload}>
          <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M6 1v7M3 5.5 6 8.5 9 5.5M2 10.5h8" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Download table (CSV)
        </button>
      </div>

      <div className="sample-table__scroll">
        <table className="sample-table">
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className={col.numeric ? "sample-table__num" : undefined}
                  onClick={() => toggleSort(col.key)}
                  aria-sort={sortKey === col.key ? (sortDir === 1 ? "ascending" : "descending") : "none"}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="sample-table__sort-arrow">{sortDir === 1 ? "↑" : "↓"}</span>
                  )}
                </th>
              ))}
              <th>QC</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p) => {
              const id = p.sample.sample_id;
              return (
                <tr
                  key={id}
                  data-selected={id === selectedSampleId}
                  onClick={() => onSelectSample(id)}
                  onMouseEnter={() => onHoverSample(id)}
                  onMouseLeave={() => onHoverSample(null)}
                  style={{
                    outline: id === hoveredSampleId ? "1px solid var(--border-default)" : undefined,
                  }}
                >
                  <td className="mono">{id}</td>
                  <td>
                    <DatasetLink bioproject={p.sample.bioproject} onSelect={onSelectDataset} />
                  </td>
                  <td className="sample-table__condition" title={p.condition.condition_label}>
                    {p.condition.condition_label}
                  </td>
                  <td className="sample-table__num">{p.sample.biological_replicate}</td>
                  <td className="sample-table__num mono">{formatTpm(p.tpm)}</td>
                  <td className="sample-table__num mono">{formatCounts(p.estimatedCounts)}</td>
                  <td>
                    <StatusBadge status={p.sample.qc_status} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
