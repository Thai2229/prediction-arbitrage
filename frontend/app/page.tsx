
"use client";

import { useState } from "react";

const opportunities = [
  {
    event: "Candidate A wins election",
    category: "Politics",
    kalshi: 0.42,
    polymarket: 0.53,
  },
  {
    event: "Team A wins championship",
    category: "Sports",
    kalshi: 0.47,
    polymarket: 0.49,
  },
  {
    event: "Interest rate cut this month",
    category: "Economics",
    kalshi: 0.38,
    polymarket: 0.57,
  },
];

export default function Home() {
  const [search, setSearch] = useState("");

  const filtered = opportunities.filter((opportunity) =>
    opportunity.event.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      <header className="border-b border-slate-800 px-8 py-5">
        <div className="mx-auto flex max-w-6xl items-center justify-between">
          <h1 className="text-2xl font-bold">
            <span className="text-blue-400">Arb</span>Finder
          </h1>
          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs text-amber-300">
            DEMO DATA
          </span>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-8 py-10">
        <h2 className="text-3xl font-bold">Arbitrage Dashboard</h2>
        <p className="mt-2 text-slate-400">
          Compare prediction markets across platforms.
        </p>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Markets scanned</p>
            <p className="mt-2 text-3xl font-bold">3</p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <p className="text-sm text-slate-400">Example opportunities</p>
            <p className="mt-2 text-3xl font-bold text-emerald-400">
              {opportunities.filter((o) => o.kalshi + o.polymarket < 1).length}
            </p>
          </div>
        </div>

        <div className="mt-10">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search markets..."
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 outline-none focus:border-blue-500 sm:max-w-md"
          />
        </div>

        <div className="mt-6 overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900 text-slate-400">
              <tr>
                <th className="px-6 py-4">Market</th>
                <th className="px-6 py-4">Kalshi YES</th>
                <th className="px-6 py-4">Polymarket NO</th>
                <th className="px-6 py-4">Gross ROI</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((opportunity) => {
                const cost = opportunity.kalshi + opportunity.polymarket;
                const roi = ((1 - cost) / cost) * 100;
                const isArbitrage = cost < 1;

                return (
                  <tr
                    key={opportunity.event}
                    className="border-t border-slate-800 hover:bg-slate-900"
                  >
                    <td className="px-6 py-5">
                      <p className="font-medium">{opportunity.event}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {opportunity.category}
                      </p>
                    </td>
                    <td className="px-6 py-5">
                      ${opportunity.kalshi.toFixed(2)}
                    </td>
                    <td className="px-6 py-5">
                      ${opportunity.polymarket.toFixed(2)}
                    </td>
                    <td className="px-6 py-5">
                      <span
                        className={
                          isArbitrage
                            ? "font-semibold text-emerald-400"
                            : "text-slate-400"
                        }
                      >
                        {isArbitrage ? `${roi.toFixed(2)}%` : "None"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <p className="p-8 text-center text-slate-400">
              No markets match your search.
            </p>
          )}
        </div>

        <p className="mt-4 text-xs text-slate-500">
          Educational demo only. All prices are fictional, and market
          equivalence, fees, and liquidity have not been verified.
        </p>
      </section>
    </main>
  );
}
