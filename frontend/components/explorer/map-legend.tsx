const screeningColors = ["#16324A", "#F2B138", "#F2B138", "#E8772E", "#E8772E"];

/** Marker glyphs, drawn to match components/explorer/map-markers.ts exactly:
 * a filled headframe for a mine that exists, an open crosshair for a place the
 * model proposes. */
function MineGlyph() {
  return (
    <svg viewBox="0 0 18 18" width="13" height="13" aria-hidden="true">
      <path d="M9 2.5 14 11H4L9 2.5Z" fill="currentColor" />
      <rect x="3" y="12.2" width="12" height="2.2" rx="0.6" fill="currentColor" />
    </svg>
  );
}
function TargetGlyph() {
  return (
    <svg viewBox="0 0 18 18" width="13" height="13" aria-hidden="true">
      <circle cx="9" cy="9" r="5.6" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="9" cy="9" r="1.5" fill="currentColor" />
      <path d="M9 0.8v3.2M9 14v3.2M0.8 9h3.2M14 9h3.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function MapLegend({ origin }: { origin: "live" | "fixture" }) {
  return (
    <div className="map-legend" aria-label="Prospectivity legend">
      <div className="map-legend-heading">
        <strong>Screened prospectivity</strong>
        <span>Index / 0—0.99</span>
      </div>
      <div className="map-legend-scale" aria-hidden="true">
        {screeningColors.map((color, index) => (
          // Stops repeat a colour on purpose (the ramp holds its hue), so the
          // colour alone is not a unique key.
          <span key={`${index}-${color}`} style={{ background: color }} />
        ))}
      </div>
      <div className="map-legend-values">
        <span>0.00</span>
        <span>0.50</span>
        <span>0.99</span>
      </div>
      <div className="map-legend-symbols">
        <span>
          <span className="map-legend-glyph map-legend-glyph--mine"><MineGlyph /></span>
          MOIL mine
        </span>
        <span>
          <span className="map-legend-glyph map-legend-glyph--target"><TargetGlyph /></span>
          Model target
        </span>
        <span>
          <span className="hatch-swatch" /> Mask exclusion
        </span>
      </div>
      {/* One line: the legend sits over the map, and a long caveat took more of
          it than the key did. */}
      <p className="map-legend-caveat">
        {origin === "live"
          ? "~5 × 3 km model cells · screening index, not reserves"
          : "No model surface without the backend"}
      </p>
    </div>
  );
}
