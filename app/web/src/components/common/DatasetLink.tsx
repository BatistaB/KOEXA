import "./DatasetLink.css";

export function DatasetLink({
  bioproject,
  onSelect,
  className,
}: {
  bioproject: string;
  onSelect: (bioproject: string) => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      className={className ? `dataset-link ${className}` : "dataset-link"}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(bioproject);
      }}
    >
      {bioproject}
    </button>
  );
}
