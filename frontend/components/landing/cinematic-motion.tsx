"use client";

import { useEffect } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { whenPreloaderDone } from "@/components/intro/preloader";
import { SCREEN_LINE_LENGTH } from "@/components/landing/screening-visual";

/** Only the first three illustrations move. Copy and real data never animate here. */
export function CinematicMotion() {
  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    let disposed = false;

    media.add("(prefers-reduced-motion: no-preference)", () => {
      const context = gsap.context(() => {
        const waste = document.querySelector<HTMLElement>("#waste");
        const ghost = document.querySelector<HTMLElement>("#ghost");
        if (waste) {
          const timeline = gsap.timeline({
            defaults: { ease: "power2.inOut" },
            scrollTrigger: {
              id: "avnesh-waste-cutaway", trigger: waste.querySelector("figure") ?? waste,
              start: "top 90%", end: "center 45%", scrub: 0.7,
              invalidateOnRefresh: true,
            },
          });
          timeline.fromTo(waste.querySelector("[data-waste-lid]"), { y: 48 }, { y: -28, duration: 1 }, 0);
          timeline.fromTo(waste.querySelectorAll("[data-waste-layer]"),
            { y: (i: number) => -(3 - i) * 11 },
            { y: (i: number) => (3 - i) * 5, duration: 1 }, 0);
          timeline.fromTo(waste.querySelector("[data-waste-core]"),
            { opacity: 0.25, scale: 0.94, transformOrigin: "50% 50%" },
            { opacity: 1, scale: 1, duration: 0.65 }, 0.25);
        }
        if (ghost) {
          const timeline = gsap.timeline({
            defaults: { ease: "power2.out" },
            scrollTrigger: {
              id: "avnesh-screening", trigger: ghost.querySelector("figure") ?? ghost,
              start: "top 90%", end: "center 40%", scrub: 0.65,
              invalidateOnRefresh: true,
            },
          });
          timeline.fromTo(ghost.querySelectorAll("[data-screen-candidate]"),
            { y: -26, opacity: 0.35 }, { y: 0, opacity: 1, stagger: 0.04, duration: 0.3 }, 0);
          const inbound = gsap.utils.toArray<SVGPathElement>(ghost.querySelectorAll("[data-screen-inbound]"));
          const outbound = gsap.utils.toArray<SVGPathElement>(ghost.querySelectorAll("[data-screen-outbound]"));
          // Hide every line up front; a staggered fromTo only primes its first target.
          gsap.set([...inbound, ...outbound], { strokeDasharray: SCREEN_LINE_LENGTH, strokeDashoffset: SCREEN_LINE_LENGTH });
          timeline.fromTo(inbound,
            { strokeDashoffset: SCREEN_LINE_LENGTH }, { strokeDashoffset: 0, ease: "none", stagger: 0.025, duration: 0.35 }, 0.15);
          timeline.fromTo(ghost.querySelectorAll("[data-screen-result]"),
            { opacity: 0.2 }, { opacity: 1, stagger: 0.04, duration: 0.25 }, 0.45);
          timeline.fromTo(outbound,
            { strokeDashoffset: SCREEN_LINE_LENGTH }, { strokeDashoffset: 0, ease: "none", stagger: 0.06, duration: 0.4 }, 0.7);
          timeline.fromTo(ghost.querySelectorAll("[data-screen-retained]"),
            { y: -18, opacity: 0.15 }, { y: 0, opacity: 1, stagger: 0.06, duration: 0.3 }, 1);
        }
      });
      // The highlight waits for the existing loader; it never obscures content.
      const stopWaiting = whenPreloaderDone(() => context.add(() => {
        const glint = document.querySelector("[data-seal-glint]");
        if (!glint) return;
        gsap.timeline().set(glint, { opacity: 0.7 })
          .to(glint, { attr: { x: 94 }, duration: 1.8, ease: "power2.inOut" })
          .set(glint, { opacity: 0 });
      }));
      return () => { stopWaiting(); context.revert(); };
    });

    media.add("(prefers-reduced-motion: no-preference) and (hover: hover) and (pointer: fine)", () => {
      const hero = document.querySelector<HTMLElement>("[data-hero]");
      const seal = hero?.querySelector<SVGSVGElement>("[data-cinematic-seal]");
      if (!hero || !seal) return;
      const light = seal.querySelector<SVGLinearGradientElement>("[data-seal-light]");
      const context = gsap.context(() => {
        gsap.set(seal, { transformPerspective: 850, transformOrigin: "50% 50%" });
      });
      // quickTo reuses its tweens; pointer events don't allocate a new timeline.
      const x = gsap.quickTo(seal, "rotationX", { duration: 0.65, ease: "power3.out" });
      const y = gsap.quickTo(seal, "rotationY", { duration: 0.65, ease: "power3.out" });
      let frame = 0;
      let pendingX = 0;
      let pendingY = 0;
      const move = (event: PointerEvent) => {
        const rect = hero.getBoundingClientRect();
        pendingX = (event.clientX - rect.left) / rect.width - 0.5;
        pendingY = (event.clientY - rect.top) / rect.height - 0.5;
        if (frame) return;
        frame = requestAnimationFrame(() => {
          frame = 0;
          x(-pendingY * 12); y(pendingX * 18);
          light?.setAttribute("gradientTransform", `rotate(${pendingX * 32} .5 .5)`);
        });
      };
      const reset = () => {
        cancelAnimationFrame(frame); frame = 0;
        x(0); y(0); light?.removeAttribute("gradientTransform");
      };
      const visibility = () => { if (document.hidden) reset(); };
      hero.addEventListener("pointermove", move, { passive: true });
      hero.addEventListener("pointerleave", reset);
      document.addEventListener("visibilitychange", visibility);
      return () => {
        hero.removeEventListener("pointermove", move);
        hero.removeEventListener("pointerleave", reset);
        document.removeEventListener("visibilitychange", visibility);
        cancelAnimationFrame(frame);
        x.tween.kill(); y.tween.kill();
        light?.removeAttribute("gradientTransform");
        context.revert();
      };
    });
    void document.fonts.ready.then(() => { if (!disposed) ScrollTrigger.refresh(); });
    return () => { disposed = true; media.revert(); };
  }, []);
  return null;
}
