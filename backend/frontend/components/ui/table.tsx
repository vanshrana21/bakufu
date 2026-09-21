import * as React from "react";
import { cn } from "@/lib/utils";

export interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {
  containerClassName?: string;
  /** Name the keyboard-scrollable region without replacing the table caption. */
  scrollLabel?: string;
}
export const Table = React.forwardRef<HTMLTableElement, TableProps>(
  ({ className, containerClassName, scrollLabel = "Scrollable data table", ...props }, ref) => (
    <div role="region" aria-label={scrollLabel} tabIndex={0} className={cn("ui-table-scroll relative max-w-full overflow-x-auto rounded-md border bg-card text-card-foreground", containerClassName)}>
      <table ref={ref} className={cn("w-full border-collapse text-left text-sm leading-5 tabular-nums", className)} {...props} />
    </div>
  ),
);
Table.displayName = "Table";
export const TableHeader = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => <thead ref={ref} className={cn("bg-surface-raised [&_tr]:border-b", className)} {...props} />,
);
TableHeader.displayName = "TableHeader";
export const TableBody = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => <tbody ref={ref} className={cn("[&_tr:last-child]:border-0", className)} {...props} />,
);
TableBody.displayName = "TableBody";
export const TableFooter = React.forwardRef<HTMLTableSectionElement, React.HTMLAttributes<HTMLTableSectionElement>>(
  ({ className, ...props }, ref) => <tfoot ref={ref} className={cn("border-t bg-surface-raised font-medium", className)} {...props} />,
);
TableFooter.displayName = "TableFooter";
export const TableRow = React.forwardRef<HTMLTableRowElement, React.HTMLAttributes<HTMLTableRowElement>>(
  ({ className, ...props }, ref) => <tr ref={ref} className={cn("border-b transition-colors hover:bg-row-hover data-[state=selected]:bg-row-selected focus-within:bg-row-hover", className)} {...props} />,
);
TableRow.displayName = "TableRow";
export const TableHead = React.forwardRef<HTMLTableCellElement, React.ThHTMLAttributes<HTMLTableCellElement>>(
  ({ className, scope = "col", ...props }, ref) => <th ref={ref} scope={scope} className={cn("px-4 py-3 align-middle text-xs font-semibold text-muted-foreground", className)} {...props} />,
);
TableHead.displayName = "TableHead";
export const TableCell = React.forwardRef<HTMLTableCellElement, React.TdHTMLAttributes<HTMLTableCellElement>>(
  ({ className, ...props }, ref) => <td ref={ref} className={cn("px-4 py-3 align-middle", className)} {...props} />,
);
TableCell.displayName = "TableCell";
export const TableCaption = React.forwardRef<HTMLTableCaptionElement, React.HTMLAttributes<HTMLTableCaptionElement>>(
  ({ className, ...props }, ref) => <caption ref={ref} className={cn("caption-bottom border-t px-4 py-3 text-left text-xs leading-5 text-muted-foreground", className)} {...props} />,
);
TableCaption.displayName = "TableCaption";
