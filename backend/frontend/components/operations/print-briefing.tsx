"use client";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
export function PrintBriefing() {
  const print = () => {
    const closed = Array.from(document.querySelectorAll("main details:not([open])"));
    closed.forEach((detail) => detail.setAttribute("open", ""));
    const restore = () => closed.forEach((detail) => detail.removeAttribute("open"));
    window.addEventListener("afterprint", restore, { once: true });
    window.requestAnimationFrame(() => window.print());
  };
  return <Button variant="outline" className="no-print" onClick={print}><Printer size={16} />Print briefing</Button>;
}
