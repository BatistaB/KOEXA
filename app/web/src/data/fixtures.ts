import type {
  Condition,
  Dataset,
  Gene,
  GeneExpressionRow,
  Sample,
  SampleQcMetrics,
} from "./types";

/**
 * Illustrative fixture data, shaped exactly like the real DuckDB tables
 * (PROJECT_MASTER_SPEC.md section 8) but with invented accessions/values —
 * the atlas itself only has 11 real samples ingested so far (Milestone 5,
 * in progress). Samples/conditions/datasets/QC are all invented here.
 *
 * The 9 genes below are also invented (real AO09 ID *format*, not real
 * RIB40 loci) but hand-tuned to tell a biologically plausible story
 * (catabolite repression, koji induction, heat stress) so the UI has real
 * signal to render and filter against. The REAL 12,090-gene RIB40 catalog
 * (see data/realGenes.ts, exported by scripts/export_gene_catalog.py) is
 * merged in alongside these at app startup, for UX/UI stress-testing at
 * real genome scale — those genes get synthetic filler expression with no
 * biological story (lib/syntheticExpression.ts), since Milestone 6 hasn't
 * produced full-genome quantification yet.
 * Swap this module for a fetch against the real API once Milestone 6 closes.
 */

const REFERENCE_VERSION = "FungiDB_v71";
const PIPELINE_VERSION = "nf-core/rnaseq 3.14 (salmon)";

export const datasets: Dataset[] = [
  {
    dataset_id: "DS001",
    bioproject: "PRJNA224101",
    geo_accession: "GSE142077",
    publication_doi: "10.1128/aem.01234-19",
    publication_title:
      "Carbon source-dependent regulation of amylolytic and proteolytic gene expression in Aspergillus oryzae RIB40",
    organism: "Aspergillus oryzae",
    strain: "RIB40",
    study_description:
      "Submerged batch culture, carbon catabolite repression vs. induction.",
    source_repository: "SRA",
  },
  {
    dataset_id: "DS002",
    bioproject: "PRJNA353338",
    geo_accession: "GSE104822",
    publication_doi: "10.1016/j.fgb.2020.103412",
    publication_title:
      "Time-resolved transcriptome of steamed-rice and wheat-bran koji fermentation",
    organism: "Aspergillus oryzae",
    strain: "RIB40",
    study_description: "Solid-state koji fermentation, 24h and 48h time points.",
    source_repository: "SRA",
  },
  {
    dataset_id: "DS003",
    bioproject: "PRJNA412177",
    geo_accession: null,
    publication_doi: null,
    publication_title:
      "Heat stress response and strain-level variation in industrial A. oryzae isolates",
    organism: "Aspergillus oryzae",
    strain: "multiple",
    study_description:
      "Short heat shock in submerged culture, RIB40 vs. strain 3.042.",
    source_repository: "ENA",
  },
];

