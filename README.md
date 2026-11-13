# KOEXA — KOji EXpression Atlas

**A public, reproducible RNA-seq expression atlas for *Aspergillus oryzae*.**

KOEXA gathers public *A. oryzae* RNA-seq experiments, reprocesses every
sample against one reference (RIB40, FungiDB v71) with one pipeline, curates
the biological conditions of each sample by hand, and serves the result as a
searchable web atlas and as downloadable expression matrices.

> **Try it:** <https://koexa-preview.koexa-atlas.workers.dev>
> &nbsp;·&nbsp; **Downloads:** <https://koexa-preview.koexa-atlas.workers.dev/downloads>
>
> No login or installation required. This is a **test preview**: the data
> and the interface may still change between releases.

---

## What is in the atlas

| | |
|---|---|
| Genes | **12,078** (canonical AO09 identifiers, *A. oryzae* RIB40) |
| Sequencing runs | **433** |
| Independent biological samples | **423** |
| Studies (BioProjects) | **29** |
| Strains | **37** (RIB40 and other industrial and natural isolates) |
| Reference | RIB40 assembly `GCF_000184455.2`, FungiDB release 71 annotation (`RIB40_v1`) |

In the web app you can:

- search a gene by AO09 ID, symbol, name, alias or UniProt accession;
- see its expression (TPM) in every sample, grouped by study and condition,
  with filters for strain and condition;
- see its global expression class (e.g. *Constitutive Core*,
  *Context-Specific*, *Rare/Silent*), derived from the whole atlas;
- browse a chromosome-wide expression map of the 8 RIB40 chromosomes;
- restrict the views to curated gene sets (e.g. the secretome);
- read, for each study, its paper, a short design summary and the
  sample-level tags.

## Downloading the data

