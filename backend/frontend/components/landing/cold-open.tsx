import Link from "next/link";
import localFont from "next/font/local";
import { Preloader } from "@/components/intro/preloader";
import { BakufuLockup } from "@/components/brand/logo-b";
import { HeroSeal } from "./hero-seal";
import { HeroMotion } from "./hero-motion";
import { CinematicMotion } from "./cinematic-motion";
import { TerrainAtmosphere } from "./terrain-atmosphere";
import h from "./hero.module.css";

// Self-hosted and scoped to Chapter 00; other chapters keep their typography.
const heroSans = localFont({
  src: "./fonts/public-sans-latin-variable.woff2",
  weight: "400 700",
  style: "normal",
  display: "swap",
  variable: "--font-hero",
  fallback: ["Arial", "sans-serif"],
});

export function ColdOpen() {
  return (
    <section className={`${h.hero} ${heroSans.variable}`} aria-labelledby="hero-heading" data-hero>
      <TerrainAtmosphere variant="hero" />
      <Preloader />
      <HeroMotion />
      <CinematicMotion />
      <header className={h.nav}>
        <a href="#story" className={h.brand} aria-label="Bakufu home">
          <BakufuLockup size={30} />
        </a>
        <span className={h.context}>Mineral intelligence<span>Sausar Belt, India</span></span>
        <Link href="/operations" className={h.workspace}>
          Open workspace <span aria-hidden="true">↗</span>
        </Link>
      </header>
      <div className={h.stage} aria-hidden="true">
        <span className={h.lift} data-hero-lift>
          <span className={h.settle} data-hero-settle>
            <span className={h.breath}>
              <HeroSeal className={h.seal} />
            </span>
          </span>
        </span>
      </div>
      <div className={h.copy}>
        <h1 id="hero-heading" className={`${h.statement} ${h.reveal}`} data-hero-statement>
          <span>Most of the belt</span>
          <span>has never been <em>drilled.</em></span>
        </h1>
        <p className={`${h.secondary} ${h.reveal}`} data-hero-secondary>
          We read it <strong>from orbit</strong> first.
        </p>
      </div>
      <div className={h.foot}>
        <span>SIH26009 / AN INDEPENDENT PROTOTYPE</span>
      </div>
      <noscript>
        <style>{"[data-hero] [data-hero-settle], [data-hero] [data-hero-statement], [data-hero] [data-hero-secondary] { opacity: 1 !important; } [data-hero] [data-hero-lift] { transform: translateY(-15vh) scale(1.08); }"}</style>
      </noscript>
    </section>
  );
}
