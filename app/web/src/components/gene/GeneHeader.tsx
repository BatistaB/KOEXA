import type { Gene } from "../../data/types";
import { isSymbolicLabel, primaryGeneLabel } from "../../lib/geneDisplay";
import "./GeneHeader.css";

export function GeneHeader({ gene }: { gene: Gene }) {
  const symbolic = isSymbolicLabel(gene);
  const primary = primaryGeneLabel(gene);
  const showNameLine = symbolic && !!gene.gene_name && gene.gene_name !== primary;

  return (
    <div className="gene-header">
      <div className="gene-header__top">
        <span className={symbolic ? "gene-header__symbol" : "gene-header__symbol gene-header__symbol--plain"}>
          {primary}
        </span>
        {showNameLine && <span className="gene-header__name">{gene.gene_name}</span>}
        <span className="gene-header__id mono">{gene.canonical_gene_id}</span>
      </div>

      <div className="gene-header__meta">
        <span>
          {gene.chromosome.replace("_A_oryzae_RIB40", "")}:{gene.start.toLocaleString("en-US")}
          –{gene.end.toLocaleString("en-US")} ({gene.strand === "+" ? "+ strand" : "− strand"})
        </span>
        <span className="gene-header__meta-sep">·</span>
        <span className="gene-header__tag">{gene.biotype}</span>
        {gene.uniprot_accession && (
          <>
            <span className="gene-header__meta-sep">·</span>
            <span>UniProt {gene.uniprot_accession}</span>
          </>
        )}
      </div>

      {gene.description && <p className="gene-header__description">{gene.description}</p>}

      {gene.aliases.length > 0 && (
        <div className="gene-header__aliases">
          <strong>Aliases:</strong> {gene.aliases.join(", ")}
        </div>
      )}
    </div>
  );
}
