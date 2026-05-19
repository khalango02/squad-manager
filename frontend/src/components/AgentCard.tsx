"use client";
import { Bot, Trash2, Play } from "lucide-react";
import type { Agent } from "@/lib/api";

interface Props {
  agent: Agent;
  isRunning?: boolean;
  onClick: () => void;
  onDelete: () => void;
  onRun: () => void;
}

export default function AgentCard({ agent, isRunning, onClick, onDelete, onRun }: Props) {
  return (
    <div
      onClick={onClick}
      className={`group relative bg-card border rounded-xl p-5 cursor-pointer transition-all hover:shadow-lg ${
        isRunning
          ? "border-accent shadow-accent/20 shadow-md"
          : "border-border hover:border-accent hover:shadow-accent/10"
      }`}
    >
      {/* Running pulse indicator */}
      {isRunning && (
        <span className="absolute top-3 right-10 flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-accent" />
        </span>
      )}

      <button
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        className="absolute top-3 right-3 p-1.5 rounded-md text-slate-500 opacity-0 group-hover:opacity-100 hover:text-red-400 hover:bg-red-400/10 transition-all"
      >
        <Trash2 size={14} />
      </button>

      <div className="flex items-center gap-3 mb-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${
          isRunning ? "bg-accent/30" : "bg-accent/15"
        }`}>
          <Bot size={18} className="text-accent" />
        </div>
        <span className="font-semibold text-white truncate pr-4">{agent.name}</span>
      </div>

      {agent.description && (
        <p className="text-slate-400 text-sm line-clamp-2 mb-3">{agent.description}</p>
      )}

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-600">
          {isRunning ? (
            <span className="text-accent">Rodando...</span>
          ) : (
            new Date(agent.updated_at).toLocaleDateString()
          )}
        </p>
        <button
          onClick={(e) => { e.stopPropagation(); onRun(); }}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/10 hover:bg-accent/20 text-accent text-xs rounded-lg transition-colors opacity-0 group-hover:opacity-100"
        >
          <Play size={11} />
          Run
        </button>
      </div>
    </div>
  );
}
