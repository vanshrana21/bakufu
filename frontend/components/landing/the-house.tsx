"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { AvneshMark } from "@/components/brand/logo-b";
import { ChapterLabel } from "./shared";
import s from "./story.module.css";
import d from "./house-deck.module.css";

/* Each room gets a chunky 7x7 pixel glyph, drawn for its job. */
const GLYPHS = {
  command: ["111.111", "111.111", "111.111", ".......", "111.111", "111.111", "111.111"],
  prospect: ["...1...", "..111..", ".11111.", "1111111", ".11111.", "..111..", "...1..."],
  production: ["......1", "....1.1", "....1.1", "..1.1.1", "..1.1.1", "1.1.1.1", "1.1.1.1"],
  actions: [".......", "......1", ".....11", "1...11.", "11.11..", ".111...", "..1...."],
  assets: ["1111111", "1.....1", "1111111", "1.....1", "1.....1", "1.....1", "1111111"],
  feedback: ["1111111", "1111111", "11...11", "1111111", "1111111", ".11....", ".1....."],
  pipeline: ["111....", "111....", "111....", "1111111", "1111111", "....111", "....111"],
  compliance: ["1111111", "1111111", "1111111", "1111111", ".11111.", "..111..", "...1..."],
  reports: ["11111..", "1...11.", "1.....1", "1.111.1", "1.....1", "1.111.1", "1111111"],
  admin: ["..111..", ".1...1.", ".1...1.", "1111111", "1111111", "111.111", "1111111"],
} as const;

/* Four hero rooms, then six supporting ones. Each list names real sections
 * of that room's page. */
const modules = [
  { title: "COMMAND CENTER", href: "/operations", lines: ["Vital signs", "Forecast + risk", "Review queue"], glyph: GLYPHS.command },
  { title: "PROSPECTIVITY", href: "/explorer", lines: ["1,024-cell heatmap", "Masks + Ghost Reserves", 'SHAP "why?"'], glyph: GLYPHS.prospect },
  { title: "PRODUCTION & RISK", href: "/production", lines: ["80% intervals", "Shortfall gauge", "Evidence rail"], glyph: GLYPHS.production },
  { title: "CORRECTIVE ACTIONS", href: "/actions", lines: ["Rule triggers", "Human review", "Audit trail"], glyph: GLYPHS.actions },
  { title: "ASSETS", href: "/assets", lines: ["Mine operations", "Ghost Reserve inventory", "Equipment fleet"], glyph: GLYPHS.assets },
  { title: "FEEDBACK", href: "/feedback", lines: ["Site context", "Annotation register", "Reports start reviews"], glyph: GLYPHS.feedback },
  { title: "PIPELINE", href: "/pipeline", lines: ["Ingestion health", "Model registry", "Retraining log"], glyph: GLYPHS.pipeline },
  { title: "COMPLIANCE", href: "/compliance", lines: ["Compliance health", "Permits + clearances", "Audit + inspections"], glyph: GLYPHS.compliance },
  { title: "REPORTS", href: "/reports", lines: ["Report templates", "Configure exports", "Recent exports"], glyph: GLYPHS.reports },
  { title: "ADMIN / RBAC", href: "/admin", lines: ["Users", "Role permissions", "System audit log"], glyph: GLYPHS.admin },
] as const;

/* Deck geometry, in degrees and pixels. */
const JITTER = [-2.4, 1.6, -0.9, 2.1, -1.8, 1.1, -2.7, 0.7, -1.3, 2.6];
const HERO_FAN = [-18, -6, 6, 18];
const HERO_ARC = [0, 14, 14, 0]; // inner cards sit lower in the hand
const SMALL_FAN = [-12, -7, -2.5, 2.5, 7, 12];
const SMALL_ARC = [0, 7, 11, 11, 7, 0];

/* Beat timing in timeline units (0-10). The pin spreads them over 400% of the
 * viewport and scrub 1.5 trails the scroll, so every beat moves like silk. */
const BEATS = {
  stack: { at: 0, duration: 1.6 },
  fan: { at: 1.6, duration: 1.8, ease: "power2.inOut" },
  flip: { at: 3.8, duration: 1.0, ease: "power3.out", stagger: 0.06 },
  settle: { at: 5.6, duration: 1.2, ease: "power2.out" },
  deal: { at: 6.6, duration: 1.0, ease: "power2.inOut", stagger: 0.04 },
  dealFlip: { at: 7.1, duration: 0.7, ease: "power3.out", stagger: 0.04 },
  rest: { at: 8.2, duration: 1.0, ease: "power2.out" },
  end: 10,
} as const;

