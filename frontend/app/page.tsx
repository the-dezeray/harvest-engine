"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type StatusResponse = {
  total_processed?: number;
  total_messages?: number;
  by_building?: Record<string, number>;
  scenario?: string;
  source?: "redis" | "memory" | string;
};

type AlertEvent = {
  id?: string;
  type?: string;
  severity?: string;
  ap_id?: string;
  building?: string;
  timestamp?: number;
  message?: string;
  value?: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const throughputData = [
  { t: "0s", value: 800 },
  { t: "10s", value: 950 },
  { t: "20s", value: 870 },
  { t: "30s", value: 1100 },
  { t: "40s", value: 1284 },
  { t: "50s", value: 1400 },
  { t: "60s", value: 1350 },
];

const cpuData = [
  { name: "worker-01", cpu: 45 },
  { name: "worker-02", cpu: 58 },
  { name: "worker-03", cpu: 82 },
  { name: "worker-04", cpu: 12 },
];

const nodes = [
  { name: "worker-01", status: "active" },
  { name: "worker-02", status: "active" },
  { name: "worker-03", status: "high load" },
  { name: "worker-04", status: "idle" },
] as const;

const statusColor: Record<(typeof nodes)[number]["status"], string> = {
  active: "bg-green-100 text-green-800",
  "high load": "bg-yellow-100 text-yellow-800",
  idle: "bg-gray-100 text-gray-500",
};

function num(n: unknown): number {
  if (typeof n === "number" && Number.isFinite(n)) return n;
  if (typeof n === "string") {
    const v = Number(n);
    if (Number.isFinite(v)) return v;
  }
  return 0;
}

export default function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [scenarioBusy, setScenarioBusy] = useState(false);

  const byBuildingEntries = useMemo(() => {
    const entries = Object.entries(status?.by_building ?? {});
    entries.sort((a, b) => b[1] - a[1]);
    return entries;
  }, [status?.by_building]);

  const scenario = status?.scenario ?? "unknown";
  const totalProcessed = num(status?.total_processed ?? status?.total_messages);

  useEffect(() => {
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/status`, { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as StatusResponse;
        if (!cancelled) setStatus(data);
      } catch {
        // ignore
      }
    };

    fetchStatus();
    const id = window.setInterval(fetchStatus, 1500);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const fetchAlerts = async () => {
      try {
        const res = await fetch(`${API_BASE}/alerts?limit=50`, { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as { alerts?: AlertEvent[] };
        if (!cancelled) setAlerts(Array.isArray(data.alerts) ? data.alerts : []);
      } catch {
        // ignore
      }
    };

    fetchAlerts();
    const id = window.setInterval(fetchAlerts, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const setScenario = async (mode: "normal" | "spike" | "cooldown" | "failure") => {
    try {
      setScenarioBusy(true);
      await fetch(`${API_BASE}/scenario?mode=${mode}`, { method: "POST" });
    } finally {
      setScenarioBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-2 font-medium text-gray-800">
          <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
          AdNe Dashboard
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs bg-gray-100 text-gray-700 px-3 py-1 rounded-full">
            scenario: {scenario}
          </span>
          <span className="text-xs bg-green-50 text-green-700 px-3 py-1 rounded-full">
            processed: {totalProcessed.toLocaleString()}
          </span>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Scenario controls */}
        <div className="bg-white border border-gray-200 rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-gray-800">Scenario controls</p>
            <p className="text-xs text-gray-500">Switch emitter mode (API: /scenario)</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {([
              { mode: "normal", label: "Normal" },
              { mode: "spike", label: "Spike" },
              { mode: "cooldown", label: "Cooldown" },
              { mode: "failure", label: "Failure" },
            ] as const).map((b) => (
              <button
                key={b.mode}
                className="text-sm px-3 py-1.5 rounded-md border border-gray-200 bg-gray-50 hover:bg-gray-100 disabled:opacity-50"
                onClick={() => setScenario(b.mode)}
                disabled={scenarioBusy}
              >
                {b.label}
              </button>
            ))}
          </div>
        </div>

        {/* Metric cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            {
              label: "Total processed",
              value: totalProcessed.toLocaleString(),
              delta: status?.source ? `source: ${status.source}` : "",
            },
            {
              label: "Buildings seen",
              value: Object.keys(status?.by_building ?? {}).length.toString(),
              delta: "from processed stream",
            },
            {
              label: "Recent alerts",
              value: alerts.length.toString(),
              delta: "last 50 events",
            },
            {
              label: "API base",
              value: API_BASE.replace("http://", "").replace("https://", ""),
              delta: "NEXT_PUBLIC_API_BASE",
            },
          ].map((m) => (
            <div key={m.label} className="bg-gray-100 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">{m.label}</p>
              <p className="text-2xl font-medium text-gray-900 truncate">{m.value}</p>
              <p className="text-xs mt-1 text-gray-600 truncate">{m.delta}</p>
            </div>
          ))}
        </div>

        {/* Throughput chart + Node list */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-800 mb-4">Data throughput — sample chart</p>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={throughputData}>
                <XAxis dataKey="t" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#1D9E75" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-800 mb-4">Worker nodes (demo)</p>
            {nodes.map((n) => (
              <div
                key={n.name}
                className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0"
              >
                <span className="text-sm text-gray-700">{n.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor[n.status]}`}>
                  {n.status}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Building breakdown + Alerts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-800 mb-4">Messages by building</p>
            {byBuildingEntries.length === 0 ? (
              <p className="text-sm text-gray-500">No processed data yet.</p>
            ) : (
              <div className="space-y-2">
                {byBuildingEntries.map(([b, count]) => (
                  <div key={b} className="flex items-center justify-between">
                    <span className="text-sm text-gray-700">{b}</span>
                    <span className="text-sm font-medium text-gray-900">{count.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-800 mb-4">Recent alerts</p>
            {alerts.length === 0 ? (
              <p className="text-sm text-gray-500">No alerts yet.</p>
            ) : (
              <div className="space-y-2">
                {alerts.slice(0, 12).map((a) => (
                  <div key={a.id ?? `${a.type}-${a.timestamp}`} className="border border-gray-100 rounded-lg p-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full">
                        {a.type ?? "event"}
                      </span>
                      <span className="text-xs text-gray-500">{a.severity ?? ""}</span>
                    </div>
                    <p className="text-sm text-gray-800 mt-2">{a.message ?? ""}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {a.ap_id ? `AP: ${a.ap_id}` : ""}
                      {a.building ? ` • Building: ${a.building}` : ""}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* CPU bar chart */}
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-sm font-medium text-gray-800 mb-4">CPU load per node — sample chart</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={cpuData} layout="vertical">
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={70} />
              <Tooltip formatter={(v) => `${v}%`} />
              <Bar dataKey="cpu" fill="#1D9E75" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

