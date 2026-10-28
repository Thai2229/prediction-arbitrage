"use client";

import { useEffect, useState } from "react";

type Market = {
  ticker: string;
  event: string;
  yes_ask: number;
  status: string;
  source: string;
};

export default function Home() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchMarkets() {
      try {
        setLoading(true);
        setError("");

        const response = await fetch(
          "http://127.0.0.1:8000/api/opportunities"
        );

        if (!response.ok) {
          throw new Error(`Backend returned status ${response.status}`);
        }

        const data = await response.json();

        // The backend currently returns real Kalshi markets in data.markets.
        setMarkets(Array.isArray(data.markets) ? data.markets : []);
      } catch (err) {
        console.error("Error fetching markets:", err);
        setError(
          "Could not load Kalshi markets. Make sure your Python backend is running on port 8000."
        );
      } finally {
        setLoading(false);
      }
    }

    fetchMarkets();
  }, []);

  const filteredMarkets = markets.filter((market) =>
    `${market.event} ${market.ticker}`
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  return (
    <main className="min-h-screen bg-[#0b0f19] text-white">
      <div className="mx-auto max-w-7xl px-6 py-10">
        {/* Header */}
        <header className="mb-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              <span className="text-emerald-400">Arb</span>Finder
            </h1>
            <p className="mt-2 text-sm text-gray-400">
              Prediction market dashboard
            </p>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-gray-700 bg-[#111827] px-4 py-2 text-sm">
            <span
              className={`h-2 w-2 rounded-full ${
                error ? "bg-red-500" : loading ? "bg-yellow-400" : "bg-emerald-400"
              }`}
            />
            {error ? "Connection error" : loading ? "Loading markets..." : "Kalshi connected"}
          </div>
        </header>

        {/* Stats */}
        <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-2xl border border-gray-800 bg-[#111827] p-6">
            <p className="text-sm text-gray-400">Markets loaded</p>
            <p className="mt-3 text-3xl font-semibold">
              {loading ? "—" : markets.length.toLocaleString()}
            </p>
            <p className="mt-2 text-xs text-gray-500">
              Open binary markets with usable YES ask prices
            </p>
          </div>

          <div className="rounded-2xl border border-gray-800 bg-[#111827] p-6">
            <p className="text-sm text-gray-400">Arbitrage opportunities</p>
            <p className="mt-3 text-3xl font-semibold text-emerald-400">
              —
            </p>
            <p className="mt-2 text-xs text-gray-500">
              Not calculated yet — Polymarket matching is next
            </p>
          </div>
        </section>

        {/* Market list */}
        <section className="overflow-hidden rounded-2xl border border-gray-800 bg-[#111827]">
          <div className="flex flex-col gap-4 border-b border-gray-800 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">Kalshi markets</h2>
              <p className="mt-1 text-sm text-gray-400">
                Live data from the Kalshi public API
              </p>
            </div>

            <input
              type="text"
              placeholder="Search markets..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="w-full rounded-xl border border-gray-700 bg-[#0b0f19] px-4 py-2.5 text-sm text-white outline-none placeholder:text-gray-500 focus:border-emerald-400 sm:max-w-xs"
            />
          </div>

          {error ? (
            <div className="p-8 text-center">
              <p className="text-red-400">{error}</p>
              <p className="mt-2 text-sm text-gray-500">
                Check the backend terminal for errors, then refresh this page.
              </p>
            </div>
          ) : loading ? (
            <div className="p-12 text-center text-gray-400">
              Loading Kalshi markets...
            </div>
          ) : filteredMarkets.length === 0 ? (
            <div className="p-12 text-center text-gray-400">
              {markets.length === 0
                ? "No markets were returned by the backend."
                : "No markets match your search."}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#0d1422] text-xs uppercase tracking-wider text-gray-400">
                  <tr>
                    <th className="px-6 py-4 font-medium">Market</th>
                    <th className="px-6 py-4 font-medium">Ticker</th>
                    <th className="px-6 py-4 font-medium">YES ask</th>
                    <th className="px-6 py-4 font-medium">Status</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-gray-800">
                  {filteredMarkets.map((market) => (
                    <tr
                      key={market.ticker}
                      className="transition hover:bg-white/[0.03]"
                    >
                      <td className="max-w-lg px-6 py-4 font-medium text-gray-200">
                        {market.event}
                      </td>

                      <td className="whitespace-nowrap px-6 py-4 font-mono text-xs text-gray-400">
                        {market.ticker}
                      </td>

                      <td className="whitespace-nowrap px-6 py-4 font-semibold text-emerald-400">
                        {(market.yes_ask * 100).toFixed(1)}¢
                      </td>

                      <td className="whitespace-nowrap px-6 py-4">
                        <span className="rounded-full border border-emerald-900 bg-emerald-950 px-2.5 py-1 text-xs text-emerald-400">
                          {market.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="border-t border-gray-800 px-6 py-4 text-xs text-gray-500">
            Showing {filteredMarkets.length} of {markets.length} markets
          </div>
        </section>

        <footer className="mt-8 text-center text-xs text-gray-600">
          ArbFinder · Market prices can change quickly. No trades are executed by this app.
        </footer>
      </div>
    </main>
  );
}
