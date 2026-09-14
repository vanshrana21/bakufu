"use client";

import { useRef, useState, type FormEvent } from "react";
import { ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { annotationTypes, severities, type AnnotationDraft } from "./types";

interface AnnotationFormProps {
  initialSiteId?: string;
  onSubmit: (draft: AnnotationDraft) => void;
}

export function AnnotationForm({ initialSiteId = "", onSubmit }: AnnotationFormProps) {
  const form = useRef<HTMLFormElement>(null);
  const [notes, setNotes] = useState("");
  const [errors, setErrors] = useState<{ siteId?: string; notes?: string }>({});

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const siteId = String(data.get("siteId") ?? "").trim();
    const trimmedNotes = notes.trim();
    const nextErrors = {
      siteId: !siteId ? "Enter a site ID. Map selection is not connected yet." : undefined,
      notes: trimmedNotes.length < 10 ? "Add at least 10 characters describing the evidence or concern." : undefined,
    };
    setErrors(nextErrors);
    if (nextErrors.siteId || nextErrors.notes) {
      const field = event.currentTarget.elements.namedItem(nextErrors.siteId ? "siteId" : "notes");
      if (field instanceof HTMLElement) field.focus();
      return;
    }
    const type = annotationTypes.find(value => value === data.get("type"));
    const severity = severities.find(value => value === data.get("severity"));
    if (!type || !severity) return;
    onSubmit({ siteId, notes: trimmedNotes, type, severity });
    setNotes("");
  }

  return <Card>
    <CardHeader>
      <CardTitle>Record an observation</CardTitle>
      <CardDescription>Flag a model concern and describe the evidence for expert review.</CardDescription>
    </CardHeader>
    <CardContent>
      <form ref={form} onSubmit={submit} className="space-y-4">
        <div>
          <label htmlFor="feedback-site" className="mb-1.5 block text-sm font-medium">Site ID <span className="font-normal text-muted-foreground">(required)</span></label>
          <input id="feedback-site" name="siteId" defaultValue={initialSiteId} required maxLength={120} autoComplete="off" spellCheck={false}
            aria-invalid={Boolean(errors.siteId)} aria-describedby={errors.siteId ? "feedback-site-error" : "feedback-site-hint"}
            className="ui-control h-10 w-full rounded-md border border-input bg-surface px-3 font-mono text-sm aria-[invalid=true]:border-critical" placeholder="Enter site identifier" />
          <p id="feedback-site-hint" className="mt-1.5 text-xs leading-5 text-muted-foreground">Manual entry · site identity and geographic scope are not validated here.</p>
          {errors.siteId && <p id="feedback-site-error" className="mt-1 text-xs text-critical">{errors.siteId}</p>}
        </div>
        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_150px]">
          <div>
            <label htmlFor="feedback-type" className="mb-1.5 block text-sm font-medium">Annotation type</label>
            <Select id="feedback-type" name="type" defaultValue="False Positive">{annotationTypes.map(type => <option key={type}>{type}</option>)}</Select>
          </div>
          <div>
            <label htmlFor="feedback-severity" className="mb-1.5 block text-sm font-medium">Severity</label>
            <Select id="feedback-severity" name="severity" defaultValue="Medium">{severities.map(severity => <option key={severity}>{severity}</option>)}</Select>
          </div>
        </div>
        <div>
          <label htmlFor="feedback-notes" className="mb-1.5 block text-sm font-medium">Geologist notes <span className="font-normal text-muted-foreground">(required)</span></label>
          <Textarea id="feedback-notes" name="notes" value={notes} onChange={event => setNotes(event.target.value)} required minLength={10} maxLength={2000}
            aria-invalid={Boolean(errors.notes)} aria-describedby={`feedback-notes-hint${errors.notes ? " feedback-notes-error" : ""}`}
            placeholder="Describe the observation, supporting evidence and what needs to be checked." />
          <div id="feedback-notes-hint" className="mt-1 flex justify-between gap-3 text-xs leading-5 text-muted-foreground"><span>Minimum 10 characters. Include evidence references when available.</span><span className="shrink-0 font-mono">{notes.length}/2000</span></div>
          {errors.notes && <p id="feedback-notes-error" className="mt-1 text-xs text-critical">{errors.notes}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3 border-t pt-4">
          <Button type="submit">Add demo annotation <ArrowUpRight size={15} aria-hidden="true" /></Button>
          <Button type="button" variant="ghost" onClick={() => { form.current?.reset(); setNotes(""); setErrors({}); }}>Clear form</Button>
        </div>
        <p className="text-xs leading-5 text-muted-foreground">Saved only in this page session. Leaving or reloading clears new entries. Nothing is sent to a backend or training pipeline.</p>
      </form>
    </CardContent>
  </Card>;
}
