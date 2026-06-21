export interface RetrievalFilterState {
  mimeTypes: string;
  heading: string;
  sectionPath: string;
  pageStart: string;
  pageEnd: string;
}

interface RetrievalFiltersPanelProps {
  filters: RetrievalFilterState;
  validationMessage: string | null;
  onChange: (filters: RetrievalFilterState) => void;
}

export const EMPTY_RETRIEVAL_FILTERS: RetrievalFilterState = {
  mimeTypes: "",
  heading: "",
  sectionPath: "",
  pageStart: "",
  pageEnd: "",
};

export default function RetrievalFiltersPanel({
  filters,
  validationMessage,
  onChange,
}: RetrievalFiltersPanelProps) {
  function updateFilter(field: keyof RetrievalFilterState, value: string) {
    onChange({
      ...filters,
      [field]: value,
    });
  }

  return (
    <details className="retrieval-filters-panel">
      <summary className="retrieval-filters-summary">
        <span className="material-symbols-outlined">tune</span>
        <span>Retrieval filters</span>
      </summary>

      <div className="retrieval-filters-grid">
        <label className="retrieval-filter-field">
          <span>MIME / file type</span>
          <input
            type="text"
            value={filters.mimeTypes}
            onChange={(event) => updateFilter("mimeTypes", event.target.value)}
            placeholder="application/pdf, text/markdown"
          />
        </label>

        <label className="retrieval-filter-field">
          <span>Heading contains</span>
          <input
            type="text"
            value={filters.heading}
            onChange={(event) => updateFilter("heading", event.target.value)}
            placeholder="Pricing"
          />
        </label>

        <label className="retrieval-filter-field retrieval-filter-field-wide">
          <span>Section path segments</span>
          <input
            type="text"
            value={filters.sectionPath}
            onChange={(event) => updateFilter("sectionPath", event.target.value)}
            placeholder="Plans, Enterprise"
          />
        </label>

        <label className="retrieval-filter-field">
          <span>Start page</span>
          <input
            type="number"
            min="0"
            step="1"
            value={filters.pageStart}
            onChange={(event) => updateFilter("pageStart", event.target.value)}
            placeholder="0"
          />
        </label>

        <label className="retrieval-filter-field">
          <span>End page</span>
          <input
            type="number"
            min="0"
            step="1"
            value={filters.pageEnd}
            onChange={(event) => updateFilter("pageEnd", event.target.value)}
            placeholder="10"
          />
        </label>
      </div>

      {validationMessage && (
        <p className="retrieval-filter-error" role="alert">
          {validationMessage}
        </p>
      )}
    </details>
  );
}
