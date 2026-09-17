"use client";

import { useEffect, useState, useRef } from "react";
import { ArrowUpRight, TrendingDown, TrendingUp } from "lucide-react";
import Link from "next/link";
import s from "../../app/(workspace)/operations/briefing.module.css";
import type { HistoricalPoint } from "./production-chart";

function usePrintIn(delayMs: number, disable: boolean) {
  const [visible, setVisible] = useState(false);
  
  useEffect(() => {
    if (disable) return;
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      setVisible(true);
      return;
    }
    let observer: IntersectionObserver;
    let el = document.getElementById("metric-row");
    if (!el) {
      setVisible(true);
      return;
    }

    observer = new IntersectionObserver((entries) => {
      if (entries[0]?.isIntersecting) {
        setTimeout(() => setVisible(true), delayMs);
        observer.disconnect();
      }
    });
    observer.observe(el);

    return () => observer.disconnect();
  }, [delayMs, disable]);

  return visible;
}

function Corners() {
  return <>
    <svg className={s.cornerTick} style={{ top: 0, left: 0 }} viewBox="0 0 10 10"><path d="M 0,10 L 0,0 L 10,0" /></svg>
    <svg className={s.cornerTick} style={{ top: 0, right: 0 }} viewBox="0 0 10 10"><path d="M 0,0 L 10,0 L 10,10" /></svg>
    <svg className={s.cornerTick} style={{ bottom: 0, right: 0 }} viewBox="0 0 10 10"><path d="M 10,0 L 10,10 L 0,10" /></svg>
    <svg className={s.cornerTick} style={{ bottom: 0, left: 0 }} viewBox="0 0 10 10"><path d="M 10,10 L 0,10 L 0,0" /></svg>
  </>;
}

