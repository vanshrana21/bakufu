import { ActionsWorkbench } from "@/components/operations/actions-workbench";
import { PrintBriefing } from "@/components/operations/print-briefing";
import { loadRegister } from "@/lib/api/load";
export default async function ActionsPage({ searchParams }: { searchParams: { review?: string | string[] } }) {
  const initialId = typeof searchParams.review === "string" ? searchParams.review : undefined;
  const register = await loadRegister();
  return <div className="briefing-page operations-page actions-page">
    <header className="operations-header"><div><p className="app-kicker">04 / ACTIONS</p><h1>Corrective Actions</h1><p>Every proposed action has a rule, a trigger and a review status.</p></div><div className="operations-header-tools"><span className="operations-edition">Demonstration rules · human review</span><PrintBriefing /></div></header>
    {register.data
      ? <ActionsWorkbench rows={register.data.rows} message={register.data.message} initialId={initialId} key={initialId ?? "default"} />
      : <p role="alert" className="note">Corrective actions unavailable — {register.error}</p>}
    <footer className="operations-footer">Demonstration rules only · domain validation pending · no operational changes executed.</footer>
  </div>;
}
