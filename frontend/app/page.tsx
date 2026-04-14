"use client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";

const throughputData = [
  { t: "0s", value: 800 }, { t: "10s", value: 950 }, { t: "20s", value: 870 },
  { t: "30s", value: 1100 }, { t: "40s", value: 1284 }, { t: "50s", value: 1400 },
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
];

const statusColor = {
  active: "bg-green-100 text-green-800",
  "high load": "bg-yellow-100 text-yellow-800",
  idle: "bg-gray-100 text-gray-500",
};

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
        <div className="flex items-center gap-2 font-medium text-gray-800">
          <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
          StreamAnalytics Platform
        </div>
        <span className="text-xs bg-green-50 text-green-700 px-3 py-1 rounded-full">
          ● 3 nodes active
        </span>
      </div>

      <div className="p-6 space-y-6">
        {/* Metric cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Messages/sec", value: "1,284", delta: "↑ 12% from last min", up: true },
            { label: "Active nodes", value: "3", delta: "↑ auto-scaled +1", up: true },
            { label: "Avg sentiment", value: "+0.34", delta: "Positive trend", up: true },
            { label: "CPU (predicted)", value: "67%", delta: "↑ spike in 30s", up: false },
          ].map((m) => (
            <div key={m.label} className="bg-gray-100 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-1">{m.label}</p>
              <p className="text-2xl font-medium text-gray-900">{m.value}</p>
              <p className={`text-xs mt-1 ${m.up ? "text-green-700" : "text-red-600"}`}>{m.delta}</p>
            </div>
          ))}
        </div>

        {/* Throughput chart + Node list */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2 bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-sm font-medium text-gray-800 mb-4">Data throughput — last 60 seconds</p>
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
            <p className="text-sm font-medium text-gray-800 mb-4">Worker nodes</p>
            {nodes.map((n) => (
              <div key={n.name} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
                <span className="text-sm text-gray-700">{n.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor[n.status]}`}>{n.status}</span>
              </div>
            ))}
          </div>
        </div>

        {/* CPU bar chart */}
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-sm font-medium text-gray-800 mb-4">CPU load per node</p>
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