Everything the web app shows can be downloaded from the
[downloads page](https://koexa-preview.koexa-atlas.workers.dev/downloads).

| File | Content |
|---|---|
| `expression_tpm.bin` | Gene × sample matrix of TPM (~20 MB) |
| `expression_counts.bin` | Gene × sample matrix of Salmon estimated counts (~20 MB) |
| `expression_index.json` | Row order (`genes`) and column order (`samples`) of both matrices |
| `genes.json` | Gene catalogue: AO09 ID, symbol, name, aliases, UniProt |
| `samples.json` | One row per run: study, BioSample, strain, condition, replicate |
| `conditions.json` | Curated conditions: medium, culture mode, time, temperature, treatment… |
| `datasets.json` | Studies (BioProjects) |
| `sample_qc.json` | Per-sample QC (reads, Q30, duplication, assigned fraction) |
| `study_annotations.json` | Paper, design summary and tags per study |
| `expression_rank.json`, `classification.json` | Global expression class and scores of each gene |

The two `.bin` matrices are **little-endian float32, row-major, one row per
gene** (12,078 rows × 433 columns, in the order of `expression_index.json`).
A gene/sample pair with no quantification is stored as 0.

<details>
<summary><b>Python</b></summary>

```python
import json
import numpy as np
import pandas as pd

index = json.load(open("expression_index.json"))
tpm = np.fromfile("expression_tpm.bin", dtype="<f4").reshape(
    len(index["genes"]), len(index["samples"])
)
tpm = pd.DataFrame(tpm, index=index["genes"], columns=index["samples"])
samples = pd.DataFrame(json.load(open("samples.json")))
```
</details>

<details>
<summary><b>R</b></summary>

```r
library(jsonlite)
index <- fromJSON("expression_index.json")
con <- file("expression_tpm.bin", "rb")
v <- readBin(con, "numeric", size = 4, endian = "little",
             n = length(index$genes) * length(index$samples))
close(con)
tpm <- matrix(v, nrow = length(index$genes), byrow = TRUE,
              dimnames = list(index$genes, index$samples))
```
</details>

**Replicates are never averaged.** Each run is its own column; the
replicate structure is in `samples.json` (`condition_id`, `biological_replicate`,
`biosample`). Runs that share a BioSample are technical replicates of one
biological sample.

## How the data is produced

```
SRA/ENA discovery ─► manual approval ─► download + QC + quantification ─► curation ─► atlas
 (metadata only)      (per run)          fastp → Salmon 1.10.1            conditions,  expression classes,
                                         (decoy-aware, RIB40_v1)          papers, tags co-expression, web
```

1. **Discovery** — `atlas discovery report` searches the SRA for
   *A. oryzae* RNA-seq (metadata only, nothing is downloaded).
2. **Approval** — every run is approved by hand (`atlas sample approve`)
   after checking organism, library type and design.
3. **Quantification** — FASTQs are fetched from ENA (MD5-checked), trimmed
   with fastp and quantified with Salmon against a decoy-aware RIB40 index
   ([`workflows/colab_pantranscriptome.ipynb`](workflows/colab_pantranscriptome.ipynb)).
   Raw reads are deleted once the results are validated.
4. **Curation** — each sample gets a curated condition
   ([`metadata/conditions.tsv`](metadata/conditions.tsv)) and each study a
   paper link, summary and tags
   ([`metadata/study_annotations/`](metadata/study_annotations/)). Unknown
   values stay unknown; nothing is guessed.
5. **Analysis and export** — `atlas refresh` reloads the database, ingests
   the quantifications, recomputes the expression classes and the
   co-expression network (summaries in `analysis/`), and exports the web data.

Design decisions are recorded in [`docs/decisions/`](docs/decisions/); the
full specification is [`PROJECT_MASTER_SPEC.md`](PROJECT_MASTER_SPEC.md).

## Running it locally

### Just the web app, with the published data

Requires [Node.js](https://nodejs.org/) 20.19+ or 22.12+.

```bash
git clone https://github.com/BatistaB/KOEXA.git
cd KOEXA/app/web
npm install

# download the published data files into public/data/
BASE=https://koexa-preview.koexa-atlas.workers.dev/data
mkdir -p public/data
for f in chromosome_expression classification conditions datasets expression_index \
         expression_rank gene_sets genes sample_qc samples study_annotations; do
  curl -sSf -o public/data/$f.json $BASE/$f.json
done
for f in expression_tpm expression_counts; do
  curl -sSf -o public/data/$f.bin $BASE/$f.bin
done

npm run dev        # then open the address it prints (usually http://localhost:5173)
```

The data files (~50 MB) are not stored in git: they are generated and are
rebuilt by the pipeline on every refresh.

### The full pipeline

Requires Python 3.10+. The command-line tool is `atlas`.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
atlas doctor                       # environment checks
atlas status                       # pipeline status
atlas --help                       # all commands
```

On Windows, `.\run_atlas.ps1 <command>` creates the virtual environment on
first use. Rebuilding the database from scratch needs the reference files
(see [`database/FungiDB_v71/PROVENANCE.md`](database/FungiDB_v71/PROVENANCE.md))
and the per-sample quantifications, which are not stored in git.

## Repository layout

| Path | Content |
|---|---|
| `src/aoryzae_atlas/` | Python package and `atlas` CLI |
| `metadata/` | Curated tables: samples, conditions, gene identifiers, tag vocabulary, study annotations |
| `config/` | Pinned reference and pipeline configuration |
| `workflows/` | Colab quantification notebook and ingestion script |
| `analysis/` | Summaries of the expression classes and the co-expression network |
| `notebooks/` | Exploratory notebooks (classification, co-expression, secretome) |
| `app/web/` | React + TypeScript web app |
| `reports/` | Discovery reports and study evidence |
| `docs/decisions/` | Architecture and design decisions |
| `tests/` | Test suite (`pytest`) |

## Acknowledgements

KOEXA is inspired by [AFED](https://github.com/kcamnairb/a_flavus_expression_db),
the *Aspergillus flavus* Expression Database (Mack & Lebar, *Database*, 2025,
[doi:10.1093/database/baaf033](https://doi.org/10.1093/database/baaf033), MIT
license). Any component substantially derived from AFED keeps its license
notice and is identified in the code and in
[`docs/decisions/0002-afed-audit.md`](docs/decisions/0002-afed-audit.md).

All expression data come from public experiments deposited in NCBI SRA, ENA
and DDBJ. Please cite the original studies (listed per study in the atlas)
along with KOEXA.
