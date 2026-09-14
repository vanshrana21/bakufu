import { useId } from "react";
import { BAKUFU_COLORS as C, BAKUFU_PATHS as P, BAKUFU_VIEWBOX } from "./mark-geometry";
import s from "./logo-b.module.css";

/** Body with the strata cut and core seat removed, as one even-odd shape. */
const CUT_BODY = `${P.body}${P.seam}`;

type MarkProps = {
  size?: number;
  /** "mark": the flat stamp. "hero": the same stamp plus the drawable outline
   * and scan paths that the preloader animates. */
  variant?: "mark" | "hero";
  /** Single-colour: the core takes currentColor and is separated from the body
   * by the cut alone. */
  monochrome?: boolean;
  className?: string;
  title?: string;
};

/** Benched kikkō with a gold reserve seated on its strata cut. */
export function BakufuMark({ size = 28, variant = "mark", monochrome = false, className, title }: MarkProps) {
  const hero = variant === "hero";
  return <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox={BAKUFU_VIEWBOX}
    className={`${s.mark} ${className ?? ""}`} data-variant={variant}
    role={title ? "img" : undefined} aria-hidden={title ? undefined : true}>
    {title && <title>{title}</title>}
    <path data-logo="body" d={CUT_BODY} fillRule="evenodd" fill="currentColor" />
    {hero && <>
      <path data-logo="frame" d={P.body} pathLength={88} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="miter" />
      <path data-logo="strata" d={P.scan} pathLength={88} fill="none" {...(monochrome ? { stroke: "currentColor" } : { className: s.scan })} strokeWidth="1.2" />
    </>}
    <path data-logo="reserve-core" d={P.core} {...(monochrome ? { fill: "currentColor" } : { className: s.core })} />
  </svg>;
}

/** Flat-top hexagon of circumradius r centred on the origin. */
const kikko = (r: number) => {
  const h = +(r * Math.sqrt(3) / 2).toFixed(2);
  return `M${-r} 0 ${-r / 2} ${-h}H${r / 2}L${r} 0 ${r / 2} ${h}H${-r / 2}Z`;
};

/** The ch00 medallion: a coin with a tick ring and a hairline kikkō (maru ni
 * kikkō), carrying the mark carved into it. The shade copies under the body show
 * through the cut as depth. Seal colours are fixed: it only appears on a dark ground. */
export function BakufuSeal({ size = 470, className, title }: { size?: number; className?: string; title?: string }) {
  const glow = `bakufu-core-${useId().replace(/:/g, "")}`;
  return <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 100 100"
    className={`${s.mark} ${className ?? ""}`} data-variant="seal"
    role={title ? "img" : undefined} aria-hidden={title ? undefined : true}>
    {title && <title>{title}</title>}
    <defs>
      <filter id={glow} x="-100%" y="-100%" width="300%" height="300%" colorInterpolationFilters="sRGB">
        <feDropShadow dx="0" dy="0" stdDeviation="1.6" floodColor={C.glow} floodOpacity="0.7" />
      </filter>
    </defs>
    <g transform="translate(50 46) rotate(-12)">
      {[6, 4.5, 3, 1.5].map((y) => <circle key={y} cy={y} r="40" fill={C.shade2} stroke={C.shade3} strokeWidth="0.7" />)}
      <circle r="40" fill={C.shade1} stroke={C.paper} strokeWidth="0.8" />
      <circle r="36.5" fill="none" stroke={C.paper} strokeOpacity="0.35" strokeWidth="0.6" />
      {Array.from({ length: 32 }, (_, i) => <path key={i} d="M0-39.2V-37.4" transform={`rotate(${i * 11.25})`} stroke={C.paper} strokeOpacity="0.45" strokeWidth="0.7" />)}
      <path d={kikko(31)} fill="none" stroke={C.paper} strokeWidth="0.5" strokeOpacity="0.55" />
      <g transform="translate(-24 -24) scale(0.75)">
        {[3, 2, 1].map((y) => <path key={y} d={CUT_BODY} transform={`translate(0 ${y})`} fillRule="evenodd" fill={C.shade3} />)}
        <path d={CUT_BODY} fillRule="evenodd" fill={C.paper} />
        <path d={P.core} fill={C.glow} filter={`url(#${glow})`} />
      </g>
    </g>
  </svg>;
}

export function BakufuLockup({ size = 32, className }: { size?: number; className?: string }) {
  return <span className={`${s.lockup} ${className ?? ""}`}>
    <BakufuMark size={size} />
    <span className={s.name}>BAKUFU</span>
    <span className={s.japanese} lang="ja">幕府</span>
  </span>;
}
