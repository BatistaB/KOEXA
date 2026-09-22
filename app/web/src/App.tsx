import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import type { Gene } from "./data/types";
import { TopBar } from "./components/shell/TopBar";
import { RightPanel, type AtlasSummary, type DatasetDetail, type GeneSummary } from "./components/shell/RightPanel";
import { GeneWorkspace } from "./components/gene/GeneWorkspace";
import { GeneRankingOverview } from "./components/overview/GeneRankingOverview";
import { Skeleton } from "./components/common/Skeleton";
import type { ChartScale } from "./components/gene/ExpressionChart";
import { referenceVersion } from "./data/fixtures";
import { loadRealGenes } from "./data/realGenes";
import { loadRealAtlas, type RealAtlasData } from "./data/realAtlas";
import { buildChartPoints, buildGeneRankings, datasetColorAssignment, median } from "./lib/points";
import { shortConditionLabel } from "./lib/conditionLabel";

const EMPTY_ATLAS: RealAtlasData = {
  datasets: [],
  conditions: [],
  samples: [],
  sampleQc: [],
  expression: [],
  classification: new Map(),
};

function App() {
  const searchRef = useRef<HTMLInputElement>(null);
  const [allGenes, setAllGenes] = useState<Gene[]>([]);
  const [atlas, setAtlas] = useState<RealAtlasData>(EMPTY_ATLAS);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [selectedGeneId, setSelectedGeneId] = useState<string | null>(null);
  const [strainFilter, setStrainFilter] = useState("all");
  const [conditionFilter, setConditionFilter] = useState("all");
  const [scale, setScale] = useState<ChartScale>("log");
  const [selectedSampleId, setSelectedSampleId] = useState<string | null>(null);
  const [hoveredSampleId, setHoveredSampleId] = useState<string | null>(null);
  const [selectedBioproject, setSelectedBioproject] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const { datasets, conditions, samples, sampleQc, expression: geneExpression, classification } = atlas;

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadRealGenes(), loadRealAtlas()])
      .then(([realGenes, realAtlas]) => {
        if (cancelled) return;
        setAllGenes(realGenes);
        setAtlas(realAtlas);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setCatalogError(err instanceof Error ? err.message : "Failed to load the atlas");
      })
      .finally(() => {
        if (!cancelled) setCatalogLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (!selectedGeneId) return;
    setLoading(true);
    const timer = window.setTimeout(() => setLoading(false), 160);
    return () => window.clearTimeout(timer);
  }, [selectedGeneId]);

  const selectedGene = useMemo(
    () => allGenes.find((g) => g.canonical_gene_id === selectedGeneId) ?? null,
    [allGenes, selectedGeneId],
  );

  const colorFor = useMemo(() => datasetColorAssignment(datasets), [datasets]);
  const strains = useMemo(() => Array.from(new Set(samples.map((s) => s.strain))).sort(), [samples]);

  const goHome = () => {
    setSelectedGeneId(null);
    setSelectedSampleId(null);
    setSelectedBioproject(null);
  };

  const selectGene = (gene: Gene) => {
    setSelectedGeneId(gene.canonical_gene_id);
    setSelectedBioproject(null);
  };

  const selectSample = (id: string) => {
    setSelectedBioproject(null);
    setSelectedSampleId((cur) => (cur === id ? null : id));
  };

  const selectDataset = (bioproject: string) => {
    setSelectedSampleId(null);
    setSelectedBioproject((cur) => (cur === bioproject ? null : bioproject));
  };

  const filteredSamples = useMemo(
    () =>
      samples.filter(
        (s) =>
          (strainFilter === "all" || s.strain === strainFilter) &&
          (conditionFilter === "all" || s.condition_id === conditionFilter),
      ),
    [samples, strainFilter, conditionFilter],
  );

  const visibleDatasets = useMemo((): [string, string][] => {
    const seen = new Map<string, string>();
    for (const s of filteredSamples) {
      if (!seen.has(s.bioproject)) {
        const ds = datasets.find((d) => d.bioproject === s.bioproject);
        seen.set(s.bioproject, ds?.publication_title ?? s.bioproject);
      }
    }
    return Array.from(seen.entries());
  }, [filteredSamples, datasets]);

  const rankings = useMemo(
    () => buildGeneRankings(allGenes, samples, conditions, datasets, geneExpression, strainFilter, conditionFilter),
    [allGenes, samples, conditions, datasets, geneExpression, strainFilter, conditionFilter],
  );

  const points = useMemo(() => {
    if (!selectedGene) return [];
    return buildChartPoints(
      selectedGene,
      samples,
      conditions,
      datasets,
      geneExpression,
      strainFilter,
      conditionFilter,
    );
  }, [selectedGene, samples, conditions, datasets, geneExpression, strainFilter, conditionFilter]);

  useEffect(() => {
    if (selectedSampleId && !points.some((p) => p.sample.sample_id === selectedSampleId)) {
      setSelectedSampleId(null);
    }
  }, [points, selectedSampleId]);

  const geneSummary: GeneSummary | null = useMemo(() => {
    if (!selectedGene) return null;
    const detected = points.filter((p) => p.tpm > 0);
    return {
      gene: selectedGene,
      sampleCount: points.length,
      conditionCount: new Set(points.map((p) => p.condition.condition_id)).size,
      datasetCount: new Set(points.map((p) => p.sample.bioproject)).size,
      detectionRate: filteredSamples.length ? detected.length / filteredSamples.length : 0,
      medianTpm: median(points.map((p) => p.tpm)),
      classification: classification.get(selectedGene.canonical_gene_id) ?? null,
    };
  }, [selectedGene, points, filteredSamples, classification]);

  const atlasSummary: AtlasSummary = useMemo(
    () => ({
      geneCount: allGenes.length,
      sampleCount: filteredSamples.length,
      conditionCount: new Set(filteredSamples.map((s) => s.condition_id)).size,
      datasetCount: new Set(filteredSamples.map((s) => s.bioproject)).size,
    }),
    [allGenes, filteredSamples],
  );

  const selection = useMemo(() => {
    if (!selectedSampleId) return null;
    const point = points.find((p) => p.sample.sample_id === selectedSampleId);
    if (!point) return null;
    const qc = sampleQc.find((q) => q.sample_id === selectedSampleId);
    return {
      sample: point.sample,
      condition: point.condition,
      dataset: point.dataset,
      qc,
      tpm: point.tpm,
      estimatedCounts: point.estimatedCounts,
    };
  }, [selectedSampleId, points, sampleQc]);

  const datasetDetail: DatasetDetail | null = useMemo(() => {
    if (!selectedBioproject) return null;
    const dataset = datasets.find((d) => d.bioproject === selectedBioproject);
    if (!dataset) return null;
    const relatedSamples = samples.filter((s) => s.bioproject === selectedBioproject);
    return {
      dataset,
      sampleCount: relatedSamples.length,
      conditionCount: new Set(relatedSamples.map((s) => s.condition_id)).size,
    };
  }, [selectedBioproject, datasets, samples]);

  const filterSummary = useMemo(() => {
    const bits: string[] = [];
    bits.push(strainFilter === "all" ? "all strains" : `strain ${strainFilter}`);
    if (conditionFilter !== "all") {
      const c = conditions.find((cd) => cd.condition_id === conditionFilter);
      bits.push(c ? `condition ${shortConditionLabel(c)}` : "selected condition");
    } else {
      bits.push("all conditions");
    }
    return `Filter: ${bits.join(" · ")}.`;
  }, [strainFilter, conditionFilter, conditions]);

  return (
    <div className="app-shell">
      <TopBar
        genes={allGenes}
        onSelectGene={selectGene}
        searchRef={searchRef}
        strains={strains}
        strain={strainFilter}
        onStrainChange={setStrainFilter}
        conditions={conditions}
        conditionId={conditionFilter}
        onConditionChange={setConditionFilter}
        referenceVersion={referenceVersion}
        sampleCount={samples.length}
        geneCount={allGenes.length}
        catalogLoading={catalogLoading}
        onBrandClick={goHome}
      />
      <div className="app-shell__body">
        <main className="app-shell__main">
          {selectedGene ? (
            <GeneWorkspace
              gene={selectedGene}
              points={points}
              datasetColor={(bioproject) => colorFor.get(bioproject) ?? "var(--series-1)"}
              scale={scale}
              onScaleChange={setScale}
              selectedSampleId={selectedSampleId}
              hoveredSampleId={hoveredSampleId}
              onHoverSample={setHoveredSampleId}
              onSelectSample={selectSample}
              onSelectDataset={selectDataset}
              loading={loading}
              onBack={goHome}
            />
          ) : catalogLoading ? (
            <div style={{ padding: 24 }}>
              <Skeleton height={20} width={280} style={{ marginBottom: 12 }} />
              <Skeleton height={340} />
            </div>
          ) : (
            <GeneRankingOverview
              rankings={rankings}
              datasets={visibleDatasets}
              datasetColor={(bioproject) => colorFor.get(bioproject) ?? "var(--series-1)"}
              onSelectGene={selectGene}
              onSelectDataset={selectDataset}
              filterSummary={
                catalogError ? `${filterSummary} Failed to load the atlas — ${catalogError}` : filterSummary
              }
            />
          )}
        </main>
        <RightPanel
          geneSummary={geneSummary}
          selection={selection}
          atlasSummary={atlasSummary}
          datasetDetail={datasetDetail}
          onCloseDataset={() => setSelectedBioproject(null)}
          onSelectDataset={selectDataset}
        />
      </div>
    </div>
  );
}

export default App;