export const conditions: Condition[] = [
  {
    condition_id: "C01",
    condition_label: "RIB40 | submerged | glucose | 30°C | 24h | control",
    strain: "RIB40",
    medium: "minimal medium",
    culture_mode: "submerged",
    carbon_source: "glucose",
    nitrogen_source: "NaNO3",
    substrate: null,
    temperature_C: 30,
    pH: 5.5,
    time_value: 24,
    time_unit: "h",
    stress: null,
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "vegetative",
  },
  {
    condition_id: "C02",
    condition_label: "RIB40 | submerged | starch (inducing) | 30°C | 24h",
    strain: "RIB40",
    medium: "minimal medium",
    culture_mode: "submerged",
    carbon_source: "soluble starch",
    nitrogen_source: "NaNO3",
    substrate: null,
    temperature_C: 30,
    pH: 5.5,
    time_value: 24,
    time_unit: "h",
    stress: null,
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "vegetative",
  },
  {
    condition_id: "C03",
    condition_label: "RIB40 | submerged | maltose | 30°C | 24h",
    strain: "RIB40",
    medium: "minimal medium",
    culture_mode: "submerged",
    carbon_source: "maltose",
    nitrogen_source: "NaNO3",
    substrate: null,
    temperature_C: 30,
    pH: 5.5,
    time_value: 24,
    time_unit: "h",
    stress: null,
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "vegetative",
  },
  {
    condition_id: "C04",
    condition_label: "RIB40 | solid-state | steamed rice (koji) | 30°C | 24h",
    strain: "RIB40",
    medium: "steamed rice",
    culture_mode: "solid-state",
    carbon_source: "rice starch",
    nitrogen_source: null,
    substrate: "steamed rice",
    temperature_C: 30,
    pH: null,
    time_value: 24,
    time_unit: "h",
    stress: null,
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "sporulating",
  },
  {
    condition_id: "C05",
    condition_label: "RIB40 | solid-state | steamed rice (koji) | 30°C | 48h",
    strain: "RIB40",
    medium: "steamed rice",
    culture_mode: "solid-state",
    carbon_source: "rice starch",
    nitrogen_source: null,
    substrate: "steamed rice",
    temperature_C: 30,
    pH: null,
    time_value: 48,
    time_unit: "h",
    stress: null,
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "sporulating",
  },
  {
    condition_id: "C06",
    condition_label: "RIB40 | solid-state | wheat bran | 30°C | 48h",
    strain: "RIB40",
    medium: "wheat bran",
    culture_mode: "solid-state",
    carbon_source: "xylan / arabinoxylan",
    nitrogen_source: null,
    substrate: "wheat bran",
    temperature_C: 30,
    pH: null,
    time_value: 48,
    time_unit: "h",
    stress: null,
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "sporulating",
  },
  {
    condition_id: "C07",
    condition_label: "RIB40 | submerged | glucose | 37°C | 6h | heat stress",
    strain: "RIB40",
    medium: "minimal medium",
    culture_mode: "submerged",
    carbon_source: "glucose",
    nitrogen_source: "NaNO3",
    substrate: null,
    temperature_C: 37,
    pH: 5.5,
    time_value: 6,
    time_unit: "h",
    stress: "heat shock",
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "vegetative",
  },
  {
    condition_id: "C08",
    condition_label: "3.042 | submerged | glucose | 30°C | 24h | control",
    strain: "3.042",
    medium: "minimal medium",
    culture_mode: "submerged",
    carbon_source: "glucose",
    nitrogen_source: "NaNO3",
    substrate: null,
    temperature_C: 30,
    pH: 5.5,
    time_value: 24,
    time_unit: "h",
    stress: null,
    treatment: null,
    oxygen_condition: "aerobic",
    developmental_stage: "vegetative",
  },
];

