"use client";
import { useEffect } from "react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/** Progressive enhancement: server-rendered copy and diagrams show final states.
 * Only sufficiently tall desktop viewports pin; touch and reduced motion read normally.
 * ScrollTrigger is shipped with gsap, not a separate @gsap/scrolltrigger package.
 */
export function StoryMotion() {
  useEffect(() => {
    const root = document.getElementById("story");
    if (!root) return;
    gsap.registerPlugin(ScrollTrigger);
    const media = gsap.matchMedia();
    let disposed = false;
    media.add("(prefers-reduced-motion: no-preference)", () => {
      const context = gsap.context(() => {
        root
          .querySelectorAll<HTMLElement>("[data-parallax]")
          .forEach((element) => {
            gsap.fromTo(
              element,
              { y: 18 },
              {
                y: -28,
                ease: "none",
                scrollTrigger: {
                  trigger: element.closest("section"),
                  start: "top bottom",
                  end: "bottom top",
                  scrub: true,
                },
              },
            );
          });
        root
          .querySelectorAll<HTMLElement>("[data-counter]")
          .forEach((element) => {
            const final = element.dataset.counter ?? "0";
            const digits = final.split(".")[1]?.length ?? 0;
            const value = { n: 0 };
            gsap.to(value, {
              n: Number(final),
              duration: 1.3,
              ease: "power2.out",
              scrollTrigger: { trigger: element, start: "top 90%", once: true },
              onUpdate: () => {
                element.textContent = value.n.toFixed(digits);
              },
            });
          });
        root.querySelectorAll<HTMLElement>("[data-card]").forEach((element) => {
          gsap.from(element, {
            rotationX: 10,
            rotationY: -9,
            y: 35,
            transformPerspective: 1000,
            duration: 0.9,
            scrollTrigger: { trigger: element, start: "top 88%", once: true },
          });
        });
        gsap.from(root.querySelector("[data-stamp]"), {
          scale: 1.3,
          rotation: -17,
          duration: 0.35,
          scrollTrigger: {
            trigger: root.querySelector("[data-stamp]"),
            start: "top 85%",
            once: true,
          },
        });
        gsap.from(root.querySelector("[data-hatch]"), {
          scaleX: 0,
          transformOrigin: "left",
          duration: 1,
          scrollTrigger: {
            trigger: root.querySelector("[data-hatch]"),
            start: "top 85%",
            once: true,
          },
        });
        gsap.to(root.querySelector("[data-ring]"), {
          rotation: 180,
          ease: "none",
          scrollTrigger: {
            trigger: root.querySelector("[data-ring]"),
            start: "top bottom",
            end: "bottom top",
            scrub: true,
          },
        });
      }, root);
      return () => {
        context.revert();
        root.querySelectorAll<HTMLElement>("[data-counter]").forEach((el) => {
          el.textContent = el.dataset.counter ?? "";
        });
      };
    });
    media.add(
      "(min-width: 1100px) and (min-height: 820px) and (prefers-reduced-motion: no-preference)",
      () => {
        const context = gsap.context(() => {
          root
            .querySelectorAll<HTMLElement>("[data-pin]")
            .forEach((section) => {
              // Never pin a chapter taller than the viewport: its lower content must stay reachable.
              const pin = section.offsetHeight <= window.innerHeight;
              const timeline = gsap.timeline({
                scrollTrigger: {
                  trigger: section,
                  start: pin ? "top top" : "top 20%",
                  end: pin ? "+=650" : "bottom 75%",
                  pin,
                  scrub: 0.5,
                  invalidateOnRefresh: true,
                },
              });
              if (section.dataset.pin === "engine") {
                const path =
                  section.querySelector<SVGPathElement>("[data-draw]");
                if (path) {
                  const length = path.getTotalLength();
                  timeline.fromTo(
                    path,
                    { strokeDasharray: length, strokeDashoffset: length },
                    { strokeDashoffset: 0, duration: 1 },
                  );
                }
                timeline.from(
                  section.querySelectorAll("[data-node]"),
                  {
                    opacity: 0.4,
                    borderColor: "#D39858",
                    stagger: 0.12,
                    duration: 0.3,
                  },
                  0,
                );
              }
              if (section.dataset.pin === "map") {
                const state = { progress: 0 };
                const canvas = section.querySelector("canvas");
                timeline.to(state, {
                  progress: 1,
                  ease: "none",
                  duration: 1,
                  onUpdate: () =>
                    canvas?.dispatchEvent(
                      new CustomEvent("field-progress", {
                        detail: state.progress,
                      }),
                    ),
                });
              }
              if (section.dataset.pin === "forecast") {
                const path =
                  section.querySelector<SVGPathElement>("[data-history]");
                if (path) {
                  const length = path.getTotalLength();
                  timeline.fromTo(
                    path,
                    { strokeDasharray: length, strokeDashoffset: length },
                    { strokeDashoffset: 0, duration: 0.5 },
                  );
                }
                timeline.from(section.querySelector("[data-future]"), {
                  opacity: 0,
                  duration: 0.2,
                });
                timeline.from(section.querySelector("[data-band]"), {
                  scaleY: 0,
                  transformOrigin: "left center",
                  duration: 0.4,
                });
                timeline.fromTo(
                  section.querySelector("[data-risk]"),
                  { attr: { "stroke-dasharray": "0 100" } },
                  { attr: { "stroke-dasharray": "32 100" }, duration: 0.4 },
                  0.5,
                );
              }
            });
        }, root);
        return () => {
          context.revert();
          root
            .querySelector("[data-cell-field]")
            ?.dispatchEvent(new CustomEvent("field-progress", { detail: 1 }));
        };
      },
    );
    media.add(
      "(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)",
      () => {
        const title = root.querySelector<HTMLElement>("[data-tilt]");
        if (!title) return;
        const context = gsap.context(() => {
          gsap.set(title, { transformPerspective: 1200 });
        }, root);
        const move = (event: PointerEvent) =>
          gsap.to(title, {
            rotationY: (event.clientX / window.innerWidth - 0.5) * 3,
            rotationX: (event.clientY / window.innerHeight - 0.5) * -2,
            duration: 0.5,
            overwrite: true,
          });
        const reset = () =>
          gsap.to(title, {
            rotationY: 0,
            rotationX: 0,
            duration: 0.5,
            overwrite: true,
          });
        const hero = title.closest("section");
        hero?.addEventListener("pointermove", move);
        hero?.addEventListener("pointerleave", reset);
        return () => {
          hero?.removeEventListener("pointermove", move);
          hero?.removeEventListener("pointerleave", reset);
          gsap.killTweensOf(title);
          context.revert();
          title.style.removeProperty("transform");
        };
      },
    );
    void document.fonts.ready.then(() => {
      if (!disposed) ScrollTrigger.refresh();
    });
    return () => {
      disposed = true;
      media.revert();
    };
  }, []);
  return null;
}
