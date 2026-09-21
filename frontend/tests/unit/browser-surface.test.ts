import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { API_ROUTES, BROWSER_ROUTES } from "@/lib/api/routes";

/** Proof, not assertion, for the one claim this repo keeps being audited on:
 * that `/api/backend` forwards exactly the routes a browser can reach.
 *
 * Reading the code and concluding "only the Explorer fetches at runtime" is an
 * argument, and arguments go stale the moment someone adds "use client" to a
 * page. This walks the real import graph from every client entry point and
 * compares what it finds against the proxy allowlist, in both directions:
 *
 *   a route reachable from the browser but not proxied  -> a 404 in the product
 *   a route proxied but not reachable                   -> surface for nothing
 *
 * Type-only imports are skipped because they are erased before the bundle
 * exists — `import type { RegisterRow } from "@/lib/api/recommendations"` does
 * not put /recommendations in the browser, and treating it as if it did would
 * force the allowlist wide open for nothing.
 */

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const SOURCE_DIRS = ["app", "components", "hooks", "lib", "fixtures"];
const EXTENSIONS = [".ts", ".tsx", ".js", ".jsx"];

function walkFiles(dir: string, out: string[] = []): string[] {
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const entry of entries) {
    if (entry === "node_modules" || entry.startsWith(".")) continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walkFiles(full, out);
    else if (EXTENSIONS.some((extension) => full.endsWith(extension))) out.push(full);
  }
  return out;
}

const ALL_SOURCES = SOURCE_DIRS.flatMap((dir) => walkFiles(join(ROOT, dir)));

/** Strip comments and string bodies so a path mentioned in prose or in a doc
 * comment cannot be mistaken for an import or a call. Keeps the quote marks so
 * the call-site patterns below can still see where a literal was. */
function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

/** Every module specifier this file pulls in at RUNTIME.
 *
 * Skipped: `import type ...`, and `import { type A, type B }` where every named
 * specifier is type-only. Both vanish at compile time. A mixed import such as
 * `import { type A, b }` does reach the browser, so it is followed. */
function runtimeImports(source: string): string[] {
  const code = stripComments(source);
  const specifiers: string[] = [];

  const statement = /(?:^|[\s;}])(?:import|export)\s+([\s\S]*?)\s*from\s*["']([^"']+)["']/g;
  for (const match of code.matchAll(statement)) {
    const clause = match[1]!.trim();
    const target = match[2]!;
    if (/^type[\s{]/.test(clause)) continue; // import type { X } / import type X
    const braced = clause.match(/\{([\s\S]*)\}/);
    if (braced) {
      const named = braced[1]!.split(",").map((part) => part.trim()).filter(Boolean);
      const sideBySide = clause.replace(/\{[\s\S]*\}/, "").replace(/,/g, "").trim();
      // All-type braces with no default/namespace alongside them: erased.
      if (named.length > 0 && named.every((part) => /^type\s/.test(part)) && !sideBySide) continue;
    }
    specifiers.push(target);
  }
  // `import "./x"` and `export * from "./x"` have no clause; catch them too.
  for (const match of code.matchAll(/(?:^|[\s;}])import\s*["']([^"']+)["']/g)) specifiers.push(match[1]!);
  for (const match of code.matchAll(/\bimport\s*\(\s*["']([^"']+)["']\s*\)/g)) specifiers.push(match[1]!);
  return specifiers;
}

/** Resolve a specifier to a file on disk, or null for a package. */
function resolveSpecifier(specifier: string, fromFile: string): string | null {
  let base: string;
  if (specifier.startsWith("@/")) base = join(ROOT, specifier.slice(2));
  else if (specifier.startsWith(".")) base = resolve(dirname(fromFile), specifier);
  else return null; // node_modules — not our source graph

  for (const candidate of [
    ...EXTENSIONS.map((extension) => base + extension),
    ...EXTENSIONS.map((extension) => join(base, "index" + extension)),
    base,
  ]) {
    try {
      if (statSync(candidate).isFile()) return candidate;
    } catch {
      /* next candidate */
    }
  }
  return null;
}

