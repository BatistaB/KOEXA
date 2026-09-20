-- Initial DuckDB schema (PROJECT_MASTER_SPEC.md section 8, Milestone 4).
-- sample_qc/processing_events/gene_expression are long-format tables per
-- the spec's own performance guidance (section 30: prefer long/compact
-- representations over wide per-sample columns).

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id          TEXT PRIMARY KEY,
    bioproject          TEXT,
    geo_accession       TEXT,
    publication_doi     TEXT,
    publication_title   TEXT,
    organism            TEXT,
    strain              TEXT,
    study_description   TEXT,
    source_repository   TEXT,
    discovery_date      TEXT,
    metadata_status     TEXT,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS conditions (
    condition_id            TEXT PRIMARY KEY,
    condition_label         TEXT,
    strain                  TEXT,
    medium                  TEXT,
    culture_mode             TEXT,
    carbon_source            TEXT,
    nitrogen_source          TEXT,
    substrate                TEXT,
    temperature_C            DOUBLE,
    pH                       DOUBLE,
    time_value               DOUBLE,
    time_unit                TEXT,
    stress                   TEXT,
    treatment                TEXT,
    oxygen_condition         TEXT,
    developmental_stage      TEXT,
    recombinant_background   TEXT,
    production_context       TEXT,
    original_description     TEXT,
    metadata_confidence      TEXT,
    metadata_source          TEXT
);

-- sample_id = run_accession (SRR/DRR/ERR...): the finest granularity
-- actually processed by nf-core/rnaseq, one row per sequencing run
-- (spec section 8: "One row per SRR/run or canonical biological sample
-- unit"). Biological-replicate grouping lives in replicate_group/
-- condition_id, never collapsed into this table (AGENTS.md: never average
-- biological replicates during ingestion).
CREATE TABLE IF NOT EXISTS samples (
    sample_id            TEXT PRIMARY KEY,
    run_accession        TEXT,
    biosample            TEXT,
    experiment_accession TEXT,
    bioproject           TEXT,
    geo_sample           TEXT,
    strain               TEXT,
    condition_id         TEXT,
    replicate_group      TEXT,
    biological_replicate TEXT,
    technical_replicate  TEXT,
    library_layout       TEXT,
    library_strategy     TEXT,
    library_source       TEXT,
    read_length          BIGINT,
    read_count           BIGINT,
    download_size        BIGINT,
    pipeline_status      TEXT,
    qc_status            TEXT,
    quant_status         TEXT,
    reference_version    TEXT,
    pipeline_version     TEXT,
    raw_deleted          BOOLEAN DEFAULT FALSE,
    exclusion_reason     TEXT,
    created_at           TIMESTAMP,
    updated_at           TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genes (
    canonical_gene_id   TEXT PRIMARY KEY,
    gene_symbol         TEXT,
    gene_name           TEXT,
    chromosome          TEXT,
    start               BIGINT,
    "end"               BIGINT,
    strand              TEXT,
    biotype             TEXT,
    description         TEXT,
    reference_version   TEXT
);

CREATE TABLE IF NOT EXISTS gene_external_identifiers (
    canonical_gene_id   TEXT,
    namespace           TEXT,
    external_id         TEXT,
    external_name       TEXT,
    mapping_type        TEXT,
    mapping_confidence  TEXT,
    mapping_method      TEXT,
    evidence            TEXT,
    source_file         TEXT,
    source_version      TEXT,
    source_checksum     TEXT,
    reference_version   TEXT
);

CREATE TABLE IF NOT EXISTS sample_qc (
    sample_id           TEXT,
    metric_name         TEXT,
    metric_value        DOUBLE,
    qc_tool             TEXT,
    qc_tool_version     TEXT,
    created_at          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS processing_events (
    event_id            BIGINT,
    sample_id           TEXT,
    event_type          TEXT,
    event_detail        TEXT,
    pipeline_version    TEXT,
    created_at          TIMESTAMP
);

-- Long format (spec section 8): one row per (sample, gene), not a wide
-- sample-by-gene matrix -- wide matrices are exported separately for
-- users (matrices/*.parquet), this table is the queryable source of truth.
CREATE TABLE IF NOT EXISTS gene_expression (
    sample_id           TEXT,
    canonical_gene_id   TEXT,
    TPM                 DOUBLE,
    estimated_counts    DOUBLE,
    effective_length    DOUBLE
);
