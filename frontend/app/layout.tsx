import type { Metadata } from "next";
import type { ReactNode } from "react";
import "mapbox-gl/dist/mapbox-gl.css";
import "maplibre-gl/dist/maplibre-gl.css";
import "@fontsource-variable/noto-sans";
import "@fontsource-variable/jetbrains-mono";
import "./globals.css";
// Area stylesheets, in cascade order. Each one is global because its classes are
// shared across routes; keep new rules in the file for their area.
import "./styles/shell.css";
import "./styles/evidence.css";
import "./styles/explorer.css";
import "./styles/layouts.css";
import "./styles/motion.css";
import "./styles/print.css";

export const metadata: Metadata = { title: "Mineral Intelligence | Earth Observatory", description: "SIH26009 · MOIL-oriented prospectivity screening prototype" };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
