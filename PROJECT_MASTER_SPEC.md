# PROJECT_MASTER_SPEC.md

## Aspergillus oryzae Transcriptome Atlas

**Project type:** KOEXA (KOji EXpression Atlas), a
reproducible public RNA-seq compendium and transcriptome atlas inspired
by AFED (*Aspergillus flavus* Expression Database)\
**Primary organism:** *Aspergillus oryzae*\
**Primary goal:** first reproduce the scientifically useful first layer
of AFED for *A. oryzae*: discover and curate public transcriptome
studies, process them uniformly, expose AO09-centered expression and
metadata through an interactive KOEXA interface, and retain compact,
traceable outputs. After this acquisition and expression-database layer
is validated, extend KOEXA with prevalence, variability, Tsallis/Hill
diversity, specificity, clustering, biological classification,
promoter-candidate discovery, and future analyses.

**Implementation strategy:** reuse established tools rather than rebuild
the public-data pipeline from scratch. Use `pysradb` and official
NCBI/ENA APIs for discovery, `nf-core/fetchngs` for approved downloads,
`nf-core/rnaseq` for reproducible QC and quantification, Nextflow for
checkpointing/resume, and the MIT-licensed AFED code and publication as
the methodological and interface reference. KOEXA-specific code owns
AO09/UniProt reconciliation, condition curation, database ingestion,
storage policy, atlas construction, and advanced analyses.

------------------------------------------------------------------------

# 0. Instructions to Codex

You are implementing a scientific data platform, not a one-off notebook.

Priorities, in order:

1.  **Data integrity**
2.  **Reproducibility**
3.  **Safe storage management**
4.  **Traceability/provenance**
5.  **Resumability after interruption**
6.  **Quality control**
7.  **Correct biological metadata**
8.  **Extensibility**
9.  **Performance**

The first product milestone is KOEXA functional parity with the useful
core of AFED, adapted to *A. oryzae*. Treat AFED as a cited reference
implementation, not as an unexamined black box. Preserve its MIT license
and attribution for reused code. Audit dependencies, data assumptions,
reference identifiers, and processing decisions before adapting any
component.

Prefer orchestration and processing components that already solve the
problem well:

-   official NCBI/ENA services and `pysradb` for discovery;
-   `nf-core/fetchngs` for accession resolution, download, and checksum
    validation;
-   `nf-core/rnaseq` for reproducible RNA-seq QC and quantification;
-   Nextflow `-resume` for durable recovery after interruption;
-   AFED's Shiny interface patterns for the first KOEXA user experience.

Custom code must be limited to the parts that are scientifically or
operationally specific to KOEXA: AO09/UniProt identifiers, metadata and
condition curation, study approval, provenance, safe cleanup, compact
database ingestion, atlas matrices, and downstream analyses.

Do not silently guess biological metadata, library layout, gene
mappings, or failed sample status.

Do not delete raw/intermediate data until the final quantification and
required QC outputs have been validated and registered in the database.

Every important operation must be logged.

The project must work on a modest personal computer. Assume disk space,
RAM, CPU, and bandwidth are limited.

Start with a small MVP and tests. Do **not** immediately download
hundreds of RNA-seq datasets.

------------------------------------------------------------------------

# 1. Scientific objective

Build a condition-wide transcriptomic atlas of *Aspergillus oryzae*.

The central data object is a matrix:

``` text
Gene             SRR01   SRR02   SRR03   ...   SRR850
AO090001000001    23.2    19.7    31.2         25.1
AO090001000002  1523.4  1411.2     0.2       1820.1
AO090001000003     0.0     0.1  4211.3          0.0
...
```

Values should initially be TPM from a common processing pipeline.

Every sample must retain its biological metadata, especially
**condition**.

The atlas should eventually support questions such as:

-   Which genes are expressed in almost every condition?
-   Which genes are consistently highly expressed?
-   Which genes are consistently low but detectable?
-   Which genes are highly variable?
-   Which genes are condition-specific?
-   Which genes are strongly inducible?
-   Which genes are rarely expressed?
-   Which genes are candidate constitutive/housekeeping genes?
-   Which genes are candidate promoters for constitutive or
    condition-specific expression?
-   How does transcriptomic diversity change across conditions?
-   Which genes show broad versus specialized expression using
    generalized entropy?
-   How do solid-state, submerged, stress, carbon-source, developmental,
    production, and other conditions differ?
-   Can these data later be projected onto GEM/GPR annotations?

Development is deliberately divided into two scientific layers.

**Layer 1 --- KOEXA expression database:**

-   inventory public *A. oryzae* transcriptome studies;
-   curate studies, samples, conditions, strains, and replicates;
-   uniformly process approved raw RNA-seq;
-   quantify expression against one frozen RIB40-compatible reference;
-   expose AO09-centered TPM, QC, and metadata in an AFED-like
    interactive interface;
-   provide gene barplots, heatmaps, PCA, downloads, co-expression, and
    genome-browser support as the data permit.

**Layer 2 --- KOEXA atlas analytics:**

-   sample- and condition-level matrices;
-   prevalence, variability, and specificity;
-   Tsallis/Hill generalized diversity;
-   computational clustering and cautious biological interpretation;
-   constitutive, inducible, and condition-specific candidates;
-   promoter-candidate, annotation, and future GEM extensions.

Layer 2 must not delay delivery and validation of Layer 1. Advanced
classification begins only after discovery, acquisition, reference
selection, QC, and the KOEXA expression database are functioning.

**Important:** the raw TPM matrix is the primary reusable scientific
asset. Classification is downstream and must never replace or overwrite
the measurements.

------------------------------------------------------------------------

# 2. Scope

## 2.1 Included initially

-   Public RNA-seq from *Aspergillus oryzae*.
-   A reproducible discovery report describing how many studies,
    BioProjects, experiments, samples, and runs are publicly available,
    with estimated download volume and explicit inclusion/exclusion
    decisions.
-   SRA/BioProject/GEO metadata when available.
-   Multiple strains may eventually be supported.
-   Multiple biological conditions are explicitly desired.
-   Biological replicates are allowed and should be retained as
    individual samples.
-   A canonical gene identifier system based on `AO09...` identifiers
    should be used wherever biologically valid.
-   Quantification should use one frozen canonical reference for
    directly compatible samples.
-   Compact per-sample quantification results, QC summaries, metadata,
    logs, and provenance are retained.
-   Large raw/intermediate files are deleted after successful
    validation.
