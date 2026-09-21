import { useId } from "react";

/** A conceptual ground section, not a mineral map or an assay result. */
export function WasteCutaway() {
  const id = useId().replace(/:/g, "");
  const metal = `${id}-metal`;
  const side = `${id}-side`;
  const copper = `${id}-copper`;
  const shadow = `${id}-shadow`;
  return (
    <svg viewBox="0 0 700 660" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
      <title id={`${id}-title`}>Layered ground with a concealed ore body</title>
      <desc id={`${id}-desc`}>An illustrative cutaway of stacked strata. Copper-colored internal facets symbolize possible manganese, not measured ore.</desc>
      <defs>
        <linearGradient id={metal} x1="0" y1="0" x2="0.85" y2="1">
          <stop stopColor="var(--waste-ink)" />
          <stop offset="0.48" stopColor="var(--waste-steel)" />
          <stop offset="1" stopColor="var(--shade-3)" />
        </linearGradient>
        <linearGradient id={side} x1="0" y1="0" x2="1" y2="0.8">
          <stop stopColor="var(--waste-steel)" />
          <stop offset="0.5" stopColor="var(--shade-3)" />
          <stop offset="1" stopColor="var(--ground)" />
        </linearGradient>
        <linearGradient id={copper} x1="0" y1="0" x2="0.8" y2="1">
          <stop stopColor="var(--paper)" />
          <stop offset="0.42" stopColor="var(--glow)" />
          <stop offset="1" stopColor="var(--ore)" />
        </linearGradient>
        <radialGradient id={shadow}>
          <stop stopColor="var(--ground)" stopOpacity="0.9" />
          <stop offset="1" stopColor="var(--ground)" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx="357" cy="541" rx="323" ry="99" fill={`url(#${shadow})`} />
      {/* Lower strata: top surfaces, illuminated fronts and dark return faces. */}
      {[112, 73, 34].map((y, i) => (
        <g key={y} data-waste-layer><g transform={`translate(0 ${y})`}>
          <path d="M79 277 302 151 615 276 395 433Z" fill={`url(#${metal})`} />
          <path d="M79 277 395 433V461L79 305Z" fill={`url(#${side})`} />
          <path d="M395 433 615 276V304L395 461Z" fill="var(--shade-2)" />
          <path d="M79 277 395 433 615 276" fill="none" stroke="var(--waste-ink)" strokeOpacity={0.2 + i * 0.08} strokeWidth="1" />
          <path d="M94 295 171 331 205 346 250 369M422 429 491 381 526 360" fill="none" stroke="var(--waste-steel)" strokeOpacity="0.45" />
        </g></g>
      ))}
      {/* Exposed inclusion spans the cut, rather than floating above the sample. */}
      <g data-waste-core>
      <path d="M117 286 291 211 556 282 410 418 344 430Z" fill="var(--ore)" />
      <path d="M117 286 293 228 357 308 278 367Z" fill={`url(#${copper})`} />
      <path d="M293 228 461 267 357 308Z" fill="var(--paper)" />
      <path d="M357 308 461 267 556 282 410 418Z" fill={`url(#${copper})`} />
      <path d="M278 367 357 308 410 418 344 430Z" fill="var(--glow)" />
      <path d="M278 367 344 430V447L278 385ZM344 430 410 418V434L344 447Z" fill="var(--ore)" />
      <path d="M293 228 357 308 410 418M357 308 278 367" fill="none" stroke="var(--paper)" strokeOpacity="0.55" strokeWidth="1.2" />
      {/* Upper waste block is split along a wedge to expose the interior. */}
      </g>
      <g data-waste-lid>
      <path d="M73 192 298 62 616 187 499 272 376 222 296 310 73 222Z" fill={`url(#${metal})`} />
      <path d="M73 222 296 310V374L73 279Z" fill={`url(#${side})`} />
      <path d="M296 310 376 222V286L296 374Z" fill="var(--shade-2)" />
      <path d="M376 222 499 272V335L376 286Z" fill={`url(#${side})`} />
      <path d="M499 272 616 187V251L499 335Z" fill="var(--shade-3)" />
      <path d="M73 192 210 130 285 185 174 237Z" fill="var(--waste-ink)" fillOpacity="0.18" />
      <path d="M210 130 298 62 399 143 285 185Z" fill="var(--waste-ink)" fillOpacity="0.1" />
      <path d="M399 143 616 187 499 272 376 222Z" fill="var(--ground)" fillOpacity="0.22" />
      <path d="M174 237 285 185 376 222 296 310Z" fill="var(--waste-steel)" fillOpacity="0.4" />
      <path d="M73 192 298 62 616 187 499 272 376 222 296 310 73 222M73 242 296 333M73 261 296 354M499 292 616 207M499 313 616 229" fill="none" stroke="var(--waste-ink)" strokeOpacity="0.28" strokeWidth="1" />
      <path d="M296 310 376 222 499 272" fill="none" stroke="var(--paper)" strokeOpacity="0.6" strokeWidth="1.5" />
      </g>
    </svg>
  );
}