export const genes: Gene[] = [
  {
    canonical_gene_id: "AO090012000242",
    gene_symbol: "amyB",
    gene_name: "Taka-amylase A",
    chromosome: "Chr3_A_oryzae_RIB40",
    start: 1_204_812,
    end: 1_207_310,
    strand: "+",
    biotype: "protein_coding",
    description:
      "Secreted alpha-amylase; hydrolyzes starch to maltose/dextrins. Subject to carbon catabolite repression under glucose.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "P0C1B4",
    fungidb_alt_id: "AO070337000000",
    aliases: ["TAA"],
  },
  {
    canonical_gene_id: "AO090701000983",
    gene_symbol: "glaA",
    gene_name: "Glucoamylase A",
    chromosome: "Chr5_A_oryzae_RIB40",
    start: 3_882_004,
    end: 3_886_921,
    strand: "-",
    biotype: "protein_coding",
    description:
      "Secreted glucoamylase; releases glucose from starch non-reducing ends. Strongly induced during koji fermentation.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "P0C1A9",
    fungidb_alt_id: null,
    aliases: ["GLA1"],
  },
  {
    canonical_gene_id: "AO090003001568",
    gene_symbol: "alpA",
    gene_name: "Alkaline protease A",
    chromosome: "Chr1_A_oryzae_RIB40",
    start: 5_120_774,
    end: 5_123_009,
    strand: "+",
    biotype: "protein_coding",
    description:
      "Subtilisin-like alkaline serine protease; induced by nitrogen limitation and proteinaceous substrates.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "Q2UNJ8",
    fungidb_alt_id: null,
    aliases: ["ALPA"],
  },
  {
    canonical_gene_id: "AO090011000330",
    gene_symbol: "pepA",
    gene_name: "Aspergillopepsin A",
    chromosome: "Chr2_A_oryzae_RIB40",
    start: 902_115,
    end: 904_688,
    strand: "-",
    biotype: "protein_coding",
    description:
      "Secreted aspartic protease active at acidic pH; a major koji fermentation protease.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "P0DJ23",
    fungidb_alt_id: null,
    aliases: ["ASPPEP"],
  },
  {
    canonical_gene_id: "AO090026000138",
    gene_symbol: "brlA",
    gene_name: "Bristle A",
    chromosome: "Chr7_A_oryzae_RIB40",
    start: 2_218_440,
    end: 2_220_115,
    strand: "+",
    biotype: "protein_coding",
    description:
      "C2H2 zinc-finger master regulator of conidiation; expressed at the onset of asexual sporulation, silent in submerged vegetative growth.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "Q2U8N1",
    fungidb_alt_id: null,
    aliases: [],
  },
  {
    canonical_gene_id: "AO090005000842",
    gene_symbol: "actA",
    gene_name: "Actin",
    chromosome: "Chr4_A_oryzae_RIB40",
    start: 4_410_221,
    end: 4_412_005,
    strand: "+",
    biotype: "protein_coding",
    description:
      "Cytoskeletal actin; stable constitutive expression used as an internal reference gene.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "P78624",
    fungidb_alt_id: null,
    aliases: [],
  },
  {
    canonical_gene_id: "AO090003000751",
    gene_symbol: "tpiA",
    gene_name: "Triose-phosphate isomerase",
    chromosome: "Chr1_A_oryzae_RIB40",
    start: 1_775_902,
    end: 1_777_310,
    strand: "-",
    biotype: "protein_coding",
    description:
      "Glycolytic enzyme; stable housekeeping expression across conditions.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "Q2UBK5",
    fungidb_alt_id: null,
    aliases: [],
  },
  {
    canonical_gene_id: "AO090701000961",
    gene_symbol: "xynA",
    gene_name: "Endo-1,4-beta-xylanase A",
    chromosome: "Chr5_A_oryzae_RIB40",
    start: 3_611_500,
    end: 3_613_240,
    strand: "+",
    biotype: "protein_coding",
    description:
      "Secreted xylanase; hydrolyzes arabinoxylan. Strongly induced on wheat-bran substrate.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "O74704",
    fungidb_alt_id: null,
    aliases: ["XYNA"],
  },
  {
    canonical_gene_id: "AO090010000122",
    gene_symbol: "pyrG",
    gene_name: "Orotidine-5'-phosphate decarboxylase",
    chromosome: "Chr6_A_oryzae_RIB40",
    start: 660_884,
    end: 662_390,
    strand: "-",
    biotype: "protein_coding",
    description:
      "Pyrimidine biosynthesis enzyme; common auxotrophic selection marker, mildly variable across conditions.",
    reference_version: REFERENCE_VERSION,
    uniprot_accession: "Q2U5W3",
    fungidb_alt_id: null,
    aliases: [],
  },
];

// --- Deterministic sample + expression generation -------------------------
// Seeded PRNG so the fixture is stable across reloads/tests.
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rand = mulberry32(20260921);
const gaussian = () => {
  // Box-Muller
  const u = Math.max(rand(), 1e-9);
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
};

// Baseline TPM per gene, per condition — the biological story the fixture tells.
const BASELINE_TPM: Record<string, Partial<Record<string, number>>> = {
  amyB: { C01: 9, C02: 1450, C03: 910, C04: 640, C05: 1120, C06: 420, C07: 18, C08: 12 },
  glaA: { C01: 14, C02: 1680, C03: 1040, C04: 980, C05: 2050, C06: 510, C07: 22, C08: 16 },
  alpA: { C01: 60, C02: 90, C03: 85, C04: 520, C05: 880, C06: 610, C07: 740, C08: 58 },
  pepA: { C01: 20, C02: 35, C03: 30, C04: 780, C05: 1240, C06: 340, C07: 40, C08: 18 },
  brlA: { C01: 3, C02: 4, C03: 3, C04: 310, C05: 890, C06: 260, C07: 2, C08: 3 },
  actA: { C01: 210, C02: 195, C03: 205, C04: 180, C05: 190, C06: 175, C07: 220, C08: 200 },
  tpiA: { C01: 175, C02: 168, C03: 172, C04: 155, C05: 160, C06: 150, C07: 190, C08: 170 },
  xynA: { C01: 6, C02: 40, C03: 25, C04: 30, C05: 45, C06: 1380, C07: 8, C08: 5 },
  pyrG: { C01: 55, C02: 60, C03: 58, C04: 50, C05: 48, C06: 52, C07: 62, C08: 54 },
};

