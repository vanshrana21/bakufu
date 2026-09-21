import type { MaskMode } from "@/lib/contracts";

/** The active mask in words: "geological mask", "both masks", "no mask". */
export const maskLabel = (mask: MaskMode): string =>
  mask === "none" ? "no mask" : mask === "both" ? "both masks" : `${mask.replaceAll("_", " ")} mask`;