/** API paths requested from a module: `apiGet<T>("/x")`, `apiPost("/x", …)`,
 * and the template form used for parameterised routes. */
function requestedPaths(source: string): string[] {
  const code = stripComments(source);
  const found: string[] = [];
  for (const match of code.matchAll(/\bapi(?:Get|Post)\s*(?:<[^>]*>)?\s*\(\s*["'`]([^"'`]*)/g)) {
    found.push(match[1]!);
  }
  return found;
}

/** Normalise a template-literal path back to its FastAPI shape:
 * `/recommendations/scenario/${encodeURIComponent(month)}` becomes
 * `/recommendations/scenario/{}`, so an interpolated segment is still reported
 * as a distinct route rather than as the prefix before it. */
function toRoutePath(raw: string): string {
  const interpolated = raw.indexOf("${");
  if (interpolated === -1) return raw;
  return `${raw.slice(0, interpolated)}{}`;
}

const CLIENT_ENTRIES = ALL_SOURCES.filter((file) => /^\s*["']use client["']/.test(readFileSync(file, "utf8")));

/** Every module the browser can load, reached from the client entry points. */
function browserModules(): Set<string> {
  const seen = new Set<string>();
  const queue = [...CLIENT_ENTRIES];
  while (queue.length > 0) {
    const file = queue.pop()!;
    if (seen.has(file)) continue;
    seen.add(file);
    const source = readFileSync(file, "utf8");
    for (const specifier of runtimeImports(source)) {
      const resolved = resolveSpecifier(specifier, file);
      if (resolved && !seen.has(resolved)) queue.push(resolved);
    }
  }
  return seen;
}

describe("what the browser can actually reach", () => {
  const modules = browserModules();

  it("finds the client entry points at all (guards against a broken walker)", () => {
    expect(CLIENT_ENTRIES.length).toBeGreaterThan(10);
    // The two hooks that genuinely fetch must be in the graph, or a later
    // assertion passing would mean nothing.
    const names = [...modules].map((file) => relative(ROOT, file));
    expect(names).toContain("hooks/use-prospectivity-surface.ts");
    expect(names).toContain("hooks/use-point-explanation.ts");
    expect(names).toContain("lib/api/heatmap.ts");
    expect(names).toContain("lib/api/predictions.ts");
  });

  it("requests exactly the routes the proxy forwards — no more, no fewer", () => {
    const reachable = new Set<string>();
    for (const file of modules) {
      for (const raw of requestedPaths(readFileSync(file, "utf8"))) {
        if (raw) reachable.add(toRoutePath(raw));
      }
    }
    const proxied = new Set(Object.keys(BROWSER_ROUTES).map((path) => `/${path}`));

    const unproxied = [...reachable].filter((path) => !proxied.has(path));
    const unused = [...proxied].filter((path) => !reachable.has(path));

    // A path here is a route the browser asks for that /api/backend answers 404.
    expect(unproxied, `browser-reachable but NOT proxied: ${unproxied.join(", ")}`).toEqual([]);
    // A path here is unauthenticated surface nothing uses.
    expect(unused, `proxied but NOT browser-reachable: ${unused.join(", ")}`).toEqual([]);
  });

  it("keeps the server-only loaders out of the browser bundle entirely", () => {
    // Stronger than checking the call sites: these modules must not be reachable
    // at all, so their routes cannot come back through a refactor unnoticed.
    const serverOnly = ["lib/api/load.ts", "lib/api/dashboard.ts", "lib/api/forecast.ts", "lib/api/shortfall.ts"];
    const names = new Set([...modules].map((file) => relative(ROOT, file)));
    for (const module of serverOnly) {
      expect(names.has(module), `${module} is reachable from a client component`).toBe(false);
    }
  });

  it("agrees with the registry about which surface each route sits on", () => {
    const browserPaths = API_ROUTES.filter((route) => route.surface === "browser").map((route) => route.path);
    expect(browserPaths.sort()).toEqual(["/predict/point", "/prospectivity/heatmap"]);
  });
});
