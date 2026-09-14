"use client";

import { useEffect } from "react";
import { gsap } from "gsap";
import { isPreloaderRunning, whenPreloaderDone } from "@/components/intro/preloader";

const HERO = {
  loaderSealSize: 140,
  settle: { duration: 1.4, ease: "power2.inOut" },
  surface: { duration: 1.2, ease: "power1.inOut", fromScale: 0.96 },
  glow: {
    handoff: { blur: "6px", strength: "12%", opacity: 0.92 },
    rest: { blur: "5px", strength: "8%" },
  },
} as const;

function introduceSeal(root: HTMLElement) {
  const settle = root.querySelector<HTMLElement>("[data-hero-settle]");
  if (!settle) return () => {};

  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    gsap.set(settle, { opacity: 1, scale: 1 });
    root.dataset.heroReady = "";
    return () => {};
  }

  const { handoff, rest } = HERO.glow;
  let tween: gsap.core.Tween | undefined;

  const settleIn = () => {
    tween = gsap.to(settle, {
      opacity: 1,
      scale: 1,
      "--glow-blur": rest.blur,
      "--glow-strength": rest.strength,
      ...HERO.settle,
      onComplete: () => {
        root.dataset.heroReady = "";
      },
    });
  };

  if (isPreloaderRunning()) {
    gsap.set(settle, {
      opacity: handoff.opacity,
      scale: HERO.loaderSealSize / settle.offsetWidth,
      "--glow-blur": handoff.blur,
      "--glow-strength": handoff.strength,
    });
    const stopWaiting = whenPreloaderDone(settleIn);
    return () => {
      stopWaiting();
      tween?.kill();
      delete root.dataset.heroReady;
    };
  }

  tween = gsap.fromTo(settle,
    { opacity: 0, scale: HERO.surface.fromScale },
    { opacity: 1, scale: 1, duration: HERO.surface.duration, ease: HERO.surface.ease, onComplete: () => {
      root.dataset.heroReady = "";
    } });

  return () => {
    tween?.kill();
    delete root.dataset.heroReady;
  };
}

export function HeroMotion() {
  useEffect(() => {
    const root = document.querySelector<HTMLElement>("[data-hero]");
    if (!root) return;
    return introduceSeal(root);
  }, []);
  return null;
}