-   A KOEXA interactive application modeled on AFED, initially
    supporting gene search, per-sample TPM barplots, metadata inspection,
    heatmaps, PCA, downloadable tables, and QC visibility.
-   UniProt Entry, Entry Name, protein names, and aliases as searchable
    annotation fields linked to canonical AO09 identifiers through an
    explicit mapping table.

## 2.2 Not required for MVP

-   Multi-agent architecture.
-   Codex SDK.
-   GEM integration.
-   Differential expression.
-   Publicly hosted, production-scale web deployment; the MVP may run
    the KOEXA interface locally.
-   Immediate feature parity with every AFED visualization before the
    first KOEXA data release.
-   Machine-learning biological interpretation.
-   Automatic literature interpretation by an LLM.
-   Processing every public sample immediately.
-   Tsallis/Hill classification before the KOEXA acquisition,
    quantification, metadata, and basic interface layers are validated.

These may be added later.

------------------------------------------------------------------------

# 3. Core scientific principles

## 3.1 One canonical reference

The atlas must define and freeze a canonical *A. oryzae* reference
before large-scale processing.

Create:

``` text
config/reference.yaml
```

Store at minimum:

``` yaml
organism: Aspergillus oryzae
reference_strain: RIB40
assembly_accession: null
annotation_accession: null
reference_version: null
canonical_gene_id_system: AO09
genome_fasta: null
annotation_gtf_or_gff: null
transcript_fasta: null
index_version: null
```

Do not invent accession numbers. Populate only from verified sources.

All reference files must have checksums.

## 3.2 Do not mix author-provided TPM values into the main matrix

The primary atlas should use values generated by the same pipeline
whenever raw reads are available.

Published TPM/FPKM/count matrices may be imported into a separate
external-results layer, but must not silently enter the canonical
matrix.

## 3.3 Preserve sample-level replicates

Biological replicates remain independent columns in the main matrix.

Example:

``` text
condition_id: glucose_30h
replicate_id: 1
sample_accession: SRR...
```

Do not average replicates during ingestion.

Replicate aggregation may be produced later as a derived table.

## 3.4 Condition is mandatory

Every accepted sample must have a condition record.

A condition may contain structured factors such as:

-   medium
-   solid/submerged
-   carbon source
-   nitrogen source
-   temperature
-   pH
-   time
-   stress
-   treatment
-   strain
-   recombinant background
-   developmental stage
-   fermentation mode
-   oxygen condition
-   production phenotype
-   tissue/material/substrate
-   free-text original description

Unknown values must be explicitly represented as unknown, not guessed.

------------------------------------------------------------------------

# 4. Storage philosophy

The local machine must never be used as permanent storage for all raw
RNA-seq files.

The workflow is:

``` text
discover accession
      ↓
register metadata
      ↓
queue sample
      ↓
download ONE sample / small batch
      ↓
temporary scratch directory
      ↓
QC + quantification
      ↓
validate output
      ↓
save compact results
      ↓
register provenance
      ↓
delete large raw/intermediate files
      ↓
process next sample
```

Treat SRA/public repositories as recoverable remote raw-data storage.

Permanent local assets:

-   reference
-   sample metadata
-   condition metadata
-   compact quantification
-   QC summaries
-   logs
-   checksums
-   provenance
-   final matrices
-   analysis tables
-   database

Temporary assets:

-   `.sra`
-   FASTQ
-   large intermediate files
-   temporary decompression products
-   alignment files if ever generated

------------------------------------------------------------------------

# 5. Storage Guardian

Implement a storage-management module.

Configuration example:

``` yaml
storage:
  scratch_max_gb: 30
  minimum_free_gb: 20
  max_parallel_samples: 1

cleanup:
  delete_sra_after_fastq_validation: true
  delete_fastq_after_quant_validation: true
  delete_intermediates_after_success: true
  keep_failed_sample_raw_temporarily: true
  keep_quantification: true
  keep_qc: true
  keep_logs: true
```

Before each download:

1.  check available disk space;
2.  estimate download size when possible;
3.  refuse or postpone the sample if safety margin would be violated;
4.  create an isolated scratch directory;
5.  log all files created.

Deletion rules:

**Never delete FASTQ solely because a quantification command exited with
code 0.**

Before deletion confirm:

-   expected quantification files exist;
-   files are non-empty;
-   gene/transcript rows are plausible;
-   sample is registered;
-   QC status is registered;
-   checksums/provenance exist where applicable;
-   final compact output was successfully written;
-   database transaction completed.

On failure, mark sample appropriately and preserve enough information
for debugging.

------------------------------------------------------------------------

# 6. Sample state machine

Every sample must have a machine-readable state.

Suggested states:

``` text
DISCOVERED
METADATA_REVIEW
APPROVED
QUEUED
DOWNLOADING
DOWNLOADED
QC_RUNNING
QC_FAILED
QUANTIFYING
QUANT_FAILED
QUANTIFIED
VALIDATING
VALIDATION_FAILED
QC_PASSED
ARCHIVED
RAW_DELETED
EXCLUDED
RETRY
```

State transitions must be logged with timestamps.

The pipeline must be resumable.

KOEXA status and Nextflow status are complementary. DuckDB records the
scientific/business state of each sample and processing event. Nextflow
records task-level execution and cache state. Store the Nextflow run
name/session, pipeline revision, parameters, work directory, and resume
command with the KOEXA processing event.

A normal pause should stop at a safe task boundary. An abrupt shutdown
must leave incomplete files/directories marked as partial and must not
advance the KOEXA state. On restart, inspect the prior Nextflow session
and resume completed cached tasks rather than restarting the sample.
Never treat the presence of an unvalidated output file as a completed
checkpoint.

Example:

``` bash
python -m atlas resume
```

should continue unfinished work without reprocessing completed samples
unless explicitly requested.

------------------------------------------------------------------------

# 7. Project structure

Create approximately:

``` text
aoryzae-transcriptome-atlas/
│
├── README.md
├── AGENTS.md
├── PROJECT_MASTER_SPEC.md
├── pyproject.toml
├── run_atlas.ps1
├── .gitignore
│
├── config/
│   ├── reference.yaml
│   ├── pipeline.yaml
│   ├── qc.yaml
│   └── storage.yaml
│
├── metadata/
│   ├── datasets.tsv
│   ├── samples.tsv
│   ├── conditions.tsv
│   ├── gene_master.tsv
│   └── gene_external_identifiers.tsv
│
├── workflows/
│   ├── fetchngs/
│   ├── rnaseq/
│   └── params/
│
├── reference/
│   ├── README.md
│   ├── genome/
│   ├── annotation/
│   ├── transcripts/
│   └── salmon_index/
│
├── scratch/
│   └── nextflow-work/
│
├── runtime/
│   ├── status.json
│   └── control/
│
├── results/
│   ├── quant/
│   ├── qc/
│   ├── logs/
│   └── manifests/
│
├── database/
│   └── atlas.duckdb
│
├── matrices/
│   ├── tpm/
│   ├── counts/
│   └── condition_aggregates/
│
├── analysis/
│   ├── descriptive/
│   ├── replicate_qc/
│   ├── entropy/
│   ├── clustering/
│   └── classification/
│
├── reports/
│   ├── discovery/
│   ├── qc/
│   └── releases/
│
├── app/
│   ├── README.md
│   └── aoed_shiny/
│
├── src/
│   └── aoryzae_atlas/
│       ├── metadata/
│       ├── discovery/
│       ├── identifiers/
│       ├── download/
│       ├── qc/
│       ├── quantify/
│       ├── storage/
│       ├── database/
│       ├── matrix/
│       ├── entropy/
│       ├── clustering/
│       ├── app/
│       └── cli/
│
├── notebooks/
│   ├── 01_reference_validation.ipynb
│   ├── 02_mvp_dataset_review.ipynb
│   ├── 03_expression_atlas_qc.ipynb
│   ├── 04_gene_statistics.ipynb
│   └── 05_tsallis_exploration.ipynb
│
└── tests/
```

`scratch/`, FASTQ, SRA and large generated files must be excluded from
Git.

------------------------------------------------------------------------

# 8. Database

Use DuckDB as the local analytical database unless implementation
testing identifies a strong reason not to.

Minimum conceptual tables:

## `datasets`

One row per study/BioProject.

Fields:

``` text
dataset_id
bioproject
geo_accession
publication_doi
publication_title
organism
strain
study_description
source_repository
discovery_date
metadata_status
notes
```

## `samples`

One row per SRR/run or canonical biological sample unit.

Fields:

``` text
sample_id
run_accession
biosample
experiment_accession
bioproject
geo_sample
strain
condition_id
replicate_group
biological_replicate
technical_replicate
library_layout
library_strategy
library_source
read_length
read_count
download_size
pipeline_status
qc_status
quant_status
reference_version
pipeline_version
raw_deleted
exclusion_reason
created_at
updated_at
```

## `conditions`

Structured biological metadata:

``` text
condition_id
condition_label
strain
medium
culture_mode
carbon_source
nitrogen_source
substrate
temperature_C
pH
time_value
time_unit
stress
treatment
oxygen_condition
developmental_stage
recombinant_background
production_context
original_description
metadata_confidence
metadata_source
```

`condition_label` must be human-readable but should not replace
structured factors.

Example:

``` text
RIB40 | submerged | glucose | 30C | 24h | control
```

## `genes`

``` text
canonical_gene_id
gene_symbol
gene_name
chromosome
start
end
strand
biotype
description
reference_version
```

Future annotation fields may include GO, KEGG, InterPro, Pfam, GEM
reaction links, secretion annotation, etc.

## `sample_qc`

Store compact QC metrics.

## `processing_events`

Audit trail of pipeline actions.

## `gene_expression`

Prefer a scalable long-format representation internally:

``` text
sample_id
canonical_gene_id
TPM
estimated_counts
effective_length
```

Also export wide matrices for users.

------------------------------------------------------------------------

# 9. Quantification strategy

Do not build a new download and general-purpose RNA-seq processing
pipeline when maintained community workflows already provide those
capabilities. KOEXA should orchestrate pinned releases of:

-   `nf-core/fetchngs` for approved accession resolution, metadata,
    FASTQ acquisition, and checksum validation;
-   `nf-core/rnaseq` for technical QC, library handling, and
    quantification;
-   Nextflow for task isolation, caching, provenance, and `-resume`.

For the primary KOEXA matrix, prefer Salmon transcript-level
quantification and gene-level aggregation to avoid permanently retaining
BAM files. Pin workflow, container, reference, and software versions.

Conceptual workflow:

``` text
approved SRA/ENA/GEO accessions
 ↓
nf-core/fetchngs
 ↓
validated FASTQ + generated samplesheet
 ↓
nf-core/rnaseq technical QC and library validation
 ↓
Salmon
 ↓
quant.sf
 ↓
transcript-to-gene aggregation
 ↓
gene-level TPM/count estimates
 ↓
Parquet + DuckDB
 ↓
delete FASTQ after validation
```

Use the AFED publication and code as a methodological benchmark. Do not
copy AFED's cluster-specific `sbatch` orchestration when Nextflow already
provides resumability and portable execution. Reused AFED code must
retain its MIT license notice and citation.

STAR may be used as a secondary, explicitly configured route when KOEXA
needs genome-aligned coverage for JBrowse or alignment-derived QC. BAM
files remain temporary. Retain compact coverage such as bigWig only
after validation, then delete BAM safely according to the Storage
Guardian rules.

Do not hard-code assumptions about paired-end versus single-end
libraries.

Library orientation must be detected or correctly specified.

Preserve the raw transcript-level `quant.sf` or a compact equivalent if
storage permits; gene-level data are mandatory.

Place Nextflow work files under a dedicated scratch directory. Never run
`nextflow clean` or remove work directories until KOEXA has validated and
registered all required compact outputs for the affected run. A resumed
execution must use the same pinned inputs, parameters, code revision,
and reference or must start a new versioned run.

------------------------------------------------------------------------

# 10. Quality control

QC is mandatory.

There are at least four distinct QC layers.

## 10.1 Technical read QC

Record metrics such as:

-   read count
-   read quality summaries when available
-   adapter/quality concerns
-   unexpectedly short reads
-   library layout consistency

Do not necessarily reject samples merely because of one imperfect
metric; implement configurable rules.

## 10.2 Quantification QC

Record:

-   mapping/assignment rate or equivalent Salmon metrics
-   number/fraction of genes detected
-   library size
-   TPM distribution
-   zero fraction
-   obvious quantification failures

## 10.3 Biological/sample-level QC

After enough samples exist, calculate:

-   sample-sample correlation
-   PCA
-   distance matrix
-   replicate correlation
-   potential outliers
-   suspiciously similar samples
-   samples clustering with unexpected studies/conditions

## 10.4 Replicate QC

Replicates remain separate.

For replicate groups:

-   calculate Pearson and Spearman correlations;
-   calculate PCA distance;
-   identify extreme disagreement;
-   flag rather than automatically delete;
-   preserve all original values;
-   create `replicate_qc_status`.

Do not assume a universal correlation threshold initially.

Create configurable thresholds after inspecting the MVP.

A failed replicate does not imply that all replicates from the condition
should be removed.

------------------------------------------------------------------------

# 11. Handling replicates

Primary matrix:

``` text
gene × individual sample
```

not:

``` text
gene × averaged condition
```

Then create a derived condition-level matrix.

For example:

``` text
condition_aggregates.parquet
```

Possible summaries:

-   median TPM across biological replicates --- preferred robust default
    for atlas summaries;
-   mean TPM;
-   standard deviation;
-   MAD;
-   number of valid replicates.

Example:

``` text
gene
condition_id
n_replicates
median_TPM
mean_TPM
sd_TPM
MAD_TPM
```

Never discard the individual sample matrix.

Technical replicates require separate handling from biological
replicates. If technical replicates should be merged, make that an
explicit documented preprocessing decision rather than silently
averaging them.

------------------------------------------------------------------------

# 12. Canonical AO09 gene identifiers

The project aims to express genes using canonical `AO09...` identifiers.

AO09 is the primary gene key throughout KOEXA. UniProt accessions,
UniProt Entry Names, gene symbols, protein names, and historical aliases
are searchable secondary identifiers and annotations. They must never
replace AO09 as the canonical key.

The supplied UniProt-derived workbook and RIB40 protein FASTA are input
evidence, not automatically authoritative versions of the same gene
catalog. Their AO09 sets must be reconciled against the frozen reference
and differences must be reported. One UniProt Entry may map to more than
one AO09 identifier, so UniProt accessions must not be constrained as a
unique gene key.

Create a mapping table:

``` text
gene_id_mapping.tsv
```

with:

``` text
source_id
source_namespace
source_strain
canonical_AO09_id
mapping_type
mapping_confidence
mapping_method
evidence
reference_version
```

Create an additional annotation table or equivalent database relation:

``` text
gene_external_identifiers
```

with at minimum:

``` text
canonical_gene_id
namespace
external_id
external_name
mapping_type
mapping_confidence
mapping_method
evidence
source_file
source_version
source_checksum
reference_version
```

Supported initial namespaces should include:

``` text
AO09
UniProtKB_accession
UniProtKB_entry_name
gene_symbol
gene_alias
RefSeq
FungiDB
```

Possible mapping types:

``` text
exact
annotation_alias
one_to_one_ortholog
one_to_many
many_to_one
unmapped
ambiguous
```

Never force ambiguous mappings.

For samples from the canonical reference strain, quantification against
the canonical transcriptome should naturally produce canonical IDs.

For other strains, build a separate explicit orthology/mapping workflow
later.

Do not silently treat strain-specific genes as identical to RIB40 genes.

------------------------------------------------------------------------

# 13. Master TPM matrix

Generate:

``` text
matrices/tpm/gene_by_sample_tpm.parquet
matrices/tpm/gene_by_sample_tpm.tsv.gz
```

Shape:

``` text
Gene             SRR01   SRR02   SRR03   ...   SRR850
AO090001000001    23.2    19.7    31.2         25.1
...
```

Only samples meeting the selected atlas QC policy should enter the
default canonical matrix.

Also allow an `all_samples` matrix containing flagged samples for
auditing.

------------------------------------------------------------------------

# 14. Gene-level statistics

Once the canonical matrix exists, calculate per gene:

``` text
gene
n_samples
n_detected
median_TPM
mean_TPM
geometric_mean_TPM
max_TPM
min_TPM
Q05_TPM
Q25_TPM
Q75_TPM
Q95_TPM
MAD
CV
robust_CV
prevalence
max_sample
max_condition
min_sample
min_condition
fold_range
expression_breadth
D_0.5
D_1
D_2
D_3
D_4
cluster
classification
classification_confidence
```

Important:

`min_condition` should be interpreted carefully because zeros may
dominate. Consider also:

``` text
min_detected_condition
lowest_nonzero_condition
```

------------------------------------------------------------------------

# 15. Detection and prevalence

Do not hard-code a final TPM detection threshold without analysis.

Support configurable thresholds, for example:

``` text
TPM > 0
TPM >= 0.1
TPM >= 1
```

Calculate sensitivity analyses.

Define:

\[
Prevalence_i(T)=`\frac{\#\{samples: TPM_i \ge T\}}{N_{valid\ samples}}`{=tex}
\]

Store prevalence for more than one threshold if useful:

``` text
prevalence_TPM_0_1
prevalence_TPM_1
prevalence_TPM_5
```

This will help distinguish stable biological patterns from threshold
artifacts.

------------------------------------------------------------------------

# 16. Tsallis / generalized diversity module

Tsallis is an exploratory analytical layer, not a replacement for
classical statistics.

For each gene (i), across valid samples or conditions:

\[ p\_{ic} = `\frac{x_{ic}}{\sum_c x_{ic}}`{=tex} \]

where (x\_{ic}) is TPM or another explicitly selected abundance measure.

Tsallis entropy:

\[ S_q(i)=`\frac{1-\sum_c p_{ic}^{q}}{q-1}`{=tex} \]

for (q `\neq 1`{=tex}).

At (q=1), use the Shannon limit:

\[ S_1(i)=-`\sum`{=tex}*c p*{ic}`\ln `{=tex}p\_{ic} \]

Also calculate the effective diversity/Hill number:

\[ D_q(i)= `\left`{=tex}(`\sum`{=tex}*c
p*{ic}^{q}`\right`{=tex})^{1/(1-q)} \]

for (q `\neq 1`{=tex}), and:

\[ D_1(i)=`\exp`{=tex}(S_1(i)) \]

Default exploratory q values:

``` text
0.5
1
2
3
4
```

The software must allow arbitrary q values.

Interpretation:

-   high effective diversity: expression broadly distributed;
-   low effective diversity: expression concentrated in a smaller subset
    of samples/conditions.

Do not label high entropy as housekeeping automatically.

A gene can have high breadth but very low abundance.

Therefore classification must jointly consider:

-   abundance
-   prevalence
-   variability
-   generalized diversity
-   condition enrichment

------------------------------------------------------------------------

# 17. Critical issue: sample imbalance across studies/conditions

This is scientifically important.

If one condition has 100 samples and another has 3, gene-centric entropy
across individual samples can be biased toward heavily sampled
conditions.

