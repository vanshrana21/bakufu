"use client";
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PredictionResponse } from "@/lib/contracts";

export function ShapBarChart({ shap }: { shap: NonNullable<PredictionResponse["shap"]> }) {
  return <div>
    <p className="mb-3 text-xs leading-5 text-muted-foreground">Synthetic explanation · {shap.output_scale === "raw_margin" ? "raw model margin" : "classifier probability"}. Before PU adjustment and masks.</p>
    <div className="h-56 min-w-0" role="img" aria-label="Synthetic feature contributions. Numeric values are also listed below.">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={shap.contributions} layout="vertical" margin={{ left: 0, right: 20, top: 5, bottom: 5 }}>
          <XAxis type="number" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={124} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
          <ReferenceLine x={0} stroke="currentColor" strokeOpacity={0.3} />
          <Tooltip formatter={(value) => [typeof value === "number" ? value.toFixed(3) : "Unavailable", "Contribution"]} />
          <Bar dataKey="contribution" barSize={14} isAnimationActive={false}>{shap.contributions.map((c) => <Cell key={c.feature} className={c.contribution >= 0 ? "shap-positive" : "shap-negative"} />)}</Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
    <p className="mt-2 text-xs text-muted-foreground">Right / + increases the classifier output. Left / − decreases it.</p>
    <details className="mt-3 text-xs"><summary className="cursor-pointer py-2">Numeric explanation values</summary><table className="w-full text-left"><caption className="sr-only">SHAP values in {shap.output_scale}</caption><thead><tr><th className="py-2">Feature</th><th>Value</th><th>Contribution</th></tr></thead><tbody>{shap.contributions.map((c) => <tr className="border-t" key={c.feature}><th className="py-2 font-normal">{c.label}</th><td>{c.value === null ? <span className="text-muted-foreground">no value at this point</span> : c.value}</td><td>{c.contribution > 0 ? "+" : ""}{c.contribution.toFixed(3)}</td></tr>)}</tbody></table><p className="pt-2">Base value: {shap.base_value}. These values explain the classifier, not the screened score.</p></details>
  </div>;
}
