import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** The API key is server-only. Two ways it could leak: a NEXT_PUBLIC_ name,
 * which Next.js inlines into the page, or the value itself ending up in a
 * client chunk. Both are checked here against the real build output. */

const ROOT = join(__dirname, "..", "..");

function walk(directory: string, matches: string[] = []): string[] {
  let entries: string[];
  try {
    entries = readdirSync(directory);
  } catch {
    return matches;
  }
  for (const entry of entries) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) walk(path, matches);
    else if (/\.(js|mjs|json|html|txt|map)$/.test(entry)) matches.push(path);
  }
  return matches;
}

function envValue(name: string): string | null {
  try {
    const line = readFileSync(join(ROOT, ".env.local"), "utf8")
      .split("\n")
      .find((row) => row.startsWith(`${name}=`));
    const value = line?.slice(name.length + 1).trim();
    return value ? value : null;
  } catch {
    return null;
  }
}

describe("the API key stays on the server", () => {
  it("is never read under a NEXT_PUBLIC_ name", () => {
    const sources = [
      "lib/api/client.ts",
      "lib/api/backend-proxy.ts",
      "app/api/backend/[...path]/route.ts",
    ].map((file) => readFileSync(join(ROOT, file), "utf8"));
    for (const source of sources) {
      expect(source).not.toMatch(/NEXT_PUBLIC_[A-Z_]*API_KEY/);
    }
    // The browser path must not even look the key up.
    const client = readFileSync(join(ROOT, "lib/api/client.ts"), "utf8");
    expect(client).toMatch(/IN_BROWSER \? undefined : process\.env\.BAKUFU_API_KEY/);
  });

  it("does not appear in anything the browser downloads", () => {
    const chunks = walk(join(ROOT, ".next", "static"));
    if (chunks.length === 0) {
      // Nothing built yet: `npm run build` makes this assertion meaningful.
      return;
    }
    const key = envValue("BAKUFU_API_KEY");
    const offenders: string[] = [];
    for (const chunk of chunks) {
      const contents = readFileSync(chunk, "utf8");
      if (contents.includes("BAKUFU_API_KEY")) offenders.push(`${chunk} (name)`);
      if (key && contents.includes(key)) offenders.push(`${chunk} (value)`);
    }
    expect(offenders).toEqual([]);
  });
});
