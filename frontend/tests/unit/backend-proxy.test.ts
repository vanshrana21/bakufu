import { describe, expect, it } from "vitest";
import { BROWSER_ROUTES, proxyTarget } from "@/lib/api/backend-proxy";

const API = "http://127.0.0.1:8000";

describe("browser proxy allowlist", () => {
  it("forwards the heatmap GET with its query intact", () => {
    expect(proxyTarget(API, ["prospectivity", "heatmap"], "GET", "?min_lon=79&mask=both"))
      .toBe("http://127.0.0.1:8000/prospectivity/heatmap?min_lon=79&mask=both");
  });

  it("forwards the point POST", () => {
    expect(proxyTarget(API, ["predict", "point"], "POST", "?mask=none")).toBe("http://127.0.0.1:8000/predict/point?mask=none");
  });

  it("refuses the wrong method for an allowed path", () => {
    expect(proxyTarget(API, ["predict", "point"], "GET", "")).toBeNull();
    expect(proxyTarget(API, ["prospectivity", "heatmap"], "POST", "")).toBeNull();
  });

  it("refuses every route the browser does not use", () => {
    for (const segments of [["train"], ["forecast"], ["predictions", "1"], ["..", "admin"], ["constructor"], ["toString"]]) {
      expect(proxyTarget(API, segments, "GET", "")).toBeNull();
      expect(proxyTarget(API, segments, "POST", "")).toBeNull();
    }
  });

  it("allows exactly the two browser routes", () => {
    expect(Object.keys(BROWSER_ROUTES).sort()).toEqual(["predict/point", "prospectivity/heatmap"]);
  });
});
