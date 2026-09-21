// UI-only types. These do not define or alter a backend API contract.
export const annotationTypes = ["False Positive", "False Negative", "Data Quality Issue"] as const;
export const severities = ["Low", "Medium", "High"] as const;
export type AnnotationType = typeof annotationTypes[number];
export type Severity = typeof severities[number];
export interface AnnotationDraft {
  siteId: string;
  type: AnnotationType;
  severity: Severity;
  notes: string;
}
export interface Annotation extends AnnotationDraft {
  id: string;
  createdAt: string;
  siteName: string | null;
  status: "Pending" | "Reviewed";
  source: "example" | "session";
}