Therefore implement **two parallel analysis levels**:

### Sample-level

Uses every valid sample.

Useful for raw reproducibility and replicate variability.

### Condition-level

First aggregate biological replicates into condition summaries, then
calculate breadth/entropy across conditions.

This should become the preferred interpretation for condition
specificity.

Store:

``` text
D_q_sample_level
D_q_condition_level
```

Later, additional balanced/resampled analyses may be implemented.

------------------------------------------------------------------------

# 18. Classical specificity metrics

Do not rely on Tsallis alone.

Implement or plan at least one established expression-specificity
metric, such as Tau, alongside:

-   prevalence
-   CV/robust CV
-   entropy/Hill diversity
-   maximum fold enrichment

This provides an important benchmark.

Tsallis-derived metrics should be compared with classical metrics rather
than assumed superior.

------------------------------------------------------------------------

# 19. Clustering

Classification must begin computationally.

Do not manually assign gene classes from arbitrary thresholds as the
first approach.

Create a feature table using appropriately transformed/scaled features
such as:

``` text
log1p(median_TPM)
prevalence
robust_CV
Tau
D_0.5
D_1
D_2
D_3
D_4
Q95/Q50 or another robust dynamic-range measure
```

Avoid redundant highly correlated features when fitting models.

Test multiple unsupervised approaches:

-   hierarchical clustering
-   k-means as baseline
-   Gaussian mixture models
-   HDBSCAN if appropriate

Use internal validation:

-   silhouette
-   BIC/AIC for mixture models where appropriate
-   stability under bootstrap/resampling
-   sensitivity to TPM detection threshold
-   sensitivity to q

Do not choose the method solely because it produces aesthetically
pleasing clusters.

------------------------------------------------------------------------

# 20. Biological class naming

Only after clusters are stable should human-readable names be assigned.

Candidate names:

``` text
constitutive_high
constitutive_medium
constitutive_low
variable
condition_specific
inducible_high
rarely_expressed
broad_low_expression
```

These are provisional.

The computational cluster ID must always be retained independently:

``` text
cluster_id = GMM_04
biological_label = constitutive_high
```

Never overwrite the cluster with the interpretation.

"Housekeeping" should not be assigned purely from expression behavior.

Instead create:

``` text
housekeeping_candidate
```

requiring broad/stable expression plus supporting functional evidence
when available.

------------------------------------------------------------------------

# 21. Condition-specific analysis

Because biological condition is central to the project, implement
summaries allowing:

``` text
gene → conditions with highest expression
gene → conditions with lowest expression
gene → strongest enrichment
gene → breadth across conditions
condition → most characteristic genes
condition → constitutive genes
condition → induced genes
```

Eventually support queries such as:

``` sql
SELECT *
FROM gene_statistics
WHERE prevalence > 0.95
  AND median_TPM > 100
  AND robust_CV < ...
ORDER BY median_TPM DESC;
```

and:

``` sql
SELECT *
FROM condition_gene_summary
WHERE condition_id = 'solid_state_koji_30h'
ORDER BY enrichment DESC;
```

------------------------------------------------------------------------

# 22. Condition ontology / metadata normalization

Public metadata will be messy.

Preserve both:

``` text
original_description
```

and normalized structured fields.

Never discard original wording.

Create controlled vocabularies incrementally.

Example:

``` text
culture_mode:
  - solid_state
  - submerged
  - plate
  - unknown

oxygen_condition:
  - aerobic
  - hypoxic
  - anaerobic
  - unspecified
```

Do not over-normalize conditions that are biologically distinct.

Each normalization must be traceable.

------------------------------------------------------------------------

# 23. Dataset discovery

Implement discovery as a separate phase from download.

Discovery should create candidate records, not automatically launch
massive downloads.

Use official NCBI/ENA APIs as authoritative sources. `pysradb` and
`ffq` may resolve and enrich accessions, but raw responses and query
parameters must be preserved because upstream APIs and metadata can
change. Discovery must be reproducible and timestamped.

Workflow:

``` text
DISCOVER
   ↓
STORE METADATA
   ↓
REVIEW
   ↓
APPROVE
   ↓
QUEUE
   ↓
PROCESS
```

Before approving downloads, generate a KOEXA discovery report containing
at minimum:

-   query date, source APIs, exact queries, and tool versions;
-   counts of BioProjects/studies, experiments, BioSamples, and runs;
-   explicit distinction between a sequencing run and a biological
    sample;
-   RNA-seq strategy, source, selection, platform, and library layout;
-   strain, condition text, treatment, medium, time, and replicate clues;
-   read/base counts and estimated download volume when available;
-   availability of FASTQ or recoverable SRA data;
-   duplicate GEO/SRA/ENA relationships;
-   metadata completeness and unresolved fields;
-   AO09/RIB40 reference compatibility risk;
-   proposed `RECOMMENDED_MVP`, `REQUIRES_REVIEW`, or `EXCLUDE` status;
-   a documented reason for every inclusion and exclusion.

Export both human- and machine-readable results:

``` text
reports/discovery/discovery_<date>.md
reports/discovery/discovery_<date>.html
reports/discovery/studies.tsv
reports/discovery/samples.tsv
reports/discovery/runs.tsv
reports/discovery/exclusions.tsv
reports/discovery/raw_api_responses/
```

For MVP, manually approve a small representative set.

Aim for diversity:

-   submerged
-   solid-state
-   different carbon sources
-   stress
-   different growth phases/time points
-   secretion/production contexts
-   different strains only when mapping is manageable

------------------------------------------------------------------------

# 24. MVP --- KOEXA first layer

Do not start with the full public universe.

The MVP is an *Aspergillus oryzae* adaptation of the useful AFED first
layer. It is not yet the final statistical classification atlas.

MVP target:

-   canonical reference validated;
-   2--5 public studies;
-   approximately 20--40 samples;
-   multiple biological conditions;
-   biological replicates;
-   at least one time-course if practical.

MVP must demonstrate:

1.  reproducible discovery and a transcriptome inventory report;
2.  manual study/sample approval;
3.  metadata and structured condition storage;
4.  AO09 canonical genes with UniProt and alias search;
5.  `nf-core/fetchngs` acquisition for approved accessions;
6.  `nf-core/rnaseq` QC and Salmon quantification;
7.  storage safety and safe deletion after validation;
8.  interruption followed by successful Nextflow/KOEXA resume;
9.  sample-level gene TPM matrix;
10. basic replicate QC;
11. KOEXA gene-expression barplot with sample metadata;
12. KOEXA heatmap and PCA views;
13. downloadable expression and metadata tables;
14. visible sample QC and inclusion/exclusion status.

