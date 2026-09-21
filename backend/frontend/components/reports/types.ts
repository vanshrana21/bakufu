export const reportTemplates = [
  { id: "production-risk", title: "Monthly Production & Risk Forecast", description: "Forecast, confidence bounds and shortfall risk for the selected operating period.", icon: "chart" },
  { id: "ghost-audit", title: "Ghost Reserve Prospectivity Audit", description: "Screened waste and slag sites with raw scores, masks and evidence caveats.", icon: "map" },
  { id: "compliance", title: "Regulatory Compliance Summary", description: "Permit status, upcoming expiries and recent audit observations.", icon: "shield" },
] as const;
export type ReportTemplateId = typeof reportTemplates[number]["id"];
export type ReportFormat = "PDF" | "Excel" | "CSV";
export type ReportStatus = "Ready" | "Processing" | "Failed";
export interface RecentReport { id: string; template: string; generated: string; requestedBy: string; format: ReportFormat; status: ReportStatus; source: "example" | "session"; }
