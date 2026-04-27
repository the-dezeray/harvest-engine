"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type StatusResponse = {
  total_processed?: number;
  by_building?: Record<string, number>;
  scenario?: string;
  source?: string;
  live_to_target_scale?: number;
};

type AlertEvent = {
  id?: string;
  type?: string;
  severity?: string;
  ap_id?: string;
  building?: string;
  timestamp?: number;
  message?: string;
};

type ForecastPoint = {
  ds: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
};

type MessageEvent = {
  id?: string;
  received_at?: string;
  payload?: {
    ap_id?: string;
    building?: string;
  };
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
const RABBITMQ_API_BASE = process.env.NEXT_PUBLIC_RABBITMQ_API_BASE ?? "http://localhost:15672/api";
const RABBITMQ_USER = process.env.NEXT_PUBLIC_RABBITMQ_USER ?? "nexus";
const RABBITMQ_PASS = process.env.NEXT_PUBLIC_RABBITMQ_PASS ?? "nexuspass";
const RABBITMQ_QUEUE = process.env.NEXT_PUBLIC_RABBITMQ_QUEUE ?? "network-data";
const WORKER_MAX_COUNT = Number(process.env.NEXT_PUBLIC_WORKER_MAX_COUNT ?? "10");

type RabbitOverview = {
  object_totals?: {
    consumers?: number;
    channels?: number;
    connections?: number;
  };
};

type RabbitQueue = {
  messages?: number;
  consumers?: number;
  message_stats?: {
    publish_details?: { rate?: number };
    deliver_get_details?: { rate?: number };
    ack_details?: { rate?: number };
  };
};
const FREQ_TO_SECONDS: Record<string, number> = {
  "10_minutes": 10 * 60,
  "1_hour": 60 * 60,
  "1_day": 24 * 60 * 60,
};

const getSecondsPerBucket = (freq?: string) => {
  if (!freq) return FREQ_TO_SECONDS["1_day"];
  return FREQ_TO_SECONDS[freq] ?? FREQ_TO_SECONDS["1_day"];
};

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<"overview" | "events">("overview");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [events, setEvents] = useState<MessageEvent[]>([]);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [forecastFreq, setForecastFreq] = useState<string>("1_day");
  const [mlStats, setMlStats] = useState<any>(null);
  const [history, setHistory] = useState<{t: string, val: number}[]>([]);
  const [scenarioBusy, setScenarioBusy] = useState(false);
  const [rabbitOverview, setRabbitOverview] = useState<RabbitOverview | null>(null);
  const [rabbitQueue, setRabbitQueue] = useState<RabbitQueue | null>(null);
  const [rabbitRates, setRabbitRates] = useState<{ t: string; publish: number; deliver: number; ack: number }[]>([]);
  const [workerCount, setWorkerCount] = useState(1);
  const [workersBusy, setWorkersBusy] = useState(false);
  const [workerError, setWorkerError] = useState("");
  const rabbitAuthHeader = useMemo(
    () => ({ Authorization: `Basic ${btoa(`${RABBITMQ_USER}:${RABBITMQ_PASS}`)}` }),
    []
  );

  const totalProcessed = status?.total_processed ?? 0;
  const hasAnomaly = alerts.some(a => a.type === "PREDICTED_ANOMALY");

  // Fetch status and track history for the chart
  useEffect(() => {
    let lastTotal = 0;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/status`);
        const data = await res.json();
        setStatus(data);
        
        if (lastTotal > 0) {
          const scale = Number(data.live_to_target_scale ?? 100);
          const rate = ((data.total_processed - lastTotal) / 2) * scale; // scaled per second
          setHistory(prev => [...prev.slice(-29), { t: new Date().toLocaleTimeString(), val: rate }]);
        }
        lastTotal = data.total_processed;
      } catch (e) {}
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Fetch Alerts
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/alerts`);
        const data = await res.json();
        setAlerts(data.alerts || []);
      } catch (e) {}
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Fetch all events with source details
  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const res = await fetch(`${API_BASE}/messages`);
        const data = await res.json();
        setEvents(data.messages || []);
      } catch (e) {}
    };

    fetchEvents();
    const interval = setInterval(fetchEvents, 3000);
    return () => clearInterval(interval);
  }, []);

  // Fetch ML Forecast and Stats
  useEffect(() => {
    const fetchML = async () => {
      try {
        const [fRes, sRes] = await Promise.all([
          fetch(`${API_BASE}/forecast?periods=12`),
          fetch(`${API_BASE}/ml-stats`)
        ]);
        const fData = await fRes.json();
        const sData = await sRes.json();
        setForecast(fData.forecast || []);
        setForecastFreq(fData?.meta?.freq || "1_day");
        setMlStats(sData);
      } catch (e) {}
    };
    fetchML();
    const interval = setInterval(fetchML, 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch RabbitMQ Management API metrics
  useEffect(() => {
    const fetchRabbit = async () => {
      try {
        const [overviewRes, queueRes] = await Promise.all([
          fetch(`${RABBITMQ_API_BASE}/overview`, { headers: rabbitAuthHeader }),
          fetch(`${RABBITMQ_API_BASE}/queues/%2F/${encodeURIComponent(RABBITMQ_QUEUE)}`, { headers: rabbitAuthHeader }),
        ]);
        const overviewData = await overviewRes.json();
        const queueData = await queueRes.json();
        setRabbitOverview(overviewData);
        setRabbitQueue(queueData);
        setRabbitRates((prev) => [
          ...prev.slice(-29),
          {
            t: new Date().toLocaleTimeString(),
            publish: queueData?.message_stats?.publish_details?.rate ?? 0,
            deliver: queueData?.message_stats?.deliver_get_details?.rate ?? 0,
            ack: queueData?.message_stats?.ack_details?.rate ?? 0,
          },
        ]);
      } catch {}
    };

    fetchRabbit();
    const interval = setInterval(fetchRabbit, 5000);
    return () => clearInterval(interval);
  }, [rabbitAuthHeader]);

  // Poll worker count for control panel freshness
  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 10000);
    return () => clearInterval(interval);
  }, []);

  const chartData = useMemo(() => {
    const secondsPerBucket = getSecondsPerBucket(forecastFreq);
    const point = forecast[0];
    return history.map((h, i) => ({
      name: h.t,
      live: h.val,
      // Convert forecast bucket totals to per-second to match live throughput.
      predicted: point ? point.yhat / secondsPerBucket : null,
      upper: point ? point.yhat_upper / secondsPerBucket : null,
      lower: point ? point.yhat_lower / secondsPerBucket : null,
    }));
  }, [history, forecast, forecastFreq]);

  const queueDepth = rabbitQueue?.messages ?? 0;
  const queueConsumers = rabbitQueue?.consumers ?? rabbitOverview?.object_totals?.consumers ?? 0;
  const publishRate = rabbitQueue?.message_stats?.publish_details?.rate ?? 0;
  const deliverRate = rabbitQueue?.message_stats?.deliver_get_details?.rate ?? 0;
  const ackRate = rabbitQueue?.message_stats?.ack_details?.rate ?? 0;

  const fetchWorkers = async () => {
    try {
      const res = await fetch(`${API_BASE}/workers`);
      const data = await res.json();
      if (data.count != null) {
        setWorkerCount(Number(data.count) || 1);
      }
      if (data.status === "error") {
        setWorkerError(data.error || "Unable to read worker state");
      } else {
        setWorkerError("");
      }
    } catch {
      setWorkerError("Unable to read worker state");
    }
  };

  const scaleWorkers = async (nextCount: number) => {
    setWorkersBusy(true);
    setWorkerError("");
    try {
      const res = await fetch(`${API_BASE}/workers/scale?count=${nextCount}`, { method: "POST" });
      const data = await res.json();
      if (data.status === "error") {
        setWorkerError(data.error || "Failed to scale workers");
      } else if (data.count != null) {
        setWorkerCount(Number(data.count) || nextCount);
      }
    } catch {
      setWorkerError("Failed to scale workers");
    } finally {
      setWorkersBusy(false);
      fetchWorkers();
    }
  };

  const setScenario = async (mode: string) => {
    setScenarioBusy(true);
    await fetch(`${API_BASE}/scenario?mode=${mode}`, { method: "POST" });
    setScenarioBusy(false);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
      {/* Header */}
      <header className="bg-white border-b px-8 py-4 flex justify-between items-center sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full animate-pulse ${hasAnomaly ? 'bg-red-500' : 'bg-emerald-500'}`}></div>
          <h1 className="text-lg font-bold tracking-tight">HARVEST ENGINE <span className="text-slate-400 font-normal">| Orchestrator</span></h1>
        </div>
        <div className="flex gap-4 items-center">
          <Link
            href="/ml-service"
            className="px-3 py-2 text-xs font-bold uppercase rounded border border-slate-300 bg-white hover:bg-slate-50"
          >
            ML Service
          </Link>
          {hasAnomaly && <span className="bg-red-100 text-red-700 px-3 py-1 rounded text-xs font-bold animate-bounce">ANOMALY DETECTED</span>}
          <div className="text-right">
            <p className="text-[10px] uppercase text-slate-400 font-bold leading-none">Scenario</p>
            <p className="text-sm font-bold text-slate-700">{status?.scenario || '...'}</p>
          </div>
        </div>
      </header>

      <main className="p-8 space-y-8 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-4 py-2 text-xs font-bold uppercase rounded border ${
              activeTab === "overview"
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab("events")}
            className={`px-4 py-2 text-xs font-bold uppercase rounded border ${
              activeTab === "events"
                ? "bg-slate-900 text-white border-slate-900"
                : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            All Events
          </button>
        </div>

        {activeTab === "overview" && (
          <>
        {/* ML Performance & Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white p-6 rounded-2xl border shadow-sm">
            <div className="flex justify-between items-center mb-6">
              <h2 className="font-bold text-slate-700">Predictive Orchestration</h2>
              <div className="flex gap-2">
                {['normal', 'spike', 'cooldown', 'failure'].map(m => (
                  <button 
                    key={m}
                    disabled={scenarioBusy}
                    onClick={() => setScenario(m)}
                    className="px-3 py-1 text-xs font-bold uppercase rounded border hover:bg-slate-50 disabled:opacity-50"
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
            
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorLive" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.1}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" hide />
                  <YAxis fontSize={10} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} />
                  <Area type="monotone" dataKey="upper" stroke="transparent" fill="#f1f5f9" />
                  <Area type="monotone" dataKey="lower" stroke="transparent" fill="#fff" />
                  <Line type="monotone" dataKey="predicted" stroke="#94a3b8" strokeDasharray="5 5" dot={false} strokeWidth={2} />
                  <Area type="monotone" dataKey="live" stroke="#10b981" fillOpacity={1} fill="url(#colorLive)" strokeWidth={3} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <p className="text-[10px] text-slate-400 mt-4 text-center">Live Throughput vs Prophet Prophet Predicted Range (Gray Band)</p>
          </div>

          <div className="space-y-6">
            <div className="bg-slate-900 text-white p-6 rounded-2xl shadow-xl">
              <p className="text-[10px] font-bold text-slate-400 uppercase mb-1">Model Accuracy</p>
              <h3 className="text-4xl font-black mb-4">
                {mlStats?.performance?.accuracy_percent ?? "00.0"}%
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">MAE</span>
                  <span className="font-mono">{mlStats?.performance?.MAE ?? "0.00"}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Target</span>
                  <span className="font-mono">{mlStats?.health?.meta?.target_col || 'n_flows'}</span>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border shadow-sm">
              <h2 className="font-bold text-slate-700 mb-4 text-sm uppercase">Recent Alerts</h2>
              <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                {alerts.map(a => (
                  <div key={a.id} className={`p-3 rounded-lg border-l-4 ${a.type === 'PREDICTED_ANOMALY' ? 'bg-red-50 border-red-500' : 'bg-slate-50 border-slate-300'}`}>
                    <p className="text-[10px] font-bold uppercase opacity-50">{a.type}</p>
                    <p className="text-xs font-medium mt-1 leading-tight">{a.message}</p>
                  </div>
                ))}
                {alerts.length === 0 && <p className="text-xs text-slate-400">System operating within bounds.</p>}
              </div>
            </div>
          </div>
        </div>

        {/* Building Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {Object.entries(status?.by_building || {}).map(([name, count]) => (
            <div key={name} className="bg-white p-4 rounded-xl border shadow-sm">
              <p className="text-[10px] font-bold text-slate-400 uppercase">{name}</p>
              <p className="text-xl font-black text-slate-700">{count.toLocaleString()}</p>
            </div>
          ))}
        </div>

        {/* RabbitMQ and Worker Controls */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-white p-6 rounded-2xl border shadow-sm">
            <h2 className="font-bold text-slate-700 mb-4 text-sm uppercase">Queue Health</h2>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-[10px] text-slate-400 uppercase font-bold">Queue Depth</p>
                <p className="text-2xl font-black text-slate-700">{queueDepth.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-400 uppercase font-bold">Consumers</p>
                <p className="text-2xl font-black text-slate-700">{queueConsumers.toLocaleString()}</p>
              </div>
            </div>
            <div className="h-[140px] mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={rabbitRates}>
                  <XAxis dataKey="t" hide />
                  <YAxis fontSize={10} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="publish" stroke="#2563eb" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="deliver" stroke="#16a34a" dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="ack" stroke="#7c3aed" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl border shadow-sm">
            <h2 className="font-bold text-slate-700 mb-4 text-sm uppercase">Worker Control</h2>
            <p className="text-[10px] text-slate-400 uppercase font-bold">Active Workers</p>
            <p className="text-3xl font-black text-slate-700 mb-4">{workerCount}</p>
            <div className="flex gap-2">
              <button
                disabled={workersBusy || workerCount <= 1}
                onClick={() => scaleWorkers(workerCount - 1)}
                className="px-3 py-2 text-xs font-bold uppercase rounded border hover:bg-slate-50 disabled:opacity-50"
              >
                - Remove Worker
              </button>
              <button
                disabled={workersBusy || workerCount >= WORKER_MAX_COUNT}
                onClick={() => scaleWorkers(workerCount + 1)}
                className="px-3 py-2 text-xs font-bold uppercase rounded border hover:bg-slate-50 disabled:opacity-50"
              >
                + Add Worker
              </button>
            </div>
            {workerError && <p className="mt-3 text-xs text-red-600">{workerError}</p>}
          </div>

          <div className="bg-white p-6 rounded-2xl border shadow-sm">
            <h2 className="font-bold text-slate-700 mb-4 text-sm uppercase">RabbitMQ Rates</h2>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-slate-400">Publish/s</span><span className="font-mono">{publishRate.toFixed(2)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Deliver/s</span><span className="font-mono">{deliverRate.toFixed(2)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Ack/s</span><span className="font-mono">{ackRate.toFixed(2)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Channels</span><span className="font-mono">{rabbitOverview?.object_totals?.channels ?? 0}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Connections</span><span className="font-mono">{rabbitOverview?.object_totals?.connections ?? 0}</span></div>
            </div>
          </div>
        </div>
          </>
        )}

        {activeTab === "events" && (
          <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b flex items-center justify-between">
              <h2 className="font-bold text-slate-700">All Live Events</h2>
              <p className="text-xs text-slate-500">{events.length} events in memory</p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 uppercase text-[11px]">
                  <tr>
                    <th className="text-left px-4 py-3">Time</th>
                    <th className="text-left px-4 py-3">AP ID</th>
                    <th className="text-left px-4 py-3">Building</th>
                    <th className="text-left px-4 py-3">Source</th>
                    <th className="text-left px-4 py-3">Event ID</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev) => (
                    <tr key={ev.id} className="border-t">
                      <td className="px-4 py-2 text-slate-700">
                        {ev.received_at ? new Date(ev.received_at).toLocaleString() : "-"}
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{ev.payload?.ap_id ?? "-"}</td>
                      <td className="px-4 py-2">{ev.payload?.building ?? "-"}</td>
                      <td className="px-4 py-2">ingest-api</td>
                      <td className="px-4 py-2 font-mono text-xs">{ev.id ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {events.length === 0 && (
                <p className="px-4 py-6 text-sm text-slate-400">No events received yet.</p>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
