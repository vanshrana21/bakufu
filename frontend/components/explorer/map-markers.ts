/** Mine and target markers, shared by the Mapbox and MapLibre canvases.
 *
 * DOM markers rather than GL symbol layers: neither style loads a glyph
 * source, so a symbol layer could draw an icon but never a label, and these
 * markers have to be readable ("Balaghat", "T1") to be useful. Both engines
 * expose the same Marker constructor shape, so one implementation serves both.
 *
 * Two icons, two meanings, deliberately unalike at a glance:
 *   mine   - a filled headframe over a base line: a place that exists today
 *   target - an open crosshair: a place the model proposes
 *
 * Ported from the team lead's Explorer (yashnimde-ship-it/Spin-off, 12ba14b).
 */

import type { MineLocation, Target } from "@/lib/contracts";
import type { Selection, SelectionKind } from "@/stores/explorer-store";

type LngLat = [number, number];

interface MarkerInstance {
  setLngLat(coordinates: LngLat): MarkerInstance;
  addTo(map: never): MarkerInstance;
  remove(): void;
}
export interface MarkerConstructor {
  new (options: { element: HTMLElement; anchor?: "bottom" | "center"; offset?: [number, number] }): MarkerInstance;
}

export const MINE_ICON =
  '<svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">' +
  '<path d="M9 2.5 14 11H4L9 2.5Z" fill="currentColor" />' +
  '<rect x="3" y="12.2" width="12" height="2.2" rx="0.6" fill="currentColor" />' +
  "</svg>";

export const TARGET_ICON =
  '<svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">' +
  '<circle cx="9" cy="9" r="5.6" fill="none" stroke="currentColor" stroke-width="1.8" />' +
  '<circle cx="9" cy="9" r="1.5" fill="currentColor" />' +
  '<path d="M9 0.8v3.2M9 14v3.2M0.8 9h3.2M14 9h3.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" />' +
  "</svg>";

export interface MarkerLayerOptions {
  mines: readonly MineLocation[];
  targets: readonly Target[];
  selected: Selection | null;
  onSelect: (selection: Selection) => void;
}

function markerElement(
  kind: SelectionKind,
  id: string,
  tag: string,
  title: string,
  selected: boolean,
  onSelect: () => void,
): HTMLElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `map-marker map-marker--${kind}`;
  button.dataset.selected = String(selected);
  button.dataset.markerKind = kind;
  button.dataset.markerId = id;
  button.title = title;
  button.setAttribute("aria-label", title);
  button.setAttribute("aria-pressed", String(selected));
  button.innerHTML =
    `<span class="map-marker-icon">${kind === "mine" ? MINE_ICON : TARGET_ICON}</span>` +
    '<span class="map-marker-tag"></span>';
  // textContent, never innerHTML: the tag carries backend-supplied names.
  button.querySelector(".map-marker-tag")!.textContent = tag;
  button.addEventListener("click", (event) => {
    // Without this the map's own click handler also fires and reports the
    // click as empty ground.
    event.stopPropagation();
    onSelect();
  });
  return button;
}

const overlaps = (a: DOMRect, b: DOMRect) =>
  a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;

/** Hides every name tag that would collide with a more important tag or with
 * another marker's icon. Icons always stay: every place remains visible and
 * clickable, and a hidden name is still its title and accessible label. Order
 * is importance: the selection, then targets by rank, then mines. */
export function declutterTags(elements: readonly HTMLElement[]): void {
  const icons = elements.map((element) => element.querySelector<HTMLElement>(".map-marker-icon")?.getBoundingClientRect() ?? null);
  const accepted: DOMRect[] = [];
  for (const element of elements) {
    const tag = element.querySelector<HTMLElement>(".map-marker-tag");
    if (!tag) continue;
    tag.style.visibility = "";
    const rect = tag.getBoundingClientRect();
    const ownIcon = icons[elements.indexOf(element)];
    const clash =
      accepted.some((other) => overlaps(rect, other)) ||
      icons.some((icon) => icon !== null && icon !== ownIcon && overlaps(rect, icon));
    if (clash) tag.style.visibility = "hidden";
    else accepted.push(rect);
  }
}

interface EventedMap {
  on(type: "moveend" | "resize", listener: () => void): unknown;
  off(type: "moveend" | "resize", listener: () => void): unknown;
}

/** Draw every marker, returning a disposer. Markers are rebuilt rather than
 * diffed: twenty elements is cheap, and a stale element surviving a data
 * change would pin the wrong name to a coordinate. */
export function renderMarkers<Map>(
  map: Map,
  Marker: MarkerConstructor,
  { mines, targets, selected, onSelect }: MarkerLayerOptions,
): () => void {
  const created: MarkerInstance[] = [];
  const byImportance: Array<{ element: HTMLElement; rank: number }> = [];

  const place = (kind: SelectionKind, id: string, tag: string, title: string, coordinates: LngLat, rank: number) => {
    const isSelected = selected?.kind === kind && selected.id === id;
    const element = markerElement(kind, id, tag, title, isSelected, () => onSelect({ kind, id }));
    created.push(new Marker({ element, anchor: "center" }).setLngLat(coordinates).addTo(map as never));
    byImportance.push({ element, rank: isSelected ? -1 : rank });
  };

  for (const mine of mines) {
    place("mine", mine.name, mine.name, `${mine.name} — operating MOIL mine, ${mine.district}, ${mine.state}`,
      [mine.location.longitude, mine.location.latitude], 1000);
  }
  // Targets last so a proposal never hides behind a mine at the same spot.
  for (const target of targets) {
    place("target", target.id, target.id, `${target.id} — model target, ${target.label}`,
      [target.location.longitude, target.location.latitude], target.rank);
  }

  const ordered = byImportance.sort((a, b) => a.rank - b.rank).map((entry) => entry.element);
  const declutter = () => declutterTags(ordered);
  const events = map as unknown as EventedMap;
  // Positions settle on the next frame; after that, only a camera change moves them.
  const frame = requestAnimationFrame(declutter);
  events.on("moveend", declutter);
  events.on("resize", declutter);

  return () => {
    cancelAnimationFrame(frame);
    events.off("moveend", declutter);
    events.off("resize", declutter);
    for (const marker of created) marker.remove();
  };
}
