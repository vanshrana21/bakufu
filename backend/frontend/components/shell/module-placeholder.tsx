import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

type ModulePlaceholderProps = {
  title: string;
  description: string;
};

export function ModulePlaceholder({ title, description }: ModulePlaceholderProps) {
  return <section className="mx-auto max-w-6xl px-4 py-8 sm:px-8 sm:py-10" aria-labelledby="module-title">
    <div className="mb-8 border-b pb-7">
      <Badge variant="outline" className="mb-4">Module preview</Badge>
      <h1 id="module-title" className="text-2xl font-semibold leading-tight tracking-tight text-foreground sm:text-3xl">{title}</h1>
      <p className="mt-3 max-w-prose text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
    <Card>
      <CardHeader>
        <CardTitle>Workspace ready for integration</CardTitle>
        <CardDescription>This page currently provides navigation and layout only. Live data and operational controls will be connected in the next implementation phase.</CardDescription>
      </CardHeader>
    </Card>
  </section>;
}
