import { useId } from "react";

const sites = [{x:250,y:142,keep:true},{x:360,y:98,keep:false},{x:470,y:142,keep:true},{x:250,y:215,keep:false},{x:360,y:258,keep:true},{x:470,y:215,keep:false}];
const diamond = "M0-14 24 0 0 14-24 0Z";
/** Long normalized length so GSAP's whole-unit dash offsets still draw smoothly. */
export const SCREEN_LINE_LENGTH = 1000;

/** Conceptual screening, not actual sites or permission to mine. */
export function ScreeningVisual() {
  const id = useId().replace(/:/g, "");
  return <svg viewBox="0 0 720 710" role="img" aria-labelledby={`${id}-title ${id}-desc`}>
    <title id={`${id}-title`}>Candidate waste sites passing through screening</title>
    <desc id={`${id}-desc`}>Six illustrative candidates reach a screening plane. Three crossed sites stop; three copper-colored candidates continue below for review.</desc>
    <defs>
      <linearGradient id={`${id}-plate`} x2="1" y2="1"><stop stopColor="var(--screen-ink)" stopOpacity="0.7"/><stop offset="0.4" stopColor="var(--screen-steel)"/><stop offset="1" stopColor="var(--shade-3)"/></linearGradient>
      <linearGradient id={`${id}-core`} x2="0.7" y2="1"><stop stopColor="var(--paper)"/><stop offset="0.5" stopColor="var(--glow)"/><stop offset="1" stopColor="var(--ore)"/></linearGradient>
    </defs>
    <path d="M70 178 360 62 650 178 360 294Z" fill={`url(#${id}-plate)`} fillOpacity="0.34" stroke="var(--screen-steel)"/>
    <path d="M70 178V190L360 306 650 190V178L360 294Z" fill="var(--shade-3)"/>
    {sites.map(({x,y})=><g key={`${x}-${y}`} data-screen-candidate><g transform={`translate(${x} ${y})`}><path d="M0 14 24 0V7L0 21-24 7V0Z" fill="var(--screen-steel)"/><path d={diamond} fill="var(--screen-ink)"/></g></g>)}
    {sites.map(({x,y})=><path data-screen-inbound pathLength={SCREEN_LINE_LENGTH} key={`${x}-${y}`} d={`M${x} ${y+24}V${y+166}`} fill="none" stroke="var(--screen-steel)" strokeOpacity="0.7"/>)}
    <path d="M52 362 360 239 668 362 360 485Z" fill={`url(#${id}-plate)`}/>
    <path d="M52 362V385L360 508V485Z" fill="var(--shade-3)"/>
    <path d="M360 485 668 362V385L360 508Z" fill="var(--shade-2)"/>
    <path d="M52 362 360 485 668 362" fill="none" stroke="var(--screen-ink)" strokeOpacity="0.5"/>
    {sites.map(({x,y,keep})=><g key={`${x}-${y}`} data-screen-result><g transform={`translate(${x} ${y+184})`}><path d="M0-19 33 0 0 19-33 0Z" fill="var(--ground)" stroke={keep?"var(--glow)":"var(--screen-ink)"} strokeOpacity="0.65"/>{keep?<path d={diamond} fill={`url(#${id}-core)`}/>:<path d="M-11-6 11 6M-11 6 11-6" stroke="var(--screen-ink)" strokeWidth="2"/>}</g></g>)}
    {sites.filter(s=>s.keep).map(({x,y})=><g key={`${x}-${y}`}><path data-screen-outbound pathLength={SCREEN_LINE_LENGTH} d={`M${x} ${y+208}V${y+356}`} stroke="var(--glow)" strokeOpacity="0.5"/><g data-screen-retained><g transform={`translate(${x} ${y+380})`}><path d="M0-25 43 0 0 25-43 0Z" fill="none" stroke="var(--glow)" strokeOpacity="0.35"/><path d="M0 14 24 0V9L0 23-24 9V0Z" fill="var(--ore)"/><path d={diamond} fill={`url(#${id}-core)`}/></g></g></g>)}
    <g fill="var(--screen-ink)" fontFamily="var(--font-mono), monospace" fontSize="10" letterSpacing="1"><text x="54" y="120">CANDIDATES</text><text x="54" y="328">SCREENING</text><text x="54" y="576" fill="var(--paper)">RETAINED FOR REVIEW</text></g>
  </svg>;
}
