"use client";
import { Bot, Trash2 } from "lucide-react";
import type { Agent } from "@/lib/api";

interface Props {
  agent: Agent;
  onClick: () => void;
  onDelete: () => void;
}

export default function AgentCard({ agent, onClick, onDelete }: Props) {
  return (
    <div
      onClick={onClick}
      className="group relative bg-card border border-border rounded-xl p-5 cursor-pointer hover:border-accent transition-all hover:shadow-lg hover:shadow-accent/10"
    >
      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="absolute top-3 right-3 p-1.5 rounded-md text-slate-500 opacity-0 group-hover:opacity-100 hover:text-red-400 hover:bg-red-400/10 transition-all"
      >
        <Trash2 size={14} />
      </button>

      <div className="flex items-center gap-3 mb-3">
        <div className="w-9 h-9 rounded-lg bg-accent/15 flex items-center justify-center">
          <Bot size={18} className="text-accent" />
        </div>
        <span className="font-semibold text-white truncate">{agent.name}</span>
      </div>

      {agent.description && (
        <p className="text-slate-400 text-sm line-clamp-2">{agent.description}</p>
      )}

      <p className="mt-3 text-xs text-slate-600">
        {new Date(agent.updated_at).toLocaleDateString()}
      </p>
    </div>
  );
}
