import { readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import * as schemas from "@/lib/api/wire-schemas";

/** Every backend payload must be parsed before an adapter touches it.
 *
 * `/recommendations` had a schema, a wire type, and no `parseWire` call: it was
 * fetched as `apiGet<WireRecommendations>`, which tells the compiler the shape
 * is guaranteed while nothing checks it at runtime. That is worse than an
 * unvalidated endpoint with no schema, because the schema's existence reads as
 * coverage. This test makes the same mistake impossible to make quietly.
 *
 * The rule it enforces: an `apiGet`/`apiPost` in lib/api is typed `<unknown>`,
 * and the module that makes the call also calls `parseWire` at least as often.
 */

const API_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "../../lib/api");

const FETCHER_MODULES = readdirSync(API_DIR)
  .filter((name) => name.endsWith(".ts") && !name.endsWith(".d.ts"))
  .map((name) => ({ name, source: readFileSync(join(API_DIR, name), "utf8") }))
  // client.ts declares apiGet/apiPost; it does not call them.
  .filter(({ name, source }) => name !== "client.ts" && /\bapi(?:Get|Post)\s*[<(]/.test(source));

const callsIn = (source: string) => [...source.matchAll(/\bapi(?:Get|Post)\s*(<[^>]*>)?\s*\(/g)];

describe("no backend payload reaches an adapter unparsed", () => {
  it("found the fetcher modules (guards against a walker that matches nothing)", () => {
    const names = FETCHER_MODULES.map((module) => module.name).sort();
    expect(names).toEqual([
      "dashboard.ts",
      "forecast.ts",
      "heatmap.ts",
      "mines.ts",
      "predictions.ts",
      "recommendations.ts",
      "shortfall.ts",
      "targets.ts",
    ]);
  });

  it.each(FETCHER_MODULES.map((module) => [module.name, module] as const))(
    "%s types every request as <unknown>",
    (_name, module) => {
      const typed = callsIn(module.source)
        .map((match) => match[1])
        .filter((argument): argument is string => Boolean(argument) && argument !== "<unknown>");
      // A response typed as its wire interface is an unchecked assertion: the
      // compiler stops asking questions and the network still decides the shape.
      expect(typed, `claims a shape without checking it: ${typed.join(", ")}`).toEqual([]);
    },
  );

  it.each(FETCHER_MODULES.map((module) => [module.name, module] as const))(
    "%s parses every response it fetches",
    (_name, module) => {
      const requests = callsIn(module.source).length;
      const parses = [...module.source.matchAll(/\bparseWire\s*\(/g)].length;
      expect(parses, `${requests} request(s), ${parses} parseWire call(s)`).toBeGreaterThanOrEqual(requests);
    },
  );

  it("exports a schema for every wire type the adapters consume", () => {
    // A schema that exists but is never referenced is the failure above waiting
    // to happen, so each one must be imported by at least one fetcher module.
    const exported = Object.keys(schemas).filter((name) => name.startsWith("Wire") && name.endsWith("Schema"));
    expect(exported.length).toBeGreaterThanOrEqual(7);
    const allSource = FETCHER_MODULES.map((module) => module.source).join("\n");
    const unused = exported.filter((name) => !allSource.includes(name));
    expect(unused, `schema exported but never used to parse anything: ${unused.join(", ")}`).toEqual([]);
  });
});