AFED-equivalent co-expression and JBrowse are the next KOEXA feature
milestone. Tsallis/Hill metrics, specificity, clustering, and biological
class naming begin only after this first layer passes tests and its data
are reviewed.

Do not scale until the MVP passes tests.

------------------------------------------------------------------------

# 25. CLI

Create a simple command-line interface.

Desired conceptual commands:

``` bash
atlas init
atlas doctor
atlas reference validate

atlas dataset add <accession>
atlas dataset discover ...
atlas dataset list
atlas discovery report
atlas discovery export

atlas sample approve <SRR>
atlas sample queue <SRR>

atlas fetch approved
atlas process next
atlas process batch --n 3
atlas pause
atlas resume

atlas status
atlas storage status
atlas storage clean

atlas qc sample <SRR>
atlas qc replicates

atlas matrix build
atlas app serve

atlas stats genes
atlas entropy genes
atlas cluster genes

atlas report build
```

Exact syntax may change if there is a cleaner implementation.

The user-facing launcher on Windows should be:

``` powershell
.\run_atlas.ps1
```

It should expose the KOEXA console and local application without
requiring the user to remember Nextflow commands. Under the hood,
commands must save the pinned `nf-core` release and the exact Nextflow
command. Long-running workflows must support graceful interruption and
resume.

`atlas status` should show:

``` text
Samples discovered:   ...
Approved:             ...
Queued:               ...
Processing:           ...
Archived:             ...
QC failed:            ...
Excluded:             ...

Disk free:            ...
Scratch usage:        ...
Current sample:       ...
Next resumable step:  ...
Nextflow run/session: ...
KOEXA app:             ...
```

------------------------------------------------------------------------

# 26. Logging and provenance

For every sample store:

-   source accession
-   download date
-   source URL/API/repository identifier
-   reference version
-   index version
-   software versions
-   command line used
-   relevant parameters
-   library type
-   start/end timestamps
-   exit status
-   QC metrics
-   final status
-   raw deletion status

Create machine-readable manifests.

A future user must be able to answer:

> Exactly how was TPM for AO090... in SRR... generated?

------------------------------------------------------------------------

# 27. Failure handling

Failures are expected.

Examples:

-   download interrupted
-   corrupted FASTQ
-   metadata incomplete
-   Salmon failure
-   low assignment rate
-   disk full
-   sample mislabeled
-   incompatible library
-   missing mate
-   invalid reference mapping

A failed sample must not corrupt the database.

Use atomic writes/transactions where appropriate.

Temporary files should use clearly marked incomplete names or
directories.

A successful sample should never be reprocessed accidentally.

------------------------------------------------------------------------

# 28. Tests

Implement automated tests early.

At minimum:

## Unit tests

-   state transitions
-   storage checks
-   safe deletion
-   metadata parsing
-   condition serialization
-   AO09 validation and AO09/UniProt one-to-many mapping
-   discovery accession normalization and run/sample distinction
-   TPM import
-   transcript-to-gene aggregation
-   entropy formulas
-   (q=1) Shannon limit
-   Hill numbers
-   prevalence
-   replicate aggregation
-   KOEXA application queries against a small fixture database

## Integration tests

Use tiny synthetic or intentionally small test data.

Test:

``` text
download/mock
→ quantify/mock
→ validate
→ database
→ cleanup
→ matrix
→ statistics
```

Include a mocked or tiny Nextflow execution that is interrupted and
successfully resumed without re-running its completed task. Test that a
workflow revision or material parameter mismatch cannot silently reuse
an incompatible run.

## Safety test

Explicitly test that raw files are **not deleted** when:

-   quantification fails;
-   output is empty;
-   database write fails;
-   QC validation fails in a way configured to preserve raw data.

------------------------------------------------------------------------

# 29. Reproducible environments

Prefer a reproducible environment specification.

Possible options:

-   WSL2 + Docker Desktop for Nextflow/nf-core on the current Windows
    workstation;
-   pinned Docker/Apptainer containers selected by nf-core profiles;
-   Conda/Mamba only where containers are impractical;
-   a native Python environment for the lightweight KOEXA CLI when useful.

Record exact versions of:

-   Python
-   Salmon
-   SRA Toolkit
-   QC tools
-   DuckDB
-   pandas/polars
-   scipy
-   scikit-learn
-   plotting dependencies

Do not make Docker mandatory for the first MVP if it makes development
unnecessarily difficult on the user's machine.

------------------------------------------------------------------------

# 30. Performance guidelines for a modest PC

Default to:

``` text
max_parallel_samples = 1
```

Allow configuration later.

Prefer:

-   streaming/chunked operations;
-   Parquet;
-   DuckDB queries;
-   compact matrices;
-   sparse representation where useful;
-   avoiding large in-memory copies;
-   avoiding BAM unless scientifically required;
-   processing one sample at a time.

Before operations that may require substantial RAM/disk, estimate
resource use when possible.

------------------------------------------------------------------------

# 31. Outputs

Core outputs:

``` text
atlas.duckdb

discovery_report.md
discovery_studies.tsv
discovery_samples.tsv
discovery_runs.tsv

gene_by_sample_tpm.parquet
gene_by_sample_tpm.tsv.gz

gene_by_condition_median_tpm.parquet

gene_statistics.parquet
gene_statistics.tsv.gz

sample_metadata.parquet
condition_metadata.parquet

sample_qc.parquet
replicate_qc.parquet

gene_entropy.parquet
gene_clusters.parquet

aoed_release_manifest.json
```

KOEXA version 0.1 also delivers a runnable local interactive application
with gene search, expression barplots, sample metadata/QC, heatmaps,
PCA, and table downloads. Application views are derived from versioned
database exports and must display the release/reference version.

Desired gene-statistics view:

``` text
gene
median_TPM
prevalence
CV
robust_CV
D_0.5
D_1
D_2
D_3
D_4
Tau
max_condition
min_detected_condition
cluster
classification
classification_confidence
```

------------------------------------------------------------------------

# 32. Initial visualizations

After MVP, automatically generate:

1.  samples per study;
2.  samples per condition;
3.  library-size distribution;
4.  genes detected per sample;
5.  sample correlation heatmap;
6.  PCA;
7.  replicate correlation plot;
8.  median TPM distribution;
9.  prevalence distribution;
10. median TPM vs prevalence;
11. robust CV vs median TPM;
12. (D_2) vs median TPM;
13. Tau vs (D_2);
14. cluster feature heatmap;
15. number of genes per cluster;
16. q-profile examples for representative genes.

Visualizations are derived outputs. Never modify primary data to make
plots cleaner.

------------------------------------------------------------------------

# 33. Future extensions

Design interfaces so these can be added later without rewriting the
ingestion engine:

## Annotation

-   GO
-   KEGG
-   Pfam
-   InterPro
-   signal peptides
-   secretion
-   transcription factors
-   CAZymes
-   ribosomal genes

## GEM

Map:

``` text
AO09 gene
→ GPR
→ reaction
```

and annotate reactions with:

-   expression breadth
-   median expression
-   variability
-   condition specificity
-   cluster

Do not impose flux constraints in the current project.

## Proteomics

Future paired transcriptome/proteome layer.

## Promoter mining

Use constitutive-high or condition-specific genes to nominate promoters.

## Literature layer

Attach publications and evidence to genes/conditions.

## Interface

The KOEXA interface is part of the first product layer, not a distant
extension. Begin from the MIT-licensed AFED Shiny implementation or
reproduce its behavior with a justified alternative. The initial local
interface must prioritize:

-   AO09/UniProt/name/alias gene search;
-   per-gene TPM barplots across samples;
-   BioProject and structured-condition filters;
-   click-through sample metadata and QC;
-   multi-gene heatmaps;
-   PCA;
-   downloadable expression and metadata tables.

Add co-expression, enrichment, and JBrowse after the basic KOEXA views
are validated. Public hosting, user accounts, and production-scale web
operations remain future work.

------------------------------------------------------------------------

# 34. Scientific cautions

The implementation and documentation must explicitly recognize:

1.  TPM is compositional/relative.
2.  TPM values from different samples can be useful for atlas-style
    exploratory comparisons but require careful interpretation.
3.  Batch effects across studies are unavoidable.
4.  The same processing pipeline reduces technical heterogeneity but
    does not remove biological/study batch effects.
5.  Library preparation and sequencing technology must be retained as
    metadata.
6.  Entropy can be biased by unequal sampling of conditions.
7.  High expression breadth does not prove housekeeping function.
8.  Low expression does not imply biological irrelevance.
9.  RNA abundance does not equal protein abundance or metabolic flux.
10. Different *A. oryzae* strains may contain genuine genomic
    differences.
11. Ambiguous gene mappings must remain ambiguous.
12. Clusters are statistical constructs; biological labels are
    interpretations.

------------------------------------------------------------------------

# 35. Batch/study effects

Do not apply an aggressive batch-correction method to the canonical TPM
matrix by default.

Keep:

``` text
RAW_CANONICAL_PROCESSED_MATRIX
```

immutable.

If batch correction is explored later, create derived matrices:

``` text
matrix_batch_corrected_method_X
```

with explicit method/version.

The primary atlas should always allow return to the uncorrected
consistently processed values.

------------------------------------------------------------------------

# 36. Data immutability

Primary imported/processed measurements should be append-only where
practical.

Corrections should create new pipeline/reference versions rather than
silently replacing history.

Example:

``` text
pipeline_version = 0.1.0
reference_version = RIB40_v1
```

If reference changes:

``` text
reference_version = RIB40_v2
```

Affected samples can be queued for reprocessing.

------------------------------------------------------------------------

# 37. First implementation milestones

## Milestone 0 --- Repository and runnable KOEXA shell

-   create project structure, environment, configuration, and logging;
-   create `run_atlas.ps1`, `atlas doctor`, `atlas status`, and CLI
    skeleton;
-   pin Nextflow/nf-core execution strategy without downloading large
    datasets;
-   add tests and decision records;
-   audit the AFED repository, license, interface, and processing
    assumptions.

## Milestone 1 --- AO09 and UniProt reconciliation

-   inspect the supplied UniProt-derived workbook and RIB40 protein
    FASTA;
-   calculate checksums and structural validation reports;
-   identify exact, missing, duplicated, one-to-many, and ambiguous
    AO09/UniProt relationships;
-   design `genes` and `gene_external_identifiers`;
-   do not declare either local file the canonical reference until the
    reference-version comparison is complete.

## Milestone 2 --- Public transcriptome discovery report

-   query NCBI/ENA and resolve GEO/SRA relationships;
-   preserve raw responses, queries, dates, and tool versions;
-   distinguish studies, experiments, biological samples, and runs;
-   estimate download volume;
-   characterize strains, conditions, layouts, replicates, and metadata
    completeness;
-   generate the human- and machine-readable KOEXA discovery report;
-   propose, but do not automatically approve, the first studies.

## Milestone 3 --- Canonical RIB40 reference

-   obtain and validate matching genome, annotation, nucleotide
    transcriptome, protein FASTA, and transcript-to-gene mapping;
-   document accessions, versions, sources, and checksums;
-   verify AO09 identifiers and reconcile them with Milestone 1;
-   build the Salmon reference/index with a pinned workflow;
-   stop and report if AO09/reference assumptions remain unclear.

## Milestone 4 --- Database, state, and storage safety

-   create DuckDB schema and migrations;
-   implement study/sample/condition/identifier/provenance models;
-   implement KOEXA state tracking around Nextflow task state;
-   monitor disk and isolate scratch/work directories;
-   implement graceful pause, restart recovery, and safe cleanup tests;
-   ensure `-resume` inputs and session provenance are preserved.

## Milestone 5 --- One sample end-to-end

Process exactly one manually approved public RNA-seq sample:

``` text
approved accession
→ nf-core/fetchngs
→ validated FASTQ
→ nf-core/rnaseq QC
→ Salmon
→ AO09 gene TPM
→ DuckDB/Parquet
→ compact validated files
→ safe raw/intermediate cleanup
```

Interrupt and resume at least one dry-run or controlled execution before
declaring this milestone complete.

## Milestone 6 --- One replicated condition

-   process one study with biological replicates;
-   curate structured condition metadata;
-   retain sample-level expression;
-   implement basic replicate QC and condition aggregation;
-   confirm sample/run/technical-replicate distinctions.

## Milestone 7 --- KOEXA basic interface

Adapt the AFED user experience for *A. oryzae*:

-   AO09/UniProt/name/alias gene search;
-   per-gene TPM barplot across samples;
-   BioProject and condition filters;
-   sample metadata and QC inspection;
-   heatmap;
-   PCA;
-   downloadable matrices and metadata.

