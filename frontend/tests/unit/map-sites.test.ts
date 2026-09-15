import { describe, expect, it } from "vitest";
import { DEMO_SITES } from "@/fixtures/predictions";
import { MAP_IDS, fallbackPlotPosition, framingPadding, renderedCounts, siteExtent, siteFeatures } from "@/lib/map/sites";

describe("siteFeatures", () => {
  const collection = siteFeatures(DEMO_SITES);

  it("draws only located, in-scope sites", () => {
    expect(collection.features.map((f) => f.id)).toEqual(["demo-dump-a", "demo-slag-b", "demo-dump-c", "farmland-control"]);
  });

  it("marks waste dumps and slag heaps, not diagnostics", () => {
    const waste = Object.fromEntries(collection.features.map((f) => [f.id, f.properties.waste]));
    expect(waste).toEqual({ "demo-dump-a": true, "demo-slag-b": true, "demo-dump-c": true, "farmland-control": false });
  });

  it("uses lon/lat order", () => {
    expect(collection.features[0]?.geometry.coordinates).toEqual([79.52, 21.73]);
  });
});

describe("siteExtent", () => {
  it("pads every located site and ignores unlocated ones", () => {
    const [[west, south], [east, north]] = siteExtent(DEMO_SITES, { inScopeOnly: true })!;
    expect(west).toBeCloseTo(79.25 - 0.08);
    expect(east).toBeCloseTo(80.05 + 0.08);
    expect(south).toBeCloseTo(21.55 - 0.07);
    expect(north).toBeCloseTo(21.82 + 0.07);
  });

  it("is null when nothing can be framed", () => {
    expect(siteExtent(DEMO_SITES.filter((site) => site.location === null), { inScopeOnly: false })).toBeNull();
    expect(siteExtent([], { inScopeOnly: true })).toBeNull();
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
  it("clamps sites into the plot and skips unlocated ones", () => {
    // Demo waste dump A at 79.52 E, 21.73 N on the 79.15-80.15 / 21.45-21.95 plot.
    const position = fallbackPlotPosition(DEMO_SITES[0]!)!;
    expect(Number.parseFloat(position.left)).toBeCloseTo(18 + 0.37 * 64);
    expect(Number.parseFloat(position.top)).toBeCloseTo(76 - (0.28 / 0.5) * 52);
    // Far outside the plot, a site is clamped to the plot edge rather than lost.
    expect(Number.parseFloat(fallbackPlotPosition({ ...DEMO_SITES[0]!, location: { longitude: 75, latitude: 30 } })!.left)).toBe(10);
    expect(Number.parseFloat(fallbackPlotPosition({ ...DEMO_SITES[0]!, location: { longitude: 75, latitude: 30 } })!.top)).toBe(16);
    expect(fallbackPlotPosition(DEMO_SITES.find((site) => site.id === "sandur")!)).toBeNull();
  });
});

describe("renderedCounts", () => {
  it("counts unique ids per layer group and zero for missing layers", () => {
    const drawn: Record<string, Array<{ properties: { id: string } }>> = {
      "prospectivity-screened": [{ properties: { id: "a" } }, { properties: { id: "a" } }, { properties: { id: "b" } }],
      "prospectivity-excluded": [{ properties: { id: "b" } }],
    };
    const counts = renderedCounts((layers) => layers.flatMap((layer) => drawn[layer] ?? []), (id) => id in drawn);
    expect(counts).toEqual({ cells: 2, excluded: 1, waste: 0 });
    expect(MAP_IDS.wasteLayer in drawn).toBe(false);
  });
});
