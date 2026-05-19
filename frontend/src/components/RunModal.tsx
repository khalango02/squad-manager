"use client";
import { useEffect, useRef, useState } from "react";
import { X, Play, CheckCircle, XCircle, Loader, Clock, Bot } from "lucide-react";
import { api, createRunStream, type AgentRun, type RunStep } from "@/lib/api";

interface Props {
  agentId: string;
  agentName: string;
  onClose: () => void;
  onRunStart: (run: AgentRun) => void;
  onRunEnd: (run: AgentRun) => void;
}

type OutputBlock =
  | { type: "text"; content: string }
  | { type: "agent"; name: string; content: string };

function StepIcon({ status, name }: { status: RunStep["status"]; name: string }) {
  const isAgentCall = name.startsWith("Chamando:");
  if (status === "running") return isAgentCall
    ? <Bot size={15} className="text-yellow-400 animate-pulse" />
    : <Loader size={15} className="text-accent animate-spin" />;
  if (status === "done") return isAgentCall
    ? <Bot size={15} className="text-yellow-400" />
    : <CheckCircle size={15} className="text-green-400" />;
  if (status === "failed") return <XCircle size={15} className="text-red-400" />;
  return <Clock size={15} className="text-slate-600" />;
}

export default function RunModal({ agentId, agentName, onClose, onRunStart, onRunEnd }: Props) {
  const [input, setInput] = useState("");
  const [run, setRun] = useState<AgentRun | null>(null);
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [blocks, setBlocks] = useState<OutputBlock[]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "done" | "failed">("idle");
  const [fallbackProvider, setFallbackProvider] = useState<string | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => { return () => esRef.current?.close(); }, []);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [blocks]);

  async function startRun() {
    if (!input.trim() || status === "running") return;
    setStatus("running");
    setSteps([]);
    setBlocks([]);
    setFallbackProvider(null);
    try {
      const newRun = await api.runs.create(agentId, input.trim());
      setRun(newRun);
      onRunStart(newRun);
      connectStream(newRun.id);
    } catch {
      setStatus("failed");
    }
  }

  function connectStream(runId: string) {
    esRef.current?.close();
    const es = createRunStream(runId);
    esRef.current = es;

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);

      if (event.type === "step_update") {
        setSteps((prev) => {
          const next = [...prev];
          next[event.index] = event.step;
          return next;
        });

      } else if (event.type === "fallback") {
        setFallbackProvider(event.provider);

      } else if (event.type === "token") {
        setBlocks((prev) => {
          const last = prev[prev.length - 1];
          if (last?.type === "text") {
            return [...prev.slice(0, -1), { type: "text", content: last.content + event.content }];
          }
          return [...prev, { type: "text", content: event.content }];
        });

      } else if (event.type === "agent_output") {
        setBlocks((prev) => [
          ...prev,
          { type: "agent", name: event.agent_name, content: event.content },
        ]);

      } else if (event.type === "done") {
        setStatus("done");
        setRun((r) => r ? { ...r, status: "done", output: event.output } : r);
        onRunEnd({ ...run!, status: "done", output: event.output });
        es.close();

      } else if (event.type === "error") {
        setStatus("failed");
        onRunEnd({ ...run!, status: "failed" });
        es.close();
      }
    };

    es.onerror = () => { setStatus("failed"); es.close(); };
  }

  const hasOutput = blocks.length > 0;
  const canRun = status === "idle" || status === "done" || status === "failed";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-4xl bg-card border border-border rounded-2xl flex flex-col max-h-[90vh]">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="font-semibold text-white">{agentName}</h2>
            <p className="text-xs text-slate-500 mt-0.5">Agent runner</p>
          </div>
          <button onClick={onClose} className="p-2 text-slate-500 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 min-h-0">

          {/* Left — steps */}
          <div className="w-52 border-r border-border p-4 flex flex-col gap-2 shrink-0">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Steps</p>
            {steps.length === 0 && status === "idle" && (
              <p className="text-xs text-slate-600">Execute um task para ver os steps.</p>
            )}
            {steps.map((step, i) => (
              <div key={i} className="flex items-start gap-2">
                <div className="mt-0.5">
                  <StepIcon status={step.status} name={step.name} />
                </div>
                <div>
                  <p className={`text-xs font-medium ${
                    step.status === "running" ? "text-accent" :
                    step.status === "done"    ? step.name.startsWith("Chamando:") ? "text-yellow-400" : "text-green-400" :
                    step.status === "failed"  ? "text-red-400" : "text-slate-500"
                  }`}>{step.name}</p>
                  {step.started_at && (
                    <p className="text-xs text-slate-600">
                      {step.finished_at
                        ? `${((new Date(step.finished_at).getTime() - new Date(step.started_at).getTime()) / 1000).toFixed(1)}s`
                        : "rodando..."}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Right — output */}
          <div className="flex-1 flex flex-col min-h-0">
            <div ref={outputRef} className="flex-1 overflow-y-auto p-5 flex flex-col gap-3">
              {!hasOutput && (
                <span className="font-mono text-sm text-slate-600">
                  {status === "running" ? "Aguardando resposta..." : "A saída do agent aparecerá aqui."}
                </span>
              )}

              {blocks.map((block, i) =>
                block.type === "text" ? (
                  <span key={i} className="font-mono text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                    {block.content}
                    {status === "running" && i === blocks.length - 1 && (
                      <span className="inline-block w-2 h-4 bg-accent ml-0.5 animate-pulse align-middle" />
                    )}
                  </span>
                ) : (
                  <div key={i} className="border border-yellow-500/25 rounded-xl overflow-hidden bg-yellow-500/5">
                    <div className="flex items-center gap-2 px-4 py-2 border-b border-yellow-500/20 bg-yellow-500/10">
                      <Bot size={13} className="text-yellow-400" />
                      <span className="text-xs font-semibold text-yellow-400">{block.name}</span>
                    </div>
                    <pre className="px-4 py-3 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed font-mono">
                      {block.content}
                    </pre>
                  </div>
                )
              )}
            </div>

            {/* Status bar */}
            {status !== "idle" && (
              <div className={`px-5 py-2 text-xs border-t border-border flex items-center gap-3 ${
                status === "running" ? "text-accent" :
                status === "done"    ? "text-green-400" : "text-red-400"
              }`}>
                <span>
                  {status === "running" ? "Processando..." :
                   status === "done"    ? "Concluído" : "Falhou"}
                </span>
                {fallbackProvider && (
                  <span className="px-2 py-0.5 rounded bg-yellow-500/15 text-yellow-400 border border-yellow-500/30">
                    via OpenAI (fallback)
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-border p-4 flex gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && e.metaKey) startRun(); }}
            placeholder="Descreva o task para o agent... (⌘+Enter para executar)"
            rows={2}
            maxLength={10000}
            disabled={!canRun}
            className="flex-1 resize-none px-4 py-2.5 bg-surface border border-border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-accent text-sm disabled:opacity-50"
          />
          <button
            onClick={startRun}
            disabled={!canRun || !input.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm rounded-lg transition-colors disabled:opacity-40 shrink-0 self-end"
          >
            <Play size={14} />
            Run
          </button>
        </div>
      </div>
    </div>
  );
}
