import { describe, expect, it } from "vitest";
import { MINES_REFERENCE } from "@/fixtures/mines";
import { mineLocations } from "@/lib/api/mines";
import {
  BELT_EXTENT, fallbackPlotPosition, framingPadding, initialExtent, markerPoints, pointsExtent, renderedCounts,
} from "@/lib/map/sites";

const MINES = mineLocations(MINES_REFERENCE);
const target = (longitude: number, latitude: number) => ({ location: { longitude, latitude } });

describe("markerPoints", () => {
  it("lists every mine then every target, in lon/lat order", () => {
    const points = markerPoints(MINES.slice(0, 2), [target(79.05, 21.6)]);
    expect(points).toEqual([
      [MINES[0]!.location.longitude, MINES[0]!.location.latitude],
      [MINES[1]!.location.longitude, MINES[1]!.location.latitude],
      [79.05, 21.6],
    ]);
  });
});

describe("pointsExtent", () => {
  it("pads every point, so no marker sits on the frame edge", () => {
    const [[west, south], [east, north]] = pointsExtent([[79.25, 21.65], [80.05, 21.82], [79.3, 21.55]])!;
    expect(west).toBeCloseTo(79.25 - 0.08);
    expect(east).toBeCloseTo(80.05 + 0.08);
    expect(south).toBeCloseTo(21.55 - 0.07);
    expect(north).toBeCloseTo(21.82 + 0.07);
  });

  it("is null when there is nothing to frame", () => {
    expect(pointsExtent([])).toBeNull();
  });

  it("frames all ten reference mines inside the served belt, give or take the pad", () => {
    const [[west, south], [east, north]] = pointsExtent(markerPoints(MINES, []))!;
    const [[beltWest, beltSouth], [beltEast, beltNorth]] = BELT_EXTENT;
    expect(west).toBeGreaterThan(beltWest - 0.2);
    expect(east).toBeLessThan(beltEast + 0.2);
    expect(south).toBeGreaterThan(beltSouth - 0.2);
    expect(north).toBeLessThan(beltNorth + 0.2);
  });
});

describe("initialExtent", () => {
  it("frames the whole served belt before any target exists, widened to hold every mine", () => {
    expect(initialExtent([])).toEqual(BELT_EXTENT);
    const [[west, south], [east, north]] = initialExtent(markerPoints(MINES, []));
    // Gumgaon at 78.98 E, padded, lies west of the belt's 79.0 E edge.
    expect(west).toBeCloseTo(78.98 - 0.08);
    expect(south).toBeLessThanOrEqual(BELT_EXTENT[0][1]);
    expect(east).toBe(BELT_EXTENT[1][0]);
    expect(north).toBe(BELT_EXTENT[1][1]);
  });
});

describe("framingPadding", () => {
  it("reserves more bottom space on narrow maps and on refit", () => {
    expect(framingPadding(1200, "initial")).toEqual({ top: 80, bottom: 42, left: 35, right: 45 });
    expect(framingPadding(400, "initial").bottom).toBe(150);
    expect(framingPadding(1200, "refit")).toEqual({ top: 90, bottom: 75, left: 35, right: 45 });
    expect(framingPadding(400, "refit").bottom).toBe(170);
  });
});

describe("fallbackPlotPosition", () => {
  it("places points inside the plot frame, west left and north up", () => {
    const gumgaon = MINES.find((mine) => mine.name === "Gumgaon")!;
    const ukwa = MINES.find((mine) => mine.name === "Ukwa")!;
    const west = fallbackPlotPosition(gumgaon);
    const east = fallbackPlotPosition(ukwa);
    expect(Number.parseFloat(west.left)).toBeLessThan(Number.parseFloat(east.left));
    // Ukwa is the northernmost mine, so it plots highest.
    expect(Number.parseFloat(east.top)).toBeLessThan(Number.parseFloat(west.top));
    for (const mine of MINES) {
      const { left, top } = fallbackPlotPosition(mine);
      expect(Number.parseFloat(left)).toBeGreaterThanOrEqual(18);
      expect(Number.parseFloat(left)).toBeLessThanOrEqual(82);
      expect(Number.parseFloat(top)).toBeGreaterThanOrEqual(24);
      expect(Number.parseFloat(top)).toBeLessThanOrEqual(76);
    }
  });

  it("clamps a point far outside the plot to its edge rather than losing it", () => {
    expect(fallbackPlotPosition(target(75, 30))).toEqual({ left: "10%", top: "16%" });
  });
});

describe("renderedCounts", () => {
  it("counts unique cell ids per layer group and zero for missing layers", () => {
    const drawn: Record<string, Array<{ properties: { id: string } }>> = {
      "prospectivity-screened": [{ properties: { id: "a" } }, { properties: { id: "a" } }, { properties: { id: "b" } }],
      "prospectivity-excluded": [{ properties: { id: "b" } }],
    };
    const counts = renderedCounts((layers) => layers.flatMap((layer) => drawn[layer] ?? []), (id) => id in drawn);
    expect(counts).toEqual({ cells: 2, excluded: 1 });
    expect(renderedCounts(() => [], () => false)).toEqual({ cells: 0, excluded: 0 });
  });
});
