"use client";
import { Button } from "@/components/ui/button";
export default function WorkspaceError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div role="alert" className="p-8"><h1 className="text-xl font-semibold">This view could not load</h1><p className="my-4 text-muted-foreground">No values have been substituted for unavailable data.</p><Button onClick={reset}>Try again</Button></div>;
}
