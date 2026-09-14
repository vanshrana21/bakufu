import type { Metadata } from "next";
import "@fontsource/archivo-black/latin-400.css";
// Editorial serif for the ch02, ch06 and ch09 voices; loaded by the landing only.
import "@fontsource-variable/fraunces/opsz.css";
import "@fontsource-variable/fraunces/opsz-italic.css";
import { StoryMotion } from "@/components/landing/story-motion";
import { ColdOpen } from "@/components/landing/cold-open";
import { TheWaste } from "@/components/landing/the-waste";
import { GhostReserves } from "@/components/landing/ghost-reserves";
import { TheEngine } from "@/components/landing/the-engine";
import { TheMap } from "@/components/landing/the-map";
import { TheForecast } from "@/components/landing/the-forecast";
import { TheDecision } from "@/components/landing/the-decision";
import { TheLoop } from "@/components/landing/the-loop";
import { TheHouse } from "@/components/landing/the-house";
import { Epilogue } from "@/components/landing/epilogue";
import s from "@/components/landing/story.module.css";
export const metadata: Metadata = {
  title: "BAKUFU 幕府 — Read the earth. Question the signal.",
  description:
    "Ghost Reserve intelligence: screen historical mine waste, anticipate production shortfalls, and put evidence before action. SIH26009 prototype for MOIL.",
};
export default function LandingPage() {
  return (
    <main className={s.story} id="story">
      <a className={s.skip} href="#house">
        Skip story · open a module
      </a>
      <StoryMotion />
      <ColdOpen />
      <TheWaste />
      <GhostReserves />
      <TheEngine />
      <TheMap />
      <TheForecast />
      <TheDecision />
      <TheLoop />
      <TheHouse />
      <Epilogue />
    </main>
  );
}
