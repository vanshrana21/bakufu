import { useId } from "react";
import { BAKUFU_PATHS as paths } from "@/components/brand/mark-geometry";

/** Chapter 00 material treatment; the shared brand geometry stays unchanged. */
export function HeroSeal({ className }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  const face = `${id}-face`;
  const edge = `${id}-edge`;
  const core = `${id}-core`;
  const body = `${paths.body}${paths.seam}`;

  return (
    <svg data-cinematic-seal className={className} viewBox="-8 -8 84 88" width="280" height="294" aria-hidden="true">
      <defs>
        <linearGradient data-seal-light id={face} x1="0" y1="0" x2="0.8" y2="1">
          <stop stopColor="var(--hero-ink)" />
          <stop offset="0.3" stopColor="var(--paper)" />
          <stop offset="0.55" stopColor="var(--hero-ink)" />
          <stop offset="1" stopColor="var(--hero-steel)" />
        </linearGradient>
        <clipPath id={`${id}-cut`}><path d={body} clipRule="evenodd" /></clipPath>
        <linearGradient id={`${id}-glint`}><stop stopColor="var(--hero-ink)" stopOpacity="0"/><stop offset="0.5" stopColor="var(--hero-ink)" stopOpacity="0.5"/><stop offset="1" stopColor="var(--hero-ink)" stopOpacity="0"/></linearGradient>
        <linearGradient id={edge} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="var(--hero-steel)" />
          <stop offset="0.48" stopColor="var(--shade-3)" />
          <stop offset="1" stopColor="var(--ground)" />
        </linearGradient>
        <linearGradient id={core} x1="0" y1="0" x2="1" y2="1">
          <stop stopColor="var(--paper)" />
          <stop offset="0.35" stopColor="var(--glow)" />
          <stop offset="1" stopColor="var(--ore)" />
        </linearGradient>
      </defs>
      <g transform="translate(0 1) rotate(-8 32 32)">
        {[5, 4, 3, 2, 1].map(depth => (
          <path key={depth} d={body} fillRule="evenodd" fill={`url(#${edge})`}
            transform={`translate(${depth * 0.45} ${depth})`} />
        ))}
        <path d={body} fillRule="evenodd" fill={`url(#${face})`} />
        <g clipPath={`url(#${id}-cut)`}><rect data-seal-glint x="-36" y="-10" width="24" height="90" fill={`url(#${id}-glint)`} transform="rotate(-22 32 32)" opacity="0" /></g>
        <path d={body} fillRule="evenodd" fill="none" stroke="var(--hero-ink)" strokeOpacity="0.5" strokeWidth="0.25" />
        <path d={paths.core} fill="var(--ore)" transform="translate(0.6 1.5)" />
        <path d={paths.core} fill={`url(#${core})`} stroke="var(--glow)" strokeWidth="0.25" />
      </g>
    </svg>
  );
}
