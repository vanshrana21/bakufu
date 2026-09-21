import type { Metadata } from "next";
import { FeedbackHub } from "@/components/feedback/FeedbackHub";

export const metadata: Metadata = { title: "Geologist Feedback Hub | Mineral Intelligence" };

export default function Page() {
  return <FeedbackHub />;
}