const pad = (n: number) => String(n).padStart(2, "0");

function PixelGlyph({ rows }: { rows: readonly string[] }) {
  return <svg className={d.glyph} viewBox="0 0 7 7" shapeRendering="crispEdges" aria-hidden="true">
    {rows.flatMap((row, y) => Array.from(row).map((cell, x) =>
      cell === "1" ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" /> : null))}
  </svg>;
}

/** AVNESH's own back: strata, an off-centre yantra crest, one exclusion hatch
 * band, vertical microtext and a tiny index. */
function CardBack({ index }: { index: number }) {
  return <span className={d.back} aria-hidden="true">
    <span className={d.strata}><i /><i /><i /><i /></span>
    <span className={d.hatch} />
    <AvneshMark size={48} className={d.backCrest} />
    <span className={d.micro}>AVNESH अवनीश — SCREENED MATERIAL</span>
    <span className={d.backIndex}>{pad(index)}</span>
  </span>;
}

export function TheHouse() {
  const stageRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    let disposed = false;
    media.add("(min-width: 900px) and (prefers-reduced-motion: no-preference)", () => {
      const cards = gsap.utils.toArray<HTMLElement>("[data-deal-card]", stage);
      const rotors = gsap.utils.toArray<HTMLElement>("[data-card-rotor]", stage);
      const heroes = cards.slice(0, 4);
      const small = cards.slice(4);
      // Offsets that put a card's centre on the stage centre. Every card in a
      // group shares that centre, so their 50% 120% origins share one pivot.
      const toCentreX = (card: HTMLElement) => stage.clientWidth / 2 - card.offsetLeft - card.offsetWidth / 2;
      const toCentreY = (card: HTMLElement) => stage.clientHeight / 2 - card.offsetTop - card.offsetHeight / 2;
      // Each card is its own 3D context on a flat stage, so a card turning on
      // its Y axis never cuts through its neighbours; z-index sets the stack.
      cards.forEach((card, i) => {
        gsap.set(card, { zIndex: i < 4 ? 7 + i : i - 3 });
      });

      const timeline = gsap.timeline({
        defaults: { ease: "power2.inOut" },
        scrollTrigger: {
          id: "house-deck", trigger: stage, start: "top 24px", end: "+=400%",
          pin: true, scrub: 1.5, anticipatePin: 1, invalidateOnRefresh: true,
          // Earlier chapters also pin: measure this deck after their added scroll distance.
          refreshPriority: -1,
          onUpdate: (self) => { stage.dataset.dealProgress = self.progress.toFixed(3); },
          onRefresh: (self) => {
            stage.dataset.dealStart = String(Math.round(self.start));
            stage.dataset.dealEnd = String(Math.round(self.end));
          },
        },
      });

      // Beat 1, stack: ten cards face-down on one centre, jittered, drifting up.
      timeline.fromTo(cards, {
        x: (i: number, card: HTMLElement) => toCentreX(card) + ((i * 7) % 5) - 2,
        y: (i: number, card: HTMLElement) => toCentreY(card) + 44 + ((i * 3) % 4),
        rotation: (i: number) => (JITTER[i] ?? 0) * 1.5,
      }, {
        y: (i: number, card: HTMLElement) => toCentreY(card) + ((i * 3) % 4),
        rotation: (i: number) => JITTER[i] ?? 0,
        duration: BEATS.stack.duration, ease: "none",
      }, BEATS.stack.at);

      // Beat 2, fan: the four spread together around the shared pivot, still face-down.
      timeline.to(heroes, {
        x: (_: number, card: HTMLElement) => toCentreX(card),
        y: (i: number, card: HTMLElement) => toCentreY(card) + (HERO_ARC[i] ?? 0),
        rotation: (i: number) => HERO_FAN[i] ?? 0,
        duration: BEATS.fan.duration, ease: BEATS.fan.ease,
      }, BEATS.fan.at);

      // Beat 3, flip: each hero turns on its own Y axis while the fan holds.
      timeline.fromTo(rotors.slice(0, 4), { rotationY: 180 }, {
        rotationY: 0, duration: BEATS.flip.duration, ease: BEATS.flip.ease, stagger: BEATS.flip.stagger,
      }, BEATS.flip.at);

      // Beat 4a, settle: the fan relaxes into a straight row of four, as on lusion.co.
      timeline.to(heroes, {
        x: 0, y: 0, rotation: 0,
        duration: BEATS.settle.duration, ease: BEATS.settle.ease,
      }, BEATS.settle.at);

      // Beat 4b, deal: the six slide out from behind the row into a smaller fan
      // below it, flip face-up in quick succession, then take their places.
      timeline.to(small, {
        // Centred horizontally, kept in their own row: one pivot under the four.
        x: (_: number, card: HTMLElement) => toCentreX(card),
        y: (i: number) => SMALL_ARC[i] ?? 0,
        rotation: (i: number) => SMALL_FAN[i] ?? 0,
        duration: BEATS.deal.duration, ease: BEATS.deal.ease, stagger: BEATS.deal.stagger,
      }, BEATS.deal.at);
      timeline.fromTo(rotors.slice(4), { rotationY: 180 }, {
        rotationY: 0, duration: BEATS.dealFlip.duration, ease: BEATS.dealFlip.ease, stagger: BEATS.dealFlip.stagger,
      }, BEATS.dealFlip.at);
      timeline.to(small, {
        x: 0, y: 0, rotation: 0,
        duration: BEATS.rest.duration, ease: BEATS.rest.ease,
      }, BEATS.rest.at);

      // Beat 5, release: rest until the end of the pin, then let go.
      timeline.to({}, { duration: BEATS.end - timeline.duration() });

      // Keyboard entry reveals all ten links instead of focusing an obscured face.
      const revealForKeyboard = () => {
        const trigger = timeline.scrollTrigger;
        if (trigger && trigger.progress < 1) {
          window.scrollTo({ top: trigger.end, behavior: "instant" });
          ScrollTrigger.update();
        }
      };
      stage.addEventListener("focusin", revealForKeyboard);
      return () => stage.removeEventListener("focusin", revealForKeyboard);
    });
    media.add("(max-width: 899px) and (prefers-reduced-motion: no-preference)", () => {
      stage.querySelectorAll<HTMLElement>("[data-deal-card]").forEach((card, i) => {
        gsap.from(card, { y: 24, opacity: 0, duration: 0.5, delay: (i % 3) * 0.08, ease: "power2.out",
          scrollTrigger: { trigger: card, start: "top 92%", once: true } });
      });
    });
    void document.fonts.ready.then(() => {
      if (!disposed) { ScrollTrigger.sort(); ScrollTrigger.refresh(); }
    });
    return () => { disposed = true; media.revert(); };
  }, []);
  return (
    <section id="house" className={`${s.chapter} ${s.house} ${d.house}`} aria-labelledby="house-heading">
      <ChapterLabel number="08">THE HOUSE / TEN CONNECTED ROOMS</ChapterLabel>
      <div className={s.sectionIntro}>
        <h2 id="house-heading" className={s.display}>NOT A DEMO<br /><span className={s.outline}>DEAD END.</span></h2>
        <p>One story. Ten working destinations.<br />Enter anywhere. Inspect everything.</p>
      </div>
      <nav ref={stageRef} className={d.stage} aria-label="Workspace modules">
        {modules.map((module, i) => (
          <Link key={module.href} href={module.href} prefetch={false}
            className={`${d.card} ${i < 4 ? d.hero : d.small}`} data-deal-card
            aria-label={`${pad(i + 1)} ${module.title} — ${module.lines.join(" · ")}`}>
            <span className={d.lift}><span className={d.rotor} data-card-rotor>
              <CardBack index={i + 1} />
              <span className={d.face}>
                <span className={d.header}>
                  <span className={d.title}>{module.title}</span>
                  <PixelGlyph rows={module.glyph} />
                </span>
                <span className={d.list}>
                  {module.lines.map((line) => <span key={line} className={d.item}>{line}</span>)}
                </span>
                <span className={`${d.header} ${d.mirror}`} aria-hidden="true">
                  <span className={d.title}>{module.title}</span>
                  <PixelGlyph rows={module.glyph} />
                </span>
              </span>
            </span></span>
          </Link>
        ))}
      </nav>
      <p className={`${s.footnote} ${d.disclaimer}`}>
        The workspace is a prototype. Demo data, simulated workflows and
        scientific limitations remain labelled in each module. Role previews are
        not server-enforced authorization.
      </p>
    </section>
  );
}
