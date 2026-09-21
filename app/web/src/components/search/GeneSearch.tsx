import { forwardRef, useMemo, useState } from "react";
import type { Gene } from "../../data/types";
import { searchGenes } from "../../lib/search";
import { isSymbolicLabel, primaryGeneLabel } from "../../lib/geneDisplay";
import "./GeneSearch.css";

interface GeneSearchProps {
  genes: Gene[];
  onSelect: (gene: Gene) => void;
}

export const GeneSearch = forwardRef<HTMLInputElement, GeneSearchProps>(
  function GeneSearch({ genes, onSelect }, ref) {
    const [query, setQuery] = useState("");
    const [open, setOpen] = useState(false);
    const [activeIndex, setActiveIndex] = useState(0);

    const hits = useMemo(
      () => searchGenes(query, genes).slice(0, 8),
      [query, genes],
    );

    const commit = (gene: Gene) => {
      onSelect(gene);
      setQuery("");
      setOpen(false);
      setActiveIndex(0);
    };

    return (
      <div className="gene-search">
        <div className="gene-search__input-wrap">
          <svg
            className="gene-search__icon"
            width="14"
            height="14"
            viewBox="0 0 16 16"
            fill="none"
            aria-hidden="true"
          >
            <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.4" />
            <line x1="11" y1="11" x2="15" y2="15" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <input
            ref={ref}
            className="gene-search__input"
            role="combobox"
            aria-expanded={open && hits.length > 0}
            aria-controls="gene-search-listbox"
            aria-autocomplete="list"
            placeholder="Search gene — AO09, symbol, alias or UniProt"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
              setActiveIndex(0);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => window.setTimeout(() => setOpen(false), 120)}
            onKeyDown={(e) => {
              if (!open || hits.length === 0) return;
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActiveIndex((i) => Math.min(i + 1, hits.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActiveIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                const hit = hits[activeIndex];
                if (hit) commit(hit.gene);
              } else if (e.key === "Escape") {
                setOpen(false);
              }
            }}
          />
          {!open && <kbd className="gene-search__kbd">⌘K</kbd>}
        </div>
        {open && query.trim() !== "" && (
          <div className="gene-search__panel" role="listbox" id="gene-search-listbox">
            {hits.length === 0 ? (
              <div className="gene-search__empty">
                No genes found for "{query}"
              </div>
            ) : (
              hits.map((hit, index) => (
                <div
                  key={hit.gene.canonical_gene_id}
                  className="gene-search__option"
                  role="option"
                  aria-selected={index === activeIndex}
                  onMouseEnter={() => setActiveIndex(index)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    commit(hit.gene);
                  }}
                >
                  <span className="gene-search__option-main">
                    <span
                      className={isSymbolicLabel(hit.gene) ? "gene-search__symbol" : "gene-search__symbol gene-search__symbol--plain"}
                    >
                      {primaryGeneLabel(hit.gene)}
                    </span>
                    {isSymbolicLabel(hit.gene) && hit.gene.gene_name && (
                      <span className="gene-search__name">{hit.gene.gene_name}</span>
                    )}
                  </span>
                  <span className="gene-search__id mono">
                    {hit.gene.canonical_gene_id}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    );
  },
);
