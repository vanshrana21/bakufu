"use client";
import { Droplets, Truck, Cog, Zap } from "lucide-react";

export function KeyConstraints() {
  return <section aria-label="Key constraints" className="mt-5 border-t pt-4">
    <p className="section-label">Key constraints</p>
    <ul className="grid grid-cols-2 gap-x-3 gap-y-3 text-xs">{[
      { label: "Water availability", icon: Droplets }, { label: "Haulage capacity", icon: Truck },
      { label: "Processing uptime", icon: Cog }, { label: "Power reliability", icon: Zap },
    ].map(({ label, icon: Icon }) => <li key={label} className="flex items-center gap-2"><Icon size={17} className="shrink-0 text-primary-ink" />{label}</li>)}</ul>
    <p className="mt-3 text-[11px] leading-4 text-metadata">Review checklist only. Current conditions are not measured.</p>
  </section>;
}
