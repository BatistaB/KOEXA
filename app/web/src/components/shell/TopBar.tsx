import type { Ref } from "react";
import type { Condition, Gene } from "../../data/types";
import { GeneSearch } from "../search/GeneSearch";
import { shortConditionLabel } from "../../lib/conditionLabel";
import lebimoLogo from "../../assets/lebimo-logo.png";
import "./TopBar.css";

interface TopBarProps {
  genes: Gene[];
  onSelectGene: (gene: Gene) => void;
  searchRef: Ref<HTMLInputElement>;
  strains: string[];
  strain: string;
  onStrainChange: (strain: string) => void;
  conditions: Condition[];
  conditionId: string;
  onConditionChange: (conditionId: string) => void;
  referenceVersion: string;
  sampleCount: number;
  geneCount: number;
  catalogLoading: boolean;
  onBrandClick: () => void;
}

export function TopBar({
  genes,
  onSelectGene,
  searchRef,
  strains,
  strain,
  onStrainChange,
  conditions,
  conditionId,
  onConditionChange,
  referenceVersion,
  sampleCount,
  geneCount,
  catalogLoading,
  onBrandClick,
}: TopBarProps) {
  return (
    <header className="top-bar">
      <button type="button" className="top-bar__brand" onClick={onBrandClick}>
        <img className="top-bar__logo" src={lebimoLogo} alt="LEBIMO — Metabolic Engineering Lab" />
        <span className="top-bar__brand-divider" aria-hidden="true" />
        <span className="top-bar__brand-mark">AOED</span>
        <span className="top-bar__brand-sub">A. oryzae Expression Database</span>
      </button>

      <div className="top-bar__filter">
        <span className="top-bar__filter-label">Strain</span>
        <select
          className="top-bar__filter-select"
          value={strain}
          onChange={(e) => onStrainChange(e.target.value)}
        >
          <option value="all">All</option>
          {strains.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="top-bar__filter">
        <span className="top-bar__filter-label">Condition</span>
        <select
          className="top-bar__filter-select"
          value={conditionId}
          onChange={(e) => onConditionChange(e.target.value)}
        >
          <option value="all">All</option>
          {conditions.map((c) => (
            <option key={c.condition_id} value={c.condition_id}>
              {shortConditionLabel(c)}
            </option>
          ))}
        </select>
      </div>

      <div className="top-bar__search-slot">
        <GeneSearch ref={searchRef} genes={genes} onSelect={onSelectGene} />
      </div>

      <div className="top-bar__provenance">
        <span>
          <strong>{referenceVersion}</strong>
        </span>
        <span>·</span>
        <span>
          {catalogLoading ? "loading gene catalog…" : `${geneCount.toLocaleString("en-US")} genes`}
        </span>
        <span>·</span>
        <span>{sampleCount} samples</span>
      </div>
    </header>
  );
}
