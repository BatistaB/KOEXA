-- Study enrichment (paper + short summary) and per-sample tags, derived
-- from metadata/study_annotations/*.json and metadata/sample_tag_vocabulary.tsv
-- by aoryzae_atlas.annotation.ingest (truncate-and-reload, like conditions).
-- Tag provenance (source/confidence/note) is kept here even though the UI
-- only shows the tag name.

CREATE TABLE IF NOT EXISTS tag_vocabulary (
    tag          TEXT PRIMARY KEY,
    category     TEXT,
    description  TEXT,
    synonyms     TEXT
);

CREATE TABLE IF NOT EXISTS study_annotations (
    bioproject              TEXT PRIMARY KEY,
    paper_status            TEXT,
    paper_title             TEXT,
    paper_authors           TEXT,
    paper_year              INTEGER,
    paper_journal           TEXT,
    paper_doi               TEXT,
    paper_pmid              TEXT,
    paper_pmcid             TEXT,
    paper_url               TEXT,
    paper_access            TEXT,
    association_evidence    TEXT,
    objective               TEXT,
    experimental_design     TEXT,
    main_finding            TEXT,
    related_identifiers     TEXT,   -- JSON object
    notes                   TEXT,   -- JSON array
    curated_by              TEXT,
    curated_at              TEXT,
    source_file             TEXT
);

CREATE TABLE IF NOT EXISTS sample_tags (
    sample_id    TEXT,
    bioproject   TEXT,
    tag          TEXT,
    category     TEXT,
    source       TEXT,
    confidence   TEXT,
    note         TEXT,
    PRIMARY KEY (sample_id, tag)
);
