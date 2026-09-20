"""Public transcriptome discovery (Milestone 2, PROJECT_MASTER_SPEC.md section 23).

Discovery is a separate phase from download: this package only queries
public metadata APIs and writes candidate records under reports/discovery/.
Nothing here downloads FASTQ/SRA data or approves samples for processing.
"""
