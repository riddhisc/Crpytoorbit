import { useVirtualizer } from "@tanstack/react-virtual";
import { useRef } from "react";

export type Column<T> = { key: string; header: string; render: (row: T) => React.ReactNode; hideOnMobile?: boolean };

export function DataTable<T extends { id: string }>({
  rows,
  columns,
  onRow,
  density = "comfortable",
  empty,
}: {
  rows: T[];
  columns: Column<T>[];
  onRow?: (row: T) => void;
  density?: "compact" | "comfortable";
  empty?: React.ReactNode;
}) {
  const parent = useRef<HTMLDivElement>(null);
  const virtual = rows.length > 200;
  const virtualizer = useVirtualizer({
    count: virtual ? rows.length : 0,
    getScrollElement: () => parent.current,
    estimateSize: () => (density === "compact" ? 40 : 56),
  });
  if (rows.length === 0) return <>{empty}</>;
  const pad = density === "compact" ? "py-2" : "py-3";
  return (
    <>
      <div className="hidden overflow-auto md:block" ref={parent} style={virtual ? { maxHeight: 560 } : undefined}>
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr>
              {columns.map((column) => (
                <th key={column.key} className="border-b border-line px-3 py-2 text-left font-medium text-muted">
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(virtual ? virtualizer.getVirtualItems().map((item) => rows[item.index]) : rows).map((row) => (
              <tr key={row.id} className="border-b border-line" tabIndex={0} onClick={() => onRow?.(row)} onKeyDown={(event) => event.key === "Enter" && onRow?.(row)}>
                {columns.map((column) => (
                  <td key={column.key} className={`px-3 ${pad}`}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-3 md:hidden">
        {rows.map((row) => (
          <button key={row.id} className="rounded-lg border border-line bg-surface p-3 text-left" onClick={() => onRow?.(row)}>
            {columns.filter((column) => !column.hideOnMobile).map((column) => (
              <div key={column.key} className="mt-1 text-sm">
                <span className="text-muted">{column.header}: </span>
                {column.render(row)}
              </div>
            ))}
          </button>
        ))}
      </div>
    </>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="mt-3 flex items-center gap-2 text-sm">
      <button className="min-h-11 rounded-md border border-line px-3" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} of {pages}
      </span>
      <button className="min-h-11 rounded-md border border-line px-3" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </div>
  );
}
