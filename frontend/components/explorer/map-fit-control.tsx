import { LocateFixed } from "lucide-react";

/** The "fit mines and targets" button both map renderers overlay. */
export function MapFitControl({ disabled, onFit }: { disabled: boolean; onFit: () => void }) {
  return (
    <button
      type="button"
      className="map-fit-control"
      aria-label="Fit mines and targets"
      title="Fit mines and targets"
      disabled={disabled}
      onClick={onFit}
    >
      <LocateFixed size={17} />
    </button>
  );
}
