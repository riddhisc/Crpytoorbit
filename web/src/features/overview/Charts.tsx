import { useState } from "react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Summary } from "@/api/client";
import { formatInr } from "@/lib/format";

export default function Charts({ summary }: { summary: Summary }) {
  const [table, setTable] = useState(false);
  const types = Object.entries(summary.by_type).map(([name, value]) => ({ name, value }));
  const holdings = summary.holdings.map((holding) => ({ name: holding.asset, value: Number(holding.value_inr) }));
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="rounded-lg border border-line p-3" aria-label="Exceptions by type">
        <div className="mb-2 flex items-center justify-between">
          <h3>Exceptions by type</h3>
          <button className="min-h-11 text-sm" onClick={() => setTable((value) => !value)}>{table ? "Chart" : "Data table"}</button>
        </div>
        {table ? (
          <table className="w-full text-sm"><tbody>{types.map((row) => <tr key={row.name}><td>{row.name}</td><td>{row.value}</td></tr>)}</tbody></table>
        ) : (
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={types} layout="vertical" margin={{ left: 24 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={140} tick={{ fill: "currentColor", fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="value" fill="var(--accent)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>
      <section className="rounded-lg border border-line p-3" aria-label="Holdings by value">
        <h3>Holdings by value</h3>
        <div className="h-56">
          <ResponsiveContainer>
            <PieChart>
              <Pie data={holdings} dataKey="value" nameKey="name" innerRadius={48} outerRadius={80}>
                {holdings.map((entry) => <Cell key={entry.name} fill="var(--accent)" />)}
              </Pie>
              <Tooltip formatter={(value) => formatInr(Number(value))} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
