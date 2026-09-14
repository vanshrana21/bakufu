import type { Metadata } from "next";
import { ReportsCenter } from "@/components/reports/ReportsCenter";

export const metadata: Metadata = { title: "Report Generation & Export Center | Mineral Intelligence" };

export default function Page() {
  return <ReportsCenter />;
}