This milestone, together with Milestones 0--6, defines KOEXA version
0.1.

## Milestone 8 --- KOEXA scale-up and AFED-equivalent extensions

-   expand to 20--40 reviewed samples, then to additional approved
    public studies in controlled batches;
-   add co-expression and functional enrichment;
-   add STAR-derived compact coverage and JBrowse only if storage tests
    pass;
-   publish a data/QC/limitations report.

## Milestone 9 --- Gene statistics

Implement abundance, prevalence, variability, specificity, and
condition-enrichment metrics on the validated KOEXA matrix.

## Milestone 10 --- Tsallis/Hill

Implement and unit-test generalized entropy/diversity. Compare
sample-level and condition-level calculations and assess sampling
imbalance.

## Milestone 11 --- Clustering and biological interpretation

Benchmark clustering methods, retain computational cluster IDs, and
assign cautious biological labels only after stability review.

## Milestone 12 --- Advanced KOEXA report

Generate a versioned report describing datasets, conditions, QC,
replicates, TPM atlas, gene statistics, entropy, clusters, limitations,
promoter candidates, and the recommended scaling plan.

------------------------------------------------------------------------

# 38. Codex workflow rules

When implementing:

1.  Read this complete specification.
2.  Inspect repository state before modifying anything.
3.  Maintain a `TODO.md`.
4.  Work milestone-by-milestone.
5.  Do not jump ahead to visualization/AI features before ingestion is
    safe.
6.  Run tests after meaningful changes.
7.  Document important design decisions in `docs/decisions/`.
8.  Ask for user input when a biological choice cannot be made safely.
9.  Never fabricate accessions or metadata.
10. Never start large downloads without explicit approval during early
    development.
11. Prefer small dry-runs.
12. Report disk estimates before scaling.
13. Keep commands reproducible.
14. Keep scientific calculations in tested functions, not only
    notebooks.
15. Notebooks are for exploration and reporting, not the sole
    implementation.

------------------------------------------------------------------------

# 39. Definition of success for version 0.1

Version 0.1 is successful when the user can run the platform on a modest
computer and:

1.  generate a reproducible inventory of public *A. oryzae* RNA-seq;
2.  review and approve studies and samples before download;
3.  preserve study/sample/condition/replicate metadata;
4.  use AO09 as the canonical gene ID and search by UniProt/name/alias;
5.  process approved samples sequentially with pinned nf-core releases;
6.  automatically prevent unsafe disk usage;
7.  quantify against the canonical AO09-compatible reference;
8.  perform and expose QC;
9.  safely delete large raw/intermediate files after validation;
10. resume successfully after an interruption or PC restart;
11. inspect sample and workflow status;
12. generate a gene × sample TPM matrix;
13. aggregate biological replicates without losing individual samples;
14. use a local KOEXA interface to view gene TPM barplots and metadata;
15. create heatmaps and PCA from selected valid samples;
16. export expression and metadata tables;
17. trace every TPM value back to its source accession, reference,
    software, pipeline version, and processing event.

Gene-level Tsallis/Hill diversity, computational clustering, and
biological class naming are version 0.2 analytical goals. They are not
required to declare the KOEXA acquisition and expression layer usable.

------------------------------------------------------------------------

# 40. Immediate task for Codex

Do **not** implement the entire platform in one pass.

Start by:

1.  reviewing this specification;
2.  auditing the AFED article, MIT-licensed repository, data model,
    interface, and reusable components;
3.  proposing the exact KOEXA repository architecture and local launcher;
4.  creating the repository skeleton, tests, `run_atlas.ps1`, and CLI
    needed for Milestone 0;
5.  auditing the supplied AO09/UniProt workbook and protein FASTA and
    generating the Milestone 1 reconciliation report;
6.  implementing discovery without downloading reads;
7.  producing the dated KOEXA public-transcriptome inventory required by
    Milestone 2;
8.  identifying uncertain biological/technical assumptions and
    proposing the first manually reviewed study set;
9.  proposing the canonical *A. oryzae* RIB40 reference strategy without
    inventing identifiers;
10. designing DuckDB, Nextflow integration, resume, and storage safety
    for the next approved implementation step.

Before downloading RNA-seq reads, present the discovery report,
estimated storage requirements, candidate studies, reference decision,
and exact pinned workflow plan, then wait for approval. Reference files
and tiny workflow test data also require explicit, clearly scoped
commands but are not to be confused with bulk sample acquisition.

------------------------------------------------------------------------

# 41. Guiding idea

The platform is fundamentally a reusable data engine:

``` text
PUBLIC RNA-seq
      ↓
reproducible discovery and manual approval
      ↓
nf-core acquisition + standardized processing
      ↓
quality-controlled AO09/UniProt expression
      ↓
KOEXA first layer: metadata + plots + heatmaps + PCA + downloads
      ↓
compact permanent atlas and advanced analytical layer
      ↓
┌──────────────┬──────────────┬──────────────┐
│ statistics   │ entropy      │ clustering   │
├──────────────┼──────────────┼──────────────┤
│ conditions   │ promoters    │ future GEM   │
└──────────────┴──────────────┴──────────────┘
```

The most valuable output is not any single classification.

It is the quality-controlled, traceable, condition-aware expression
compendium that allows many future questions to be asked without
repeatedly downloading and processing the raw RNA-seq data.

------------------------------------------------------------------------

# 42. AFED reference implementation and KOEXA relationship

KOEXA version 0.1 is explicitly inspired by:

> Brian M. Mack and Matthew D. Lebar. AFED, a comprehensive resource for
> *Aspergillus flavus* gene expression profiling. *Database*, 2025,
> baaf033. https://doi.org/10.1093/database/baaf033

Reference implementation:

``` text
https://github.com/kcamnairb/a_flavus_expression_db
```

The AFED repository is published under the MIT license. Any KOEXA source
file substantially derived from AFED must preserve the required license
and copyright notice. KOEXA documentation and publications must cite the
AFED article and clearly distinguish reused, adapted, and newly developed
components.

KOEXA is not merely a renamed AFED deployment. It changes the organism,
reference, canonical identifier system, metadata ontology, processing
orchestration, storage constraints, and downstream scientific scope.
The AFED interface and scientific workflow define the first-layer
product benchmark; AO09/UniProt reconciliation, Nextflow/nf-core
execution, resumability, storage safety, condition-level analysis, and
advanced atlas analytics are KOEXA-specific requirements.
