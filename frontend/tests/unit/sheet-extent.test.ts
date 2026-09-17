import { describe, expect, it } from "vitest";
import { WARM_VIEWPORTS } from "@/lib/api/heatmap";
import { SHEET_EXTENT, formatLatitude, formatLongitude } from "@/components/shell/sheet-frame";

/** Every sheet's rulers claim an area: the Sausar Belt, the model's validated
 * scope. That claim has to be the same area the map actually scores, or the
 * frame would label one place and the heatmap would show another. */
describe("sheet graticule", () => {
  it("frames exactly the extent the backend warms and the Explorer maps", () => {
    const { minLon, maxLon, minLat, maxLat } = WARM_VIEWPORTS.full_bbox;
    expect(SHEET_EXTENT).toEqual({ west: minLon, east: maxLon, south: minLat, north: maxLat });
  });

  it("labels coordinates in degrees and whole minutes", () => {
    expect(formatLongitude(79.0)).toBe("79°00′E");
    expect(formatLongitude(79.4)).toBe("79°24′E");
    expect(formatLongitude(80.6)).toBe("80°36′E");
    expect(formatLatitude(22.1)).toBe("22°06′N");
    expect(formatLatitude(21.3)).toBe("21°18′N");
  });

  it("carries a minute that rounds up to 60 into the next degree", () => {
    // 79.9999° is 79°59.994′ - it must read 80°00′, never 79°60′.
    expect(formatLongitude(79.9999)).toBe("80°00′E");
  });

  it("names the other hemispheres correctly", () => {
    expect(formatLongitude(-3.5)).toBe("3°30′W");
    expect(formatLatitude(-12.25)).toBe("12°15′S");
  });
});
