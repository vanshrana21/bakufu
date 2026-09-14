"use client";

import { useState } from "react";
import { ClipboardPen, MapPinned, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { AnnotationForm } from "./AnnotationForm";
import { PendingAnnotationsTable } from "./PendingAnnotationsTable";
import { demoAnnotations } from "./demo-annotations";
import type { Annotation, AnnotationDraft } from "./types";

export function FeedbackHub() {
  const [annotations, setAnnotations] = useState<readonly Annotation[]>(demoAnnotations);
  const [confirmation, setConfirmation] = useState("");

  function addAnnotation(draft: AnnotationDraft) {
    const id = `LOCAL-${crypto.randomUUID().slice(0, 8).toUpperCase()}`;
    setAnnotations(current => [{ ...draft, id, siteName: null, createdAt: new Date().toISOString(), status: "Pending", source: "session" }, ...current]);
    setConfirmation(`${id} added to the demo register. Local only; not submitted for review or retraining.`);
  }

  return <div className="mx-auto max-w-[1800px] px-4 py-6 sm:px-7 sm:py-8">
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4 border-b pb-6">
      <div><p className="app-kicker">06 / FEEDBACK</p><h1 className="app-title">Geologist Feedback Hub</h1><p className="app-description">Turn field observations into reviewable model feedback. Keep expert judgment, supporting evidence and training decisions separate.</p></div>
      <Badge variant="warning">Demo workspace · no backend submission</Badge>
    </header>
    <div className="grid items-start gap-6 min-[1500px]:grid-cols-[minmax(320px,.75fr)_minmax(0,1.25fr)]">
      <section aria-labelledby="feedback-map-heading" className="min-w-0">
        <div data-theme="dark" className="flex min-h-64 flex-col rounded-lg border border-border p-6 min-[1500px]:min-h-[460px]">
          <div className="flex items-center justify-between gap-3 border-b pb-4"><h2 id="feedback-map-heading" className="text-sm font-semibold">Site context</h2><MapPinned size={18} className="text-muted-foreground" aria-hidden="true" /></div>
          <div className="flex flex-1 flex-col items-start justify-center py-10"><MapPinned size={32} strokeWidth={1.3} className="mb-5 text-primary-ink" aria-hidden="true" /><p className="text-lg font-medium">Map Integration Pending</p><p className="mt-3 max-w-sm text-sm leading-6 text-muted-foreground">Enter the site ID manually in the form. This placeholder does not select a location or validate its model score.</p></div>
          <p className="border-t pt-4 font-mono text-xs leading-5 text-muted-foreground">Sausar Belt · model scope unchanged</p>
        </div>
        <div className="mt-5 space-y-5 px-1">
          <div className="flex items-start gap-3"><ClipboardPen size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-muted-foreground" /><div><h3 className="text-sm font-medium">A report starts a review</h3><p className="mt-1 max-w-prose text-xs leading-5 text-muted-foreground">False-positive and false-negative labels capture a geologist’s concern. They do not automatically establish training ground truth.</p></div></div>
          <div className="flex items-start gap-3"><ShieldCheck size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-muted-foreground" /><div><h3 className="text-sm font-medium">Retraining remains disconnected</h3><p className="mt-1 max-w-prose text-xs leading-5 text-muted-foreground">Evidence validation, expert approval and backend integration are required before annotations can enter a training dataset.</p></div></div>
        </div>
      </section>
      <div className="min-w-0 space-y-6">
        <AnnotationForm onSubmit={addAnnotation} />
        <p role="status" aria-live="polite" aria-atomic="true" className={confirmation ? "rounded-md border bg-success-soft p-3 text-sm leading-6 text-success" : "sr-only"}>{confirmation}</p>
        <PendingAnnotationsTable annotations={annotations} />
      </div>
    </div>
  </div>;
}
