interface PatternRegistry {
  hasImage(name: string): boolean;
  addImage(name: string, image: { width: number; height: number; data: Uint8Array }, options: { pixelRatio: number }): unknown;
}

/** Semantic map exclusion pattern. Re-register on style.load, before addLayer.
 * 8×8 power-of-two sprite: two gray pixels / six transparent pixels per diagonal.
 * Never apply this pattern to unknown scope or use it as UI decoration. */
export function registerMaskPattern(map: PatternRegistry): void {
  if (map.hasImage("excluded-hatch")) return;
  const width = 8;
  const data = new Uint8Array(width * width * 4);
  for (let y = 0; y < width; y++) {
    for (let x = 0; x < width; x++) {
      const offset = (y * width + x) * 4;
      data[offset] = 185; data[offset + 1] = 196; data[offset + 2] = 204;
      data[offset + 3] = (x + y) % 8 < 2 ? 255 : 0;
    }
  }
  map.addImage("excluded-hatch", { width, height: width, data }, { pixelRatio: 1 });
}
