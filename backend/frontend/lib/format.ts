/** Formatting shared between Server and Client Components.
 *
 * This deliberately does NOT live in production-chart.tsx: that module is
 * "use client", so importing a plain function from it into a Server Component
 * yields a client-reference proxy rather than the function, and the page fails
 * at prerender with "TypeError: i is not a function".
 */

/** Tonnages are reported whole. Live Prophet output carries decimals that the
 * round-numbered fixtures never exposed, and "1,86,907.364 t" reads as false
 * precision on a forecast with a ±15,000 t interval. */
export const tonnes = (value: number) =>
  new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(value);