const REPLICATES_PER_CONDITION = 3;

function buildSamplesAndExpression(): {
  samples: Sample[];
  expression: GeneExpressionRow[];
  qc: SampleQcMetrics[];
} {
  const samples: Sample[] = [];
  const expression: GeneExpressionRow[] = [];
  const qc: SampleQcMetrics[] = [];

  const conditionToDataset: Record<string, string> = {
    C01: "PRJNA224101",
    C02: "PRJNA224101",
    C03: "PRJNA224101",
    C04: "PRJNA353338",
    C05: "PRJNA353338",
    C06: "PRJNA353338",
    C07: "PRJNA412177",
    C08: "PRJNA412177",
  };

  let srrCounter = 15481200;
  let flaggedOnce = false;

  for (const condition of conditions) {
    const repCount =
      condition.condition_id === "C04" || condition.condition_id === "C07"
        ? 4
        : REPLICATES_PER_CONDITION;

    for (let rep = 1; rep <= repCount; rep++) {
      srrCounter += 1;
      const sampleId = `SRR${srrCounter}`;
      const bioproject = conditionToDataset[condition.condition_id];

      // One deliberately-flagged sample (low mapping rate) to exercise the
      // "QC attention" state — never the first sample, so the default view
      // isn't dominated by it.
      const shouldFlag =
        !flaggedOnce && condition.condition_id === "C05" && rep === 2;
      if (shouldFlag) flaggedOnce = true;

      const mappingRate = shouldFlag ? 0.58 + rand() * 0.05 : 0.88 + rand() * 0.09;
      const qcStatus: Sample["qc_status"] = shouldFlag
        ? "warning"
        : mappingRate > 0.9
          ? "pass"
          : "pass";

      samples.push({
        sample_id: sampleId,
        run_accession: sampleId,
        biosample: `SAMN${10_000_000 + srrCounter}`,
        bioproject,
        strain: condition.strain,
        condition_id: condition.condition_id,
        biological_replicate: rep,
        library_layout: "PAIRED",
        library_strategy: "RNA-Seq",
        read_count: Math.round(22_000_000 + rand() * 9_000_000),
        pipeline_status: "QUANTIFIED",
        qc_status: qcStatus,
        reference_version: REFERENCE_VERSION,
        pipeline_version: PIPELINE_VERSION,
      });

      qc.push({
        sample_id: sampleId,
        mapping_rate: mappingRate,
        q30_rate: 0.92 + rand() * 0.06,
        duplication_rate: shouldFlag ? 0.41 + rand() * 0.05 : 0.12 + rand() * 0.08,
        genes_detected: Math.round(
          (shouldFlag ? 7200 : 9400) + rand() * 500,
        ),
        salmon_total_gene_assigned_counts: Math.round(
          (shouldFlag ? 9_500_000 : 18_000_000) + rand() * 3_000_000,
        ),
      });

      for (const gene of genes) {
        const baseline =
          BASELINE_TPM[gene.gene_symbol ?? ""]?.[condition.condition_id] ?? 10;
        // Log-normal biological + technical noise around the baseline.
        const noiseFactor = Math.exp(gaussian() * 0.22);
        const dropoutPenalty = shouldFlag ? 0.6 : 1;
        const tpm = Math.max(0, baseline * noiseFactor * dropoutPenalty);
        const estimatedCounts = Math.round(
          (tpm / 1_000_000) *
            (shouldFlag ? 9_500_000 : 18_000_000) *
            (0.8 + rand() * 0.4),
        );

        expression.push({
          sample_id: sampleId,
          canonical_gene_id: gene.canonical_gene_id,
          TPM: Math.round(tpm * 100) / 100,
          estimated_counts: estimatedCounts,
        });
      }
    }
  }

  return { samples, expression, qc };
}

const generated = buildSamplesAndExpression();
export const samples: Sample[] = generated.samples;
export const geneExpression: GeneExpressionRow[] = generated.expression;
export const sampleQcMetrics: SampleQcMetrics[] = generated.qc;

export const referenceVersion = REFERENCE_VERSION;
export const pipelineVersion = PIPELINE_VERSION;
