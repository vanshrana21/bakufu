import { Diamond } from "lucide-react";

const screeningColors = ["#16324A", "#F2B138", "#F2B138", "#E8772E", "#E8772E"];

export function MapLegend() {
  return (
    <div className="map-legend" aria-label="Prospectivity legend">
      <div className="map-legend-heading">
        <strong>Screened prospectivity</strong>
        <span>Index / 0—0.99</span>
      </div>
      <div className="map-legend-scale" aria-hidden="true">
        {screeningColors.map((color) => (
          <span key={color} style={{ background: color }} />
        ))}
      </div>
      <div className="map-legend-values">
        <span>0.00</span>
        <span>0.50</span>
        <span>0.99</span>
      </div>
      <div className="map-legend-symbols">
        <span>
          <Diamond size={13} fill="#34150F" stroke="#34150F" /> Waste / slag
          fixture
        </span>
        <span>
          <span className="hatch-swatch" /> Mask exclusion
        </span>
      </div>
      <p className="map-legend-caveat">
        Synthetic cells, not surveyed footprints or a validated boundary. No
        claim of measured ore.
      </p>
    </div>
  );
}
