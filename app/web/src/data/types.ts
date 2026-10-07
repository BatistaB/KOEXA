/**
 * Shapes mirror PROJECT_MASTER_SPEC.md section 8 (Database) so the mock
 * fixtures here can be swapped for a real API response with no field
 * renaming — this UI is being built ahead of Milestone 6/7 against
 * fixture data (see docs/decisions/0005-milestone7-frontend-stack.md).
 */

export interface Dataset {
  dataset_id: string;
  bioproject: string;
  geo_accession: string | null;
  publication_doi: string | null;
  publication_title: string;
  organism: string;
  strain: string;
  study_description: string;
  source_repository: string;
}

/**
 * Study enrichment (`atlas annotate` / `atlas database load-annotations`,
 * src/aoryzae_atlas/annotation/): the paper that produced the data, a 3-part
 * summary, and per-run tags from the shared vocabulary
 * (metadata/sample_tag_vocabulary.tsv). Source/confidence of each tag live
 * in the database only.
 */
export type PaperStatus = "found" | "not_found" | "ambiguous";

export interface StudyAnnotation {
  bioproject: string;
  paper: {
    status: PaperStatus;
    title: string | null;
    authors: string | null;
    year: number | null;
    journal: string | null;
    doi: string | null;
    pmid: string | null;
    url: string | null;
  };
  summary: {
    objective: string;
    experimental_design: string;
    main_finding: string;
  };
  related_identifiers: Record<string, string | string[] | null>;
  /** One entry per exported run, tags already in display order. */
  samples: { sample_id: string; condition_id: string; tags: string[] }[];
}

export interface StudyAnnotations {
  byBioproject: Map<string, StudyAnnotation>;
  /** tag -> vocabulary category (e.g. "glucose" -> "carbon_source"). */
  tagCategories: Record<string, string>;
}

export interface Condition {
  condition_id: string;
  condition_label: string;
  strain: string;
  medium: string | null;
  culture_mode: string | null;
  carbon_source: string | null;
  nitrogen_source: string | null;
  substrate: string | null;
  temperature_C: number | null;
  pH: number | null;
  time_value: number | null;
  time_unit: string | null;
  stress: string | null;
  treatment: string | null;
  oxygen_condition: string | null;
  developmental_stage: string | null;
}

export type QcStatus = "pass" | "warning" | "fail";

export interface Sample {
  sample_id: string;
  run_accession: string;
  biosample: string;
  bioproject: string;
  strain: string;
  condition_id: string;
  biological_replicate: number;
  library_layout: "SINGLE" | "PAIRED";
  library_strategy: string;
  read_count: number;
  pipeline_status: string;
  qc_status: QcStatus;
  reference_version: string;
  pipeline_version: string;
}

export type Biotype = "protein_coding" | "tRNA" | "rRNA" | "ncRNA";

export interface Gene {
  canonical_gene_id: string;
  gene_symbol: string | null;
  gene_name: string | null;
  chromosome: string;
  start: number;
  end: number;
  strand: "+" | "-";
  biotype: Biotype;
  description: string;
  reference_version: string;
  uniprot_accession: string | null;
  fungidb_alt_id: string | null;
  /** Alternate short names beyond gene_symbol, if any (rare). */
  aliases: string[];
}

export interface GeneExpressionRow {
  sample_id: string;
  canonical_gene_id: string;
  TPM: number;
  estimated_counts: number;
}

export interface SampleQcMetrics {
  sample_id: string;
  mapping_rate: number;
  q30_rate: number;
  duplication_rate: number;
  genes_detected: number;
  salmon_total_gene_assigned_counts: number;
}

export type BiologicalLabel =
  | "constitutive_high"
  | "constitutive_medium"
  | "condition_specific"
  | "variable_broad"
  | "rarely_expressed";

export type ClassificationConfidence = "low" | "medium" | "high";

/**
 * Output of `atlas cluster genes` (src/aoryzae_atlas/clustering/classify.py):
 * BASE-model expression-behavior classification, one row per gene. Not
 * every gene has one -- genes with <2 detected conditions have an
 * undefined Tau and are excluded from clustering, so biological_label/
 * cluster_base are null for them (see classify.py's module docstring).
 */
export interface GeneClassification {
  canonical_gene_id: string;
  median_TPM: number;
  n_detected_conditions: number;
  n_conditions: number;
  Tau_log1p: number | null;
  Tau_raw: number | null;
  prevalence_TPM_1: number | null;
  robust_CV: number | null;
  cluster_base: number | null;
  biological_label: BiologicalLabel | null;
  classification_confidence: ClassificationConfidence;
}

/**
 * One fixed-size genomic window's worth of expression, for the
 * chromosome-wide expression map. `nGenes === 0` means an annotation gap
 * (nothing measured there), distinct from `meanTpm === 0` (measured, not
 * detected) -- see src/aoryzae_atlas/genome/karyotype.py.
 */
export interface ChromosomeBin {
  start: number;
  end: number;
  nGenes: number;
  nDetectedGenes: number;
  meanTpm: number | null;
  log10MeanTpm: number | null;
}

export interface ChromosomeTrack {
  chromosome: string;
  length: number;
  bins: ChromosomeBin[];
}

export interface ChromosomeExpression {
  binSizeBp: number;
  chromosomes: ChromosomeTrack[];
}

/**
 * Pan-transcriptomic expression rank (`atlas rank genes`, src/aoryzae_atlas/
 * rank/): every gene's *global* behavior across all independent biological
 * samples. Unlike GeneClassification (per-condition clustering), the
 * classes are rule-based with thresholds derived from the atlas's own
 * distributions, so they are re-derived on every `atlas refresh`.
 */
export type ExpressionClass =
  | "Constitutive High"
  | "Constitutive Core"
  | "Constitutive Low"
  | "Broad Variable"
  | "Context-Specific"
  | "Rare/Silent"
  | "Intermediate";

export interface ExpressionRankRow {
  canonical_gene_id: string;
  expression_class: ExpressionClass;
  /** Percentile-rank scores in (0, 1]; kept as separate axes, never blended. */
  level_score: number;
  stability_score: number;
  specificity_score: number;
  prevalence_score: number;
  /** 1 = best; each is an independent ordering of all genes. */
  global_rank: number;
  rank_most_expressed: number;
  rank_most_stable: number;
  rank_most_variable: number;
  rank_most_specific: number;
  rank_rarest: number;
  median_TPM: number;
  prevalence_TPM_1: number;
  MAD_logTPM: number;
  Tau: number | null;
  /** Semicolon-separated quality flags ('' when none): possible_study_effect, possible_strain_effect, low_sample_support, borderline_class. */
  quality_flags: string;
}

export interface ExpressionRankSummary {
  generated_at: string;
  n_genes: number;
  n_runs: number;
  n_samples: number;
  n_studies: number;
  n_strains: number;
  samples_per_study: Record<string, number>;
  samples_per_strain: Record<string, number>;
  class_order: ExpressionClass[];
  class_counts: Record<string, number>;
  flag_rates: Record<string, number>;
  robustness: { perturbation: string; n_samples_used: number; class_agreement: number }[];
  median_robustness_agreement: number | null;
}

export interface ExpressionRank {
  summary: ExpressionRankSummary | null;
  rows: ExpressionRankRow[];
  byGene: Map<string, ExpressionRankRow>;
}
