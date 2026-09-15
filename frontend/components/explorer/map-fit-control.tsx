import { LocateFixed } from "lucide-react";

/** The "fit screening locations" button both map renderers overlay. */
export function MapFitControl({ disabled, onFit }: { disabled: boolean; onFit: () => void }) {
  return (
    <button
      type="button"
      className="map-fit-control"
      aria-label="Fit screening locations"
      title="Fit screening locations"
      disabled={disabled}
      onClick={onFit}
    >
      <LocateFixed size={17} />
    </button>
  );
}
