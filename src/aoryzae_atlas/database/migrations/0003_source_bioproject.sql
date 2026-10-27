-- Provenance for grouped studies (aoryzae_atlas.database.study_groups).
-- `samples.bioproject` is the study key everything downstream groups by; for a
-- sample in a study group it holds the group's study_id, so the accession the
-- run was actually deposited under is kept here. For every other sample the
-- two columns are equal.

ALTER TABLE samples ADD COLUMN IF NOT EXISTS source_bioproject VARCHAR;
UPDATE samples SET source_bioproject = bioproject WHERE source_bioproject IS NULL;
