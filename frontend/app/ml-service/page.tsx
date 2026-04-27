"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

type ChatRole = "user" | "assistant";

type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  raw?: unknown;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const formatJson = (value: unknown) => JSON.stringify(value, null, 2);

const helpText = `Try:
- forecast 12
- stats
- health
- evaluate`;

export default function MlServicePage() {
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "ML service assistant ready. Ask for forecast, stats, health, or evaluate.",
    },
  ]);

  const canSend = useMemo(() => prompt.trim().length > 0 && !busy, [prompt, busy]);

  const runCommand = async (input: string) => {
    const normalized = input.trim().toLowerCase();

    if (normalized.startsWith("forecast")) {
      const match = normalized.match(/forecast\s+(\d+)/);
      const periods = match ? Number(match[1]) : 12;
      const res = await fetch(`${API_BASE}/forecast?periods=${periods}`);
      return {
        label: `Forecast (${periods} periods)`,
        payload: await res.json(),
      };
    }

    if (normalized.includes("stats")) {
      const res = await fetch(`${API_BASE}/ml-stats`);
      return {
        label: "ML Stats",
        payload: await res.json(),
      };
    }

    if (normalized.includes("health")) {
      const res = await fetch(`${API_BASE}/ml-stats`);
      const payload = await res.json();
      return {
        label: "ML Health",
        payload: payload?.health ?? payload,
      };
    }

    if (normalized.includes("evaluate")) {
      const res = await fetch(`${API_BASE}/ml-stats`);
      const payload = await res.json();
      return {
        label: "ML Evaluation",
        payload: payload?.performance ?? payload,
      };
    }

    return {
      label: "Unknown command",
      payload: {
        error: "Unknown command.",
        help: helpText,
      },
    };
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSend) return;

    const userInput = prompt.trim();
    const userMessage: ChatMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      text: userInput,
    };

    setMessages((prev) => [...prev, userMessage]);
    setPrompt("");
    setBusy(true);

    try {
      const result = await runCommand(userInput);
      const assistantMessage: ChatMessage = {
        id: `${Date.now()}-assistant`,
        role: "assistant",
        text: `${result.label}\n${formatJson(result.payload)}`,
        raw: result.payload,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const assistantMessage: ChatMessage = {
        id: `${Date.now()}-assistant-error`,
        role: "assistant",
        text: `Request failed\n${formatJson({
          error: error instanceof Error ? error.message : "Unexpected error",
        })}`,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-white border-b px-8 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold tracking-tight">HARVEST ENGINE</h1>
          <p className="text-xs text-slate-500 uppercase">ML Service Console</p>
        </div>
        <Link
          href="/"
          className="px-3 py-2 text-xs font-bold uppercase rounded border border-slate-300 bg-white hover:bg-slate-50"
        >
          Back to Dashboard
        </Link>
      </header>

      <main className="max-w-5xl mx-auto p-8">
        <div className="bg-white border rounded-2xl shadow-sm overflow-hidden">
          <div className="p-4 border-b bg-slate-50">
            <p className="text-xs text-slate-500 whitespace-pre-line">{helpText}</p>
          </div>

          <div className="h-[60vh] overflow-y-auto p-4 space-y-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`rounded-lg p-3 text-sm ${
                  msg.role === "user"
                    ? "bg-slate-900 text-white ml-10"
                    : "bg-slate-100 text-slate-800 mr-10"
                }`}
              >
                <p className="text-[10px] uppercase opacity-60 mb-1 font-bold">{msg.role}</p>
                <pre className="whitespace-pre-wrap break-words font-mono text-xs">{msg.text}</pre>
              </div>
            ))}
          </div>

          <form onSubmit={onSubmit} className="p-4 border-t flex gap-3">
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Type command (for example: forecast 24)"
              className="flex-1 border rounded-lg px-3 py-2 text-sm"
            />
            <button
              type="submit"
              disabled={!canSend}
              className="px-4 py-2 text-xs font-bold uppercase rounded border border-slate-900 bg-slate-900 text-white disabled:opacity-50"
            >
              {busy ? "Sending..." : "Send"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
