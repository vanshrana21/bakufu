import * as React from "react";
import { cn } from "@/lib/utils";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => <textarea ref={ref} className={cn("ui-control min-h-28 w-full resize-y rounded-md border border-input bg-surface px-3 py-2 text-sm leading-6 text-foreground placeholder:text-metadata disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-critical", className)} {...props} />,
);
Textarea.displayName = "Textarea";
