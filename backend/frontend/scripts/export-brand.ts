/** Regenerates the static brand files from components/brand/mark-geometry.ts so
 * the favicon and presentation exports can never drift from the component.
 *
 *   bun scripts/export-brand.ts
 */
import { writeFileSync } from "node:fs";
import {
  BAKUFU_COLORS as C,
  BAKUFU_FAVICON_PATHS as F,
  BAKUFU_PATHS as P,
  BAKUFU_VIEWBOX,
} from "../components/brand/mark-geometry";

const root = new URL("..", import.meta.url);
const write = (path: string, svg: string) => writeFileSync(new URL(path, root), `${svg}\n`);

const markBody = (body: string, core: string, paths: { body: string; seam: string; core: string } = P) =>
  `<path d="${paths.body}${paths.seam}" fill="${body}" fill-rule="evenodd"/><path d="${paths.core}" fill="${core}"/>`;

// Favicon: ground tile so the mark holds on both light and dark tab strips.
write("app/icon.svg",
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${BAKUFU_VIEWBOX}"><rect width="64" height="64" rx="12" fill="${C.ground}"/><g transform="translate(3.2 3.2) scale(0.9)">${markBody(C.paper, C.glow, F)}</g></svg>`);

const surfaces = [
  { suffix: "", ink: C.paper, core: C.glow, note: "for dark surfaces" },
  { suffix: "-light", ink: C.char, core: C.ore, note: "for paper and light slides" },
] as const;

for (const { suffix, ink, core, note } of surfaces) {
  write(`public/brand/bakufu-mark${suffix}.svg`,
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${BAKUFU_VIEWBOX}" role="img" aria-label="BAKUFU mark (${note})">${markBody(ink, core)}</svg>`);
  write(`public/brand/bakufu-lockup${suffix}.svg`,
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 64" role="img" aria-label="BAKUFU 幕府 (${note})"><g>${markBody(ink, core)}</g>` +
    `<text x="80" y="43" fill="${ink}" font-family="'JetBrains Mono', ui-monospace, Menlo, monospace" font-size="30" font-weight="700" letter-spacing="4.8">BAKUFU</text>` +
    `<text x="236" y="40" fill="${core}" font-family="'Hiragino Sans', 'Noto Sans JP', sans-serif" font-size="14" letter-spacing="1.7">幕府</text></svg>`);
}

console.log("brand files written: app/icon.svg, public/brand/bakufu-{mark,lockup}{,-light}.svg");
