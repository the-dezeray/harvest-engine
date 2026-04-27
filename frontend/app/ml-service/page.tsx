"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_ML_BASE ?? "http://localhost:8001";

// ── tiny icon helpers ──────────────────────────────────────────────────────────
const Icon = {
  Activity: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  BarChart: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" /><line x1="2" y1="20" x2="22" y2="20" />
    </svg>
  ),
  Heart: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  ),
  Zap: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-5 h-5">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  RefreshCw: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
      <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  ),
  ChevronRight: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="w-4 h-4">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  ),
};

// ── types ──────────────────────────────────────────────────────────────────────
type HealthData = {
  status: string;
  model_trained: boolean;
  meta: Record<string, unknown>;
};

type ForecastPoint = {
  ds: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
};

type PredictData = {
  meta: Record<string, unknown>;
  periods: number;
  forecast: ForecastPoint[];
};

type EvaluateData = {
  meta: Record<string, unknown>;
  MAE: number;
  RMSE: number;
  MAPE_percent: number;
  accuracy_percent: number;
  accuracy_percent_clipped: number;
};

type Tab = "health" | "predict" | "evaluate";

// ── helpers ────────────────────────────────────────────────────────────────────
function fmt(n: number) {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toFixed(2);
}

function shortDate(ds: string) {
  const d = new Date(ds);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// ── sub-components ─────────────────────────────────────────────────────────────
function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 flex flex-col gap-1 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>
      <p className={`text-2xl font-bold ${accent ?? "text-slate-900"}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function Badge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${
        ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-600"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-emerald-500" : "bg-red-500"}`} />
      {ok ? "Online" : "Offline"}
    </span>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
    </div>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700">
      <strong>Error:</strong> {msg}
    </div>
  );
}

// ── HEALTH TAB ─────────────────────────────────────────────────────────────────
function HealthTab() {
  const [data, setData] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  const meta = data?.meta ?? {};

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Service Health</h2>
          <p className="text-sm text-slate-500">Check if the ML model is trained and ready</p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors"
        >
          <Icon.RefreshCw />
          {loading ? "Checking…" : "Check Health"}
        </button>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBox msg={error} />}

      {data && !loading && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              label="Status"
              value={data.status.toUpperCase()}
              accent={data.status === "ok" ? "text-emerald-600" : "text-red-600"}
            />
            <StatCard
              label="Model"
              value={data.model_trained ? "Trained" : "Not Ready"}
              accent={data.model_trained ? "text-emerald-600" : "text-amber-500"}
            />
            <StatCard label="Frequency" value={String(meta.freq ?? "—")} />
            <StatCard label="Dataset Rows" value={meta.rows ? String(meta.rows) : "—"} />
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-700">Model Metadata</p>
              <Badge ok={data.model_trained} />
            </div>
            <div className="divide-y divide-slate-100">
              {Object.entries(meta).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between px-5 py-3">
                  <span className="text-xs font-mono text-slate-500">{k}</span>
                  <span className="text-xs font-semibold text-slate-800 max-w-xs truncate text-right">
                    {String(v)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <div className="rounded-2xl border-2 border-dashed border-slate-200 p-12 text-center text-slate-400">
          <Icon.Heart />
          <p className="mt-3 text-sm">Click "Check Health" to ping the service</p>
        </div>
      )}
    </div>
  );
}

