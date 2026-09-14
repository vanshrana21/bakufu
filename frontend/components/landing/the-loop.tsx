import { ChapterLabel, Crest } from "./shared";
import s from "./story.module.css";
export function TheLoop() {
  return (
    <section
      className={s.chapter + " " + s.loop}
      aria-labelledby="loop-heading"
    >
      <ChapterLabel number="07">STAGE 9 / THE FEEDBACK LOOP / 巡</ChapterLabel>
      <div className={s.twoColumn}>
        <div className={s.loopDiagram}>
          <svg
            viewBox="0 0 500 500"
            className={s.loopOrbit}
            data-ring
            aria-hidden="true"
          >
            <circle
              cx="250"
              cy="250"
              r="195"
              fill="none"
              stroke="var(--shade-3)"
              strokeWidth="2"
              strokeDasharray="4 9"
            />
            <path
              d="M250 55A195 195 0 0 1 445 250"
              fill="none"
              stroke="var(--glow)"
              strokeWidth="3"
            />
            <circle cx="445" cy="250" r="9" fill="var(--glow)" />
          </svg>
          <Crest className={s.loopCrest} />
          <span className={s.loopTop}>01 / GEOLOGIST FLAGS</span>
          <span className={s.loopRight}>02 / ANNOTATE</span>
          <span className={s.loopBottom}>03 / REVIEW + RETRAIN</span>
          <span className={s.loopLeft}>04 / VALIDATE</span>
          <strong className={s.version}>
            v6 → v7<span>CANDIDATE, NOT AUTO-DEPLOYED</span>
          </strong>
        </div>
        <div>
          <h2 id="loop-heading" className={s.display}>
            <span className={s.stepOne}>CORRECT.</span>{" "}
            <span className={`${s.stepTwo} ${s.outline}`}>QUESTION.</span>{" "}
            <span className={s.stepThree}>REPEAT.</span>
          </h2>
          <p className={s.lead}>
            Every correction makes
            <br />
            the house better informed.
          </p>
          <p>
            Geologists flag false positives, missed signals and data issues.
            Reviewed annotations enter the next training cycle. A new version
            earns promotion through evaluation.
          </p>
          <span className={s.sticker + " " + s.limeSticker}>
            HUMAN KNOWLEDGE.
            <br />
            VERSIONED.
          </span>
        </div>
      </div>
      <p className={s.footnote}>
        Workflow illustration. Feedback is not proof of improved accuracy;
        held-out spatial evaluation remains the gate.
      </p>
    </section>
  );
}
