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
 */

import type { MineLocation, Target } from "@/lib/contracts";
import type { Selection, SelectionKind } from "@/stores/explorer-store";

type LngLat = [number, number];

interface MarkerInstance {
  setLngLat(coordinates: LngLat): MarkerInstance;
  addTo(map: unknown): MarkerInstance;
  remove(): void;
}
export interface MarkerConstructor {
  new (options: {
    element: HTMLElement;
    anchor?: "bottom" | "center";
    offset?: [number, number];
  }): MarkerInstance;
}

const MINE_ICON =
  '<svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">' +
  '<path d="M9 2.5 14 11H4L9 2.5Z" fill="currentColor" />' +
  '<rect x="3" y="12.2" width="12" height="2.2" rx="0.6" fill="currentColor" />' +
  "</svg>";

const TARGET_ICON =
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
    `<span class="map-marker-tag"></span>`;
  // textContent, never innerHTML: the tag carries backend-supplied names.
  button.querySelector(".map-marker-tag")!.textContent = tag;
  button.addEventListener("click", (event) => {
    // Without this the map's own click handler also fires and clears the
    // selection the marker just made.
    event.stopPropagation();
    onSelect();
  });
  return button;
}

/** Draw every marker, returning a disposer. Markers are rebuilt rather than
 * diffed: twenty elements is cheap, and a stale element surviving a data
 * change would pin the wrong name to a coordinate. */
export function renderMarkers(
  map: unknown,
  Marker: MarkerConstructor,
  { mines, targets, selected, onSelect }: MarkerLayerOptions,
): () => void {
  const created: MarkerInstance[] = [];

  const place = (
    kind: SelectionKind,
    id: string,
    tag: string,
    title: string,
    coordinates: LngLat,
  ) => {
    const isSelected = selected?.kind === kind && selected.id === id;
    const element = markerElement(kind, id, tag, title, isSelected, () =>
      onSelect({ kind, id }),
    );
    created.push(
      new Marker({ element, anchor: "center" }).setLngLat(coordinates).addTo(map),
    );
  };

  for (const mine of mines) {
    place(
      "mine",
      mine.name,
      mine.name,
      `${mine.name} — operating mine, ${mine.district}, ${mine.state}`,
      [mine.location.longitude, mine.location.latitude],
    );
  }
  // Targets last so a proposal never hides behind a mine at the same spot.
  for (const target of targets) {
    place(
      "target",
      target.id,
      target.id,
      `${target.id} — model target, ${target.label}`,
      [target.location.longitude, target.location.latitude],
    );
  }

  return () => {
    for (const marker of created) marker.remove();
  };
}
