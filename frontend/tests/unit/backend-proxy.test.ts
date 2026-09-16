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

  it("refuses segments that would rewrite the path after the allowlist matched", () => {
    // Next.js hands these already decoded, so `predict%2Fpoint` arrives as one
    // segment containing a slash. Joining it would produce an allowed-looking
    // path; and `..` would walk off the route the allowlist actually approved.
    for (const segments of [
      ["predict", "..", "point"],
      ["prospectivity", "heatmap", ".."],
      ["predict/point"],
      ["predict\\point"],
      ["prospectivity", "heatmap/../../train"],
      ["."],
      ["%2e%2e", "train"],
    ]) {
      expect(proxyTarget(API, segments, "GET", ""), segments.join("|")).toBeNull();
      expect(proxyTarget(API, segments, "POST", ""), segments.join("|")).toBeNull();
    }
  });

  it("does not treat inherited object properties as routes", () => {
    for (const name of ["constructor", "toString", "hasOwnProperty", "__proto__", "valueOf"]) {
      expect(proxyTarget(API, [name], "GET", "")).toBeNull();
    }
  });

  it("passes the query string through untouched, including repeated keys", () => {
    expect(proxyTarget(API, ["prospectivity", "heatmap"], "GET", "?mask=both&mask=none&grid_size=32"))
      .toBe("http://127.0.0.1:8000/prospectivity/heatmap?mask=both&mask=none&grid_size=32");
    expect(proxyTarget(API, ["prospectivity", "heatmap"], "GET", "")).toBe("http://127.0.0.1:8000/prospectivity/heatmap");
  });
});