// ── PREDICT TAB ────────────────────────────────────────────────────────────────
function PredictTab() {
  const [periods, setPeriods] = useState(14);
  const [data, setData] = useState<PredictData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/predict?periods=${periods}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [periods]);

  const chartData = data?.forecast.map((p) => ({
    date: shortDate(p.ds),
    ds: p.ds,
    yhat: p.yhat,
    lower: p.yhat_lower,
    upper: p.yhat_upper,
  })) ?? [];

  const maxVal = chartData.length ? Math.max(...chartData.map((d) => d.upper)) : 0;
  const minVal = chartData.length ? Math.min(...chartData.map((d) => d.lower)) : 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-[200px]">
          <h2 className="text-lg font-bold text-slate-900">Forecast</h2>
          <p className="text-sm text-slate-500">Predict future network load using Prophet</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Periods
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={1}
                max={96}
                value={periods}
                onChange={(e) => setPeriods(Number(e.target.value))}
                className="w-32 accent-indigo-600"
              />
              <span className="w-8 text-sm font-bold text-slate-700 text-center">{periods}</span>
            </div>
          </div>
          <button
            onClick={run}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors self-end"
          >
            <Icon.Zap />
            {loading ? "Running…" : "Run Forecast"}
          </button>
        </div>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBox msg={error} />}

      {data && !loading && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard label="Periods" value={String(data.periods)} sub={String(data.meta.freq ?? "")} />
            <StatCard label="Peak Forecast" value={fmt(maxVal)} accent="text-indigo-600" />
            <StatCard label="Floor Forecast" value={fmt(minVal)} />
            <StatCard
              label="Target"
              value={String(data.meta.target_col ?? "—")}
              sub={`${data.meta.rows} training rows`}
            />
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-5">
            <p className="text-sm font-semibold text-slate-700 mb-4">
              Forecast with 90% Confidence Interval
            </p>
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="ciGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} />
                <YAxis
                  tickFormatter={fmt}
                  tick={{ fontSize: 11, fill: "#94a3b8" }}
                  tickLine={false}
                  axisLine={false}
                  width={60}
                />
                <Tooltip
                  formatter={(v: number, name: string) => [
                    fmt(v),
                    name === "yhat" ? "Forecast" : name === "upper" ? "Upper CI" : "Lower CI",
                  ]}
                  labelFormatter={(l) => `Date: ${l}`}
                  contentStyle={{
                    borderRadius: "12px",
                    border: "1px solid #e2e8f0",
                    fontSize: "12px",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="upper"
                  stroke="none"
                  fill="url(#ciGrad)"
                  name="upper"
                />
                <Area
                  type="monotone"
                  dataKey="lower"
                  stroke="none"
                  fill="white"
                  name="lower"
                />
                <Line
                  type="monotone"
                  dataKey="yhat"
                  stroke="#6366f1"
                  strokeWidth={2.5}
                  dot={false}
                  name="yhat"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
              <p className="text-sm font-semibold text-slate-700">Raw Forecast Data</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left px-5 py-2.5 text-slate-500 font-semibold">Date</th>
                    <th className="text-right px-5 py-2.5 text-slate-500 font-semibold">Forecast</th>
                    <th className="text-right px-5 py-2.5 text-slate-500 font-semibold">Lower CI</th>
                    <th className="text-right px-5 py-2.5 text-slate-500 font-semibold">Upper CI</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {data.forecast.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50 transition-colors">
                      <td className="px-5 py-2.5 font-mono text-slate-600">{row.ds.slice(0, 16)}</td>
                      <td className="px-5 py-2.5 text-right font-semibold text-indigo-600">{fmt(row.yhat)}</td>
                      <td className="px-5 py-2.5 text-right text-slate-500">{fmt(row.yhat_lower)}</td>
                      <td className="px-5 py-2.5 text-right text-slate-500">{fmt(row.yhat_upper)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <div className="rounded-2xl border-2 border-dashed border-slate-200 p-12 text-center text-slate-400">
          <div className="flex justify-center mb-3"><Icon.Activity /></div>
          <p className="text-sm">Set periods and click "Run Forecast" to generate predictions</p>
        </div>
      )}
    </div>
  );
}

// ── EVALUATE TAB ───────────────────────────────────────────────────────────────
function EvaluateTab() {
  const [testRatio, setTestRatio] = useState(0.2);
  const [intervalWidth, setIntervalWidth] = useState(0.9);
  const [data, setData] = useState<EvaluateData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/evaluate?test_ratio=${testRatio}&interval_width=${intervalWidth}`
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [testRatio, intervalWidth]);

  const accuracy = data?.accuracy_percent_clipped ?? 0;
  const arcColor =
    accuracy >= 80 ? "#10b981" : accuracy >= 60 ? "#f59e0b" : "#ef4444";

  // simple gauge bar
  const GaugeBar = ({ value, max, color }: { value: number; max: number; color: string }) => (
    <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${Math.min((value / max) * 100, 100)}%`, backgroundColor: color }}
      />
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex-1 min-w-[200px]">
          <h2 className="text-lg font-bold text-slate-900">Model Evaluation</h2>
          <p className="text-sm text-slate-500">Train/test split evaluation with error metrics</p>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Test Ratio
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0.05}
                max={0.45}
                step={0.05}
                value={testRatio}
                onChange={(e) => setTestRatio(Number(e.target.value))}
                className="w-28 accent-indigo-600"
              />
              <span className="w-10 text-sm font-bold text-slate-700 text-center">
                {Math.round(testRatio * 100)}%
              </span>
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              Interval Width
            </label>
            <div className="flex items-center gap-2">
              <input
                type="range"
                min={0.55}
                max={0.98}
                step={0.05}
                value={intervalWidth}
                onChange={(e) => setIntervalWidth(Number(e.target.value))}
                className="w-28 accent-indigo-600"
              />
              <span className="w-10 text-sm font-bold text-slate-700 text-center">
                {Math.round(intervalWidth * 100)}%
              </span>
            </div>
          </div>
          <button
            onClick={run}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-semibold rounded-xl transition-colors"
          >
            <Icon.BarChart />
            {loading ? "Evaluating…" : "Run Evaluation"}
          </button>
        </div>
      </div>

      {loading && <Spinner />}
      {error && <ErrorBox msg={error} />}

      {data && !loading && (
        <>
          {/* Accuracy hero */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 flex flex-col sm:flex-row items-center gap-6">
            <div className="relative flex items-center justify-center w-32 h-32 shrink-0">
              <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
                <circle cx="60" cy="60" r="50" fill="none" stroke="#f1f5f9" strokeWidth="12" />
                <circle
                  cx="60"
                  cy="60"
                  r="50"
                  fill="none"
                  stroke={arcColor}
                  strokeWidth="12"
                  strokeDasharray={`${(accuracy / 100) * 314} 314`}
                  strokeLinecap="round"
                  style={{ transition: "stroke-dasharray 0.8s ease" }}
                />
              </svg>
              <div className="absolute text-center">
                <p className="text-2xl font-bold" style={{ color: arcColor }}>
                  {accuracy.toFixed(1)}%
                </p>
                <p className="text-[10px] text-slate-400 uppercase font-semibold">Accuracy</p>
              </div>
            </div>
            <div className="flex-1 space-y-3 w-full">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500 font-semibold">MAE</span>
                  <span className="font-bold text-slate-800">{fmt(data.MAE)}</span>
                </div>
                <GaugeBar value={data.MAE} max={data.MAE * 3} color="#6366f1" />
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500 font-semibold">RMSE</span>
                  <span className="font-bold text-slate-800">{fmt(data.RMSE)}</span>
                </div>
                <GaugeBar value={data.RMSE} max={data.RMSE * 3} color="#8b5cf6" />
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-500 font-semibold">sMAPE</span>
                  <span className="font-bold text-slate-800">{data.MAPE_percent.toFixed(2)}%</span>
                </div>
                <GaugeBar value={data.MAPE_percent} max={100} color={arcColor} />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <StatCard
              label="Accuracy"
              value={`${data.accuracy_percent_clipped.toFixed(1)}%`}
              accent={accuracy >= 80 ? "text-emerald-600" : accuracy >= 60 ? "text-amber-500" : "text-red-600"}
            />
            <StatCard label="MAE" value={fmt(data.MAE)} sub="Mean Absolute Error" />
            <StatCard label="RMSE" value={fmt(data.RMSE)} sub="Root Mean Sq. Error" />
            <StatCard label="sMAPE" value={`${data.MAPE_percent.toFixed(2)}%`} sub="Symmetric MAPE" />
          </div>

          {/* Eval meta */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 bg-slate-50">
              <p className="text-sm font-semibold text-slate-700">Evaluation Details</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-slate-100">
              <div className="p-5 space-y-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Training Set</p>
                <Row label="Rows" value={String((data.meta as Record<string, unknown>).train_rows ?? "—")} />
                <Row label="Start" value={String((data.meta as Record<string, unknown>).train_ds_start ?? "—").slice(0, 10)} />
                <Row label="End" value={String((data.meta as Record<string, unknown>).train_ds_end ?? "—").slice(0, 10)} />
              </div>
              <div className="p-5 space-y-2">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Test Set</p>
                <Row label="Rows" value={String((data.meta as Record<string, unknown>).test_rows ?? "—")} />
                <Row label="Start" value={String((data.meta as Record<string, unknown>).test_ds_start ?? "—").slice(0, 10)} />
                <Row label="End" value={String((data.meta as Record<string, unknown>).test_ds_end ?? "—").slice(0, 10)} />
              </div>
            </div>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <div className="rounded-2xl border-2 border-dashed border-slate-200 p-12 text-center text-slate-400">
          <div className="flex justify-center mb-3"><Icon.BarChart /></div>
          <p className="text-sm">Configure parameters and click "Run Evaluation"</p>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-xs font-semibold text-slate-800">{value}</span>
    </div>
  );
}

// ── MAIN PAGE ──────────────────────────────────────────────────────────────────
const TABS: { id: Tab; label: string; icon: keyof typeof Icon }[] = [
  { id: "health", label: "Health", icon: "Heart" },
  { id: "predict", label: "Forecast", icon: "Activity" },
  { id: "evaluate", label: "Evaluate", icon: "BarChart" },
];

export default function MlServicePage() {
  const [tab, setTab] = useState<Tab>("health");

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white">
            <Icon.Zap />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-slate-900">HARVEST ENGINE</h1>
            <p className="text-[10px] text-slate-400 uppercase tracking-widest">ML Service Dashboard</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden sm:block text-xs text-slate-400 font-mono">{API_BASE}</span>
          <Link
            href="/"
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
          >
            Dashboard <Icon.ChevronRight />
          </Link>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Tab bar */}
        <div className="flex gap-1 bg-white border border-slate-200 rounded-xl p-1 shadow-sm w-fit">
          {TABS.map(({ id, label, icon }) => {
            const IconComp = Icon[icon];
            return (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${
                  tab === id
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                }`}
              >
                <IconComp />
                {label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        {tab === "health" && <HealthTab />}
        {tab === "predict" && <PredictTab />}
        {tab === "evaluate" && <EvaluateTab />}
      </div>
    </div>
  );
}
