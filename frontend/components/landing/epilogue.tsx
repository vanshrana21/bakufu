import { BakufuLockup } from "@/components/brand/logo-b";
import { ChapterLabel, Crest } from "./shared";
import { RollLink } from "./roll-link";
import s from "./story.module.css";
import f from "./finale.module.css";
const ticker =
  "123 MONTHS · PROJECT HISTORY   /   1,024 ILLUSTRATIVE CELLS   /   FOUR MODEL ROLES   /   80% INTERVALS   /   SIH26009   /   ";
export function Epilogue() {
  return (
    <section
      className={s.chapter + " " + s.epilogue}
      aria-labelledby="epilogue-heading"
    >
      <ChapterLabel number="09">EVIDENCE BEFORE ACTION</ChapterLabel>
      <div className={s.marquee} aria-label={ticker}>
        <div aria-hidden="true">
          <span>{ticker}</span>
          <span>{ticker}</span>
        </div>
      </div>
      <div className={f.finale}>
        <div className={f.seal}>
          <Crest />
          <p>Now, go read it.</p>
        </div>
        <div className={f.content}>
          <span className={f.crosses} aria-hidden="true">
            <i /><i /><i /><i /><i />
          </span>
          <h2 id="epilogue-heading" className={f.kicker}>THE GROUND HAS MORE TO SAY.</h2>
          <RollLink href="/operations" lines={["Enter the", "workspace."]} label="Enter the workspace." className={f.title} />
        </div>
      </div>
      <footer className={s.footer}>
        <BakufuLockup size={28} />
        <p>
          Mineral intelligence for MOIL’s challenge.
          <br />
          SIH26009 · Ministry of Steel problem statement.
          <br />
          Independent hackathon prototype. No official endorsement.
        </p>
        <a href="#story">BACK TO THE SURFACE ↑</a>
      </footer>
    </section>
  );
}
