import type { ReactNode } from "react";
import s from "./story.module.css";
export function ChapterLabel({
  number,
  children,
}: {
  number: string;
  children: ReactNode;
}) {
  return (
    <>
      <div className={s.chapterLabel}>
        <span>{number} / FIELD NOTES</span>
        <span>{children}</span>
        <span aria-hidden="true">↗</span>
      </div>
      <span className={s.chapterIndex} aria-hidden="true">
        {number}
      </span>
    </>
  );
}
export function Crest({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 240 240" className={className} aria-hidden="true">
      <circle
        cx="120"
        cy="120"
        r="110"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle
        cx="120"
        cy="120"
        r="97"
        fill="none"
        stroke="currentColor"
        strokeDasharray="1 7"
      />
      <path
        d="M48 170 120 46 192 170H48ZM79 152 120 81 161 152H79Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        d="M120 46v124M48 170l113-18M192 170 79 152"
        stroke="currentColor"
        fill="none"
      />
      <circle cx="120" cy="125" r="17" fill="currentColor" />
      <path d="M104 185h32M113 193h14" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}
/** Original sculptural illustration, never presented as satellite imagery. */
export function ChromeRock({
  id,
  className = "",
}: {
  id: string;
  className?: string;
}) {
  const faces = [
    "70,155 156,48 224,130",
    "156,48 300,30 224,130",
    "300,30 382,104 224,130",
    "382,104 437,235 316,226",
    "224,130 382,104 316,226",
    "70,155 224,130 147,273",
    "224,130 316,226 147,273",
    "70,155 147,273 88,331",
    "147,273 316,226 289,367",
    "316,226 437,235 387,335",
    "316,226 387,335 289,367",
    "88,331 147,273 289,367",
  ];
  return (
    <svg
      className={className}
      viewBox="0 0 500 420"
      role="img"
      aria-label="Sculptural chrome rock, an illustration of manganese-bearing ore"
    >
      <defs>
        <linearGradient id={id + "-metal"} x1="0" y1="0" x2=".9" y2="1">
          <stop stopColor="#EACEAA" />
          <stop offset=".32" stopColor="#362C2A" />
          <stop offset=".49" stopColor="#EACEAA" />
          <stop offset=".53" stopColor="#271F1F" />
          <stop offset=".82" stopColor="#EACEAA" stopOpacity=".75" />
          <stop offset="1" stopColor="#EACEAA" />
        </linearGradient>
        <linearGradient id={id + "-edge"}>
          <stop stopColor="#34150F" />
          <stop offset=".5" stopColor="#EACEAA" />
          <stop offset="1" stopColor="#362C2A" />
        </linearGradient>
      </defs>
      {faces.map((points, i) => (
        <polygon
          key={points}
          points={points}
          fill={"url(#" + id + (i % 3 === 0 ? "-edge)" : "-metal)")}
          stroke="#EACEAA"
          strokeWidth=".6"
          opacity={0.72 + (i % 4) * 0.09}
        />
      ))}
      <path
        d="m70 155 154-25 76-100M224 130l92 96 121 9M147 273l77-143M316 226l-27 141"
        fill="none"
        stroke="#EACEAA"
        strokeWidth="1.5"
      />
    </svg>
  );
}