export function VitalTiles({ latest, next, risk, proposed, drafts, change, history, firstForecast, live, registerData }: any) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const prodStr = latest && !latest.unavailable ? latest.value : "—";
  const nextStr = next && !next.unavailable ? next.value : "—";
  const riskStr = risk && !risk.unavailable ? risk.value : "—";
  const proposedStr = String(proposed).padStart(2, "0");

  const pVis = usePrintIn(60, !mounted);
  const nVis = usePrintIn(120, !mounted);
  const rVis = usePrintIn(180, !mounted);
  const prVis = usePrintIn(240, !mounted);

  const riskNum = riskStr !== "—" ? parseFloat(riskStr.replace("%","")) : 0;
  const riskColor = riskNum >= 30 ? "var(--brick)" : "var(--moss)";
  const riskTicks = Math.round(riskNum / 10);
  const riskLevelText = riskStr !== "—" ? "below 90% of issued forecast" : (risk?.note ?? "Read event definition and calibration below");

  const prefersReduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const baseStyle = mounted ? { transform: "translateY(0)", opacity: 1 } : { transform: "translateY(8px)", opacity: 0 };
  const getStyle = (delay: number) => (prefersReduced || !mounted ? undefined : { ...baseStyle, transition: `transform 400ms ease ${delay}ms, opacity 400ms ease ${delay}ms` });

  const getNumStyle = (vis: boolean) => (prefersReduced || !mounted ? { fontVariantNumeric: "tabular-nums" } : { fontVariantNumeric: "tabular-nums", opacity: vis ? 1 : 0, filter: vis ? "blur(0)" : "blur(4px)", transition: "opacity 200ms ease, filter 200ms ease" });

  return (
    <section id="metric-row" className={s.metrics} aria-label="Operational vital signs">
      <article className={s.metric} data-kind="observed" style={getStyle(60)}>
        <Corners />
        <div className={s.metricLabel}>
          {live && <span className={`${s.pulseDot} ${s.pulseMoss}`} />}
          Latest production<span>tonnes</span>
        </div>
        <p className={s.metricValue} style={getNumStyle(pVis)}>{prodStr === "—" ? "—" : <>{prodStr}<sup>t</sup></>}</p>
        
        <div className={s.microVisual} aria-hidden="true">
          <svg viewBox="0 0 100 28" preserveAspectRatio="none">
             {history && history.length > 0 && (() => {
               const max = Math.max(...history.map((h:any) => h.tonnes));
               const min = Math.min(...history.map((h:any) => h.tonnes));
               const range = max - min || 1;
               const pts = history.map((h:any, i:number) => {
                 const x = (i / (history.length - 1)) * 100;
                 const y = 28 - ((h.tonnes - min) / range) * 24 - 2;
                 return `${x},${y}`;
               });
               const lastPt = pts[pts.length - 1].split(',');
               return <>
                 <polyline points={pts.join(' ')} fill="none" stroke="var(--observed)" strokeWidth="1.5" />
                 <circle cx={lastPt[0]} cy={lastPt[1]} r="2" fill="var(--observed)" />
               </>;
             })()}
          </svg>
        </div>
        
        <div className={s.metricFootWrapper}>
          <p className={s.metricFoot}>{change === null ? (latest?.note ?? "Latest reported month") : <>{change >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}<span data-tone={change >= 0 ? "good" : undefined}>{change > 0 ? "+" : ""}{change.toFixed(1)}%</span> vs previous month</>}</p>
        </div>
      </article>

      <article className={s.metric} data-kind="model" style={getStyle(120)}>
        <Corners />
        <div className={s.metricLabel}>
          {live && <span className={`${s.pulseDot} ${s.pulseMoss}`} />}
          Next-month forecast<span>tonnes</span>
        </div>
        <p className={s.metricValue} style={getNumStyle(nVis)}>{nextStr === "—" ? "—" : <>{nextStr}<sup>t</sup></>}</p>
        
        <div className={s.microVisual} aria-hidden="true">
          <svg viewBox="0 0 100 28" preserveAspectRatio="none">
            {firstForecast && firstForecast.lower_bound !== null && firstForecast.upper_bound !== null && (() => {
               const lb = firstForecast.lower_bound;
               const ub = firstForecast.upper_bound;
               const pe = firstForecast.point_estimate;
               const min = lb - (ub - lb)*0.5;
               const max = ub + (ub - lb)*0.5;
               const range = max - min || 1;
               const getX = (val:number) => ((val - min) / range) * 100;
               return <>
                 <rect x={getX(lb)} y="8" width={getX(ub) - getX(lb)} height="12" fill="var(--signal)" opacity="0.28" />
                 <line x1={getX(pe)} y1="6" x2={getX(pe)} y2="22" stroke="var(--signal)" strokeWidth="1.5" strokeDasharray="2 2" />
               </>;
            })()}
          </svg>
        </div>

        <div className={s.metricFootWrapper}>
          <p className={s.metricFoot}>{next?.unavailable ? next.note : "Point estimate · interval shown below"}</p>
        </div>
      </article>

      <article className={s.metric} data-kind="model" style={{ ...getStyle(180), '--kind-ink': riskColor } as any}>
        <Corners />
        <div className={s.metricLabel}>
          {live && <span className={`${s.pulseDot} ${s.pulseMoss}`} />}
          Downside risk<span>forecast-relative</span>
        </div>
        <p className={s.metricValue} data-testid="vital-risk" style={getNumStyle(rVis)}>{riskStr === "—" ? "—" : <>{riskStr}<sup>%</sup></>}</p>

        <div className={s.microVisual} aria-hidden="true" style={{ display: 'flex', gap: '2px', alignItems: 'center', height: '28px' }}>
          {Array.from({length: 10}).map((_, i) => (
            <div key={i} style={{ flex: 1, height: '8px', background: i < riskTicks ? riskColor : 'var(--border)' }} />
          ))}
        </div>

        <div className={s.metricFootWrapper}>
          <p className={s.metricFoot}>{risk?.unavailable ? risk.note : riskLevelText}</p>
        </div>
      </article>

      <article className={s.metric} data-kind="action" style={getStyle(240)}>
        <Corners />
        <div className={s.metricLabel}>
          <span className={`${s.pulseDot} ${s.pulseCopper}`} />
          Pending reviews<Link href="/actions" aria-label="View corrective actions"><ArrowUpRight size={15} /></Link>
        </div>
        <p className={s.metricValue} style={getNumStyle(prVis)}>{proposedStr === "—" ? "—" : proposedStr}<small>{registerData ? `${drafts} draft` : "unavailable"}</small></p>

        <div className={s.microVisual} aria-hidden="true" style={{ display: 'flex', gap: '4px', alignItems: 'flex-end', height: '28px', paddingBottom: '4px' }}>
          {Array.from({length: Math.max(1, proposed)}).map((_, i) => (
             <div key={`p-${i}`} style={{ width: '8px', height: '12px', background: proposed > 0 ? 'var(--action)' : 'transparent', border: '1px solid var(--action)' }} />
          ))}
          {Array.from({length: Math.max(0, drafts)}).map((_, i) => (
             <div key={`d-${i}`} style={{ width: '8px', height: '12px', border: '1px solid var(--action)' }} />
          ))}
        </div>

        <div className={s.metricFootWrapper}>
          <p className={s.metricFoot}>{registerData ? "drafts are not proposals yet" : "Recommendations unavailable"}</p>
        </div>
      </article>
    </section>
  );
}
