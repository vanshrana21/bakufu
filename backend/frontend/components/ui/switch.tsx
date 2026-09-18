"use client";
import * as React from "react";
import * as SwitchPrimitive from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

export const Switch = React.forwardRef<React.ElementRef<typeof SwitchPrimitive.Root>, React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>>(({ className, ...props }, ref) => (
  <SwitchPrimitive.Root className={cn("peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-md border-2 border-transparent transition-colors data-[state=checked]:bg-primary data-[state=unchecked]:bg-metadata focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50", className)} {...props} ref={ref}>
    <SwitchPrimitive.Thumb className="pointer-events-none block h-5 w-5 rounded-full bg-[var(--paper)] transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0" />
  </SwitchPrimitive.Root>
));
Switch.displayName = "Switch";
