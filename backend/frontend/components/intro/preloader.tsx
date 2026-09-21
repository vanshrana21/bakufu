"use client";

import { useEffect, useState } from "react";
import { BakufuMark } from "@/components/brand/logo-b";

/** Fired on window when the loader has gone. The hero picks the seal up from here. */
export const PRELOADER_DONE = "bakufu:preloader-done";

/** True while the loader covers the page. */
export function isPreloaderRunning() {
  return document.documentElement.dataset.preloader === "running";
}

/** Runs `callback` once the loader has gone, or straight away if it never ran. */
export function whenPreloaderDone(callback: () => void): () => void {
  if (!isPreloaderRunning()) {
    callback();
    return () => {};
  }
  window.addEventListener(PRELOADER_DONE, callback, { once: true });
  return () => window.removeEventListener(PRELOADER_DONE, callback);
}

export function Preloader() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem("bakufu-preloader-shown")) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      sessionStorage.setItem("bakufu-preloader-shown", "1");
      return;
    }

    const root = document.documentElement;
    root.dataset.preloader = "running";
    setMounted(true);

    const finish = () => {
      sessionStorage.setItem("bakufu-preloader-shown", "1");
      root.dataset.preloader = "done";
      setMounted(false);
      window.dispatchEvent(new Event(PRELOADER_DONE));
    };
    const timer = window.setTimeout(finish, 2300);
    const skip = () => {
      window.clearTimeout(timer);
      finish();
    };

    window.addEventListener("pointerdown", skip, { once: true });
    window.addEventListener("keydown", skip, { once: true });

    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("pointerdown", skip);
      window.removeEventListener("keydown", skip);
      if (root.dataset.preloader === "running") delete root.dataset.preloader;
    };
  }, []);

  if (!mounted) return null;

  return (
    <div className="bakufu-preloader" aria-hidden="true">
      <div className="bakufu-preloader__scan" />
      <div className="bakufu-preloader__stage">
        <BakufuMark size={140} variant="hero" className="bakufu-preloader__crest" />
        <div className="bakufu-preloader__wordmark">
          <span>BAKUFU</span>
          <span lang="ja">幕府</span>
        </div>
      </div>
      <style>{`
        .bakufu-preloader {
          position: fixed;
          inset: 0;
          z-index: 50;
          display: grid;
          place-items: center;
          overflow: hidden;
          background: var(--ground);
          color: var(--paper);
          --mark-ink: var(--paper);
          --mark-core: var(--glow);
          animation: bakufuOverlayExit 400ms cubic-bezier(.22,.61,.36,1) 1900ms forwards;
          pointer-events: auto;
        }

        .bakufu-preloader::before,
        .bakufu-preloader::after {
          content: "";
          position: absolute;
          inset: 12%;
          border: 1px solid var(--paper);
          opacity: .34;
          transform: scale(.92);
          animation: bakufuSurveyFrame 900ms cubic-bezier(.22,.61,.36,1) forwards;
        }

        .bakufu-preloader::after {
          inset: 22%;
          border-color: var(--paper);
          opacity: .18;
          animation-delay: 240ms;
        }

        /* The crest is the only in-flow child, so it sits at the exact centre of
           the viewport: the hero seal waits at the same point underneath. */
        .bakufu-preloader__stage {
          position: relative;
          display: grid;
          place-items: center;
          animation: bakufuStageExit 400ms cubic-bezier(.22,.61,.36,1) 1900ms forwards;
        }

        .bakufu-preloader__crest {
          overflow: visible;
          filter: drop-shadow(0 0 22px var(--glow));
          opacity: .92;
        }

        .bakufu-preloader__crest [data-logo="body"] {
          opacity: 0;
          animation: bakufuPeakIn 500ms cubic-bezier(.22,.61,.36,1) 600ms forwards;
        }

        .bakufu-preloader__crest [data-logo="frame"],
        .bakufu-preloader__crest [data-logo="strata"] {
          stroke-dasharray: 88;
          stroke-dashoffset: 88;
          animation: bakufuStrataDraw 700ms cubic-bezier(.22,.61,.36,1) forwards;
        }

        .bakufu-preloader__crest [data-logo="reserve-core"] {
          transform-box: fill-box;
          transform-origin: center;
          opacity: 0;
          animation: bakufuCorePulse 600ms cubic-bezier(.22,.61,.36,1) 700ms forwards;
        }

        .bakufu-preloader__scan {
          position: absolute;
          top: 50%;
          left: 50%;
          width: min(46vw, 440px);
          height: 1px;
          background: var(--paper);
          opacity: 0;
          transform: translate(-50%, -50%) rotate(-24deg) translateX(-190px);
          transform-origin: center;
          animation: bakufuScan 400ms cubic-bezier(.22,.61,.36,1) 1300ms forwards;
        }

        .bakufu-preloader__scan::after {
          content: "";
          position: absolute;
          top: -3px;
          right: 0;
          width: 8px;
          height: 8px;
          background: var(--glow);
        }

        .bakufu-preloader__wordmark {
          position: absolute;
          top: calc(100% + 24px);
          left: 50%;
          white-space: nowrap;
          display: flex;
          align-items: baseline;
          gap: 18px;
          color: var(--paper);
          font-family: var(--font-mono);
          font-size: 13px;
          font-weight: 700;
          letter-spacing: .34em;
          opacity: 0;
          transform: translate(-50%, 10px);
          animation: bakufuWordmarkIn 200ms cubic-bezier(.22,.61,.36,1) 1700ms forwards;
        }

        .bakufu-preloader__wordmark span:last-child {
          color: var(--glow);
          letter-spacing: .12em;
        }

        @keyframes bakufuStrataDraw {
          to { stroke-dashoffset: 0; }
        }

        @keyframes bakufuPeakIn {
          to { opacity: 1; }
        }

        @keyframes bakufuCorePulse {
          0% { transform: scale(.72); opacity: .7; filter: drop-shadow(0 0 0 var(--glow)); }
          48% { transform: scale(1.28); opacity: 1; filter: drop-shadow(0 0 20px var(--glow)); }
          100% { transform: scale(1); opacity: 1; filter: drop-shadow(0 0 9px var(--glow)); }
        }

        @keyframes bakufuScan {
          0% { opacity: 0; transform: translate(-50%, -50%) rotate(-24deg) translateX(-190px); }
          22% { opacity: .8; }
          100% { opacity: 0; transform: translate(-50%, -50%) rotate(-24deg) translateX(190px); }
        }

        @keyframes bakufuWordmarkIn {
          to { opacity: 1; transform: translate(-50%, 0); }
        }

        @keyframes bakufuSurveyFrame {
          to { transform: scale(1); opacity: .26; }
        }

        /* Exit is a pure fade, no scale: the identical seal underneath stays put. */
        @keyframes bakufuStageExit {
          to { opacity: 0; }
        }

        @keyframes bakufuOverlayExit {
          to { opacity: 0; pointer-events: none; }
        }

        @media (prefers-reduced-motion: reduce) {
          .bakufu-preloader {
            display: none;
          }
        }
      `}</style>
    </div>
  );
}
