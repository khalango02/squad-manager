"use client";
import { useState } from "react";
import { X, Play } from "lucide-react";
import { api, type AgentRun } from "@/lib/api";

interface Props {
  agentId: string;
  agentName: string;
  onClose: () => void;
  onRunStarted: (run: AgentRun) => void;
}

export default function RunModal({ agentId, agentName, onClose, onRunStarted }: Props) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleRun() {
    if (!input.trim() || loading) return;
    setLoading(true);
    try {
      const run = await api.runs.create(agentId, input.trim());
      onRunStarted(run);
    } catch {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl bg-card border border-border rounded-2xl shadow-2xl">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider">Executar agent</p>
            <h2 className="font-semibold text-white">{agentName}</h2>
          </div>
          <button onClick={onClose} className="p-2 text-slate-500 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="p-4 flex gap-3">
          <textarea
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && e.metaKey) handleRun(); }}
            placeholder="Descreva o task para o agent... (⌘+Enter para executar)"
            rows={3}
            maxLength={10000}
            className="flex-1 resize-none px-4 py-2.5 bg-surface border border-border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-accent text-sm"
          />
          <button
            onClick={handleRun}
            disabled={!input.trim() || loading}
            className="flex items-center gap-2 px-5 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm rounded-lg transition-colors disabled:opacity-40 shrink-0 self-end"
          >
            <Play size={14} />
            {loading ? "Iniciando..." : "Run"}
          </button>
        </div>
      </div>
    </div>
  );
}
