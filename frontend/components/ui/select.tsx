import * as React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

/** Native select retains keyboard navigation and the platform's mobile picker. */
export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => <div className="relative">
    <select ref={ref} className={cn("ui-control h-10 w-full appearance-none rounded-md border border-input bg-surface pl-3 pr-10 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-critical", className)} {...props}>{children}</select>
    <ChevronDown size={16} aria-hidden="true" className="pointer-events-none absolute right-3 top-3 text-muted-foreground" />
  </div>,
);
Select.displayName = "Select";
