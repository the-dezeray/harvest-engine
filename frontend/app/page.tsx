"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
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
  by_building?: Record<string, number>;
  scenario?: string;
  source?: string;
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export default function Dashboard() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [mlStats, setMlStats] = useState<any>(null);
  const [history, setHistory] = useState<{t: string, val: number}[]>([]);
  const [scenarioBusy, setScenarioBusy] = useState(false);

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
          const rate = (data.total_processed - lastTotal) / 2; // per second
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
        const res = await fetch(`${API_BASE}/alerts?limit=10`);
        const data = await res.json();
        setAlerts(data.alerts || []);
      } catch (e) {}
    }, 3000);
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
        setMlStats(sData);
      } catch (e) {}
    };
    fetchML();
    const interval = setInterval(fetchML, 30000);
    return () => clearInterval(interval);
  }, []);

  const chartData = useMemo(() => {
    return history.map((h, i) => ({
      name: h.t,
      live: h.val,
      // map forecast to same timescale (very rough normalization)
      predicted: forecast[0] ? forecast[0].yhat / 86400 : null,
      upper: forecast[0] ? forecast[0].yhat_upper / 86400 : null,
      lower: forecast[0] ? forecast[0].yhat_lower / 86400 : null,
    }));
  }, [history, forecast]);

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
          {hasAnomaly && <span className="bg-red-100 text-red-700 px-3 py-1 rounded text-xs font-bold animate-bounce">ANOMALY DETECTED</span>}
          <div className="text-right">
            <p className="text-[10px] uppercase text-slate-400 font-bold leading-none">Scenario</p>
            <p className="text-sm font-bold text-slate-700">{status?.scenario || '...'}</p>
          </div>
        </div>
      </header>

      <main className="p-8 space-y-8 max-w-7xl mx-auto">
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
                {mlStats?.performance?.accuracy_percent || '00.0'}%
              </h3>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">MAE</span>
                  <span className="font-mono">{mlStats?.performance?.MAE || '0.00'}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Target</span>
                  <span className="font-mono">{mlStats?.health?.meta?.target_col || 'n_flows'}</span>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-2xl border shadow-sm">
              <h2 className="font-bold text-slate-700 mb-4 text-sm uppercase">Recent Alerts</h2>
              <div className="space-y-3">
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
      </main>
    </div>
  );
}
