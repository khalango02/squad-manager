"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, LogOut, Zap, Bot, X, ChevronRight } from "lucide-react";
import { api, createRunStream, type Agent, type AgentRun, type Connection } from "@/lib/api";
import dynamic from "next/dynamic";
import type { AgentStatus } from "@/components/ConnectionGraph";

const ConnectionGraph = dynamic(() => import("@/components/ConnectionGraph"), { ssr: false });
const RunModal = dynamic(() => import("@/components/RunModal"), { ssr: false });

type ExecBlock =
  | { type: "sub"; agentId: string; agentName: string; content: string }
  | { type: "main"; agentId: string; agentName: string; content: string };

export default function DashboardPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  // Run state
  const [runModalAgentId, setRunModalAgentId] = useState<string | null>(null);
  const [agentStates, setAgentStates] = useState<Record<string, AgentStatus>>({});
  const [execBlocks, setExecBlocks] = useState<ExecBlock[]>([]);
  const [mainTokens, setMainTokens] = useState("");
  const [activeRun, setActiveRun] = useState<{ runId: string; agentId: string } | null>(null);
  const [showResults, setShowResults] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const resultsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.auth.me().catch(() => router.replace("/login"));
    Promise.all([api.agents.list(), api.connections.list()]).then(([a, c]) => {
      setAgents(a);
      setConnections(c);
    });
  }, [router]);

  useEffect(() => {
    resultsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [execBlocks, mainTokens]);

  async function createAgent(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    const agent = await api.agents.create({ name: newName.trim() });
    setAgents((prev) => [agent, ...prev]);
    setNewName("");
    setCreating(false);
  }

  async function deleteAgent(id: string) {
    await api.agents.delete(id);
    setAgents((prev) => prev.filter((a) => a.id !== id));
    setConnections((prev) => prev.filter((c) => c.source_id !== id && c.target_id !== id));
  }

  async function handleConnect(sourceId: string, targetId: string) {
    const conn = await api.connections.create({ source_id: sourceId, target_id: targetId });
    setConnections((prev) => [...prev, conn]);
  }

  async function handleDisconnect(connectionId: string) {
    await api.connections.delete(connectionId);
    setConnections((prev) => prev.filter((c) => c.id !== connectionId));
  }

  async function logout() {
    await api.auth.logout();
    router.push("/login");
  }

  // ── Run lifecycle ─────────────────────────────────────────────────────────

  function handleRunStarted(agentId: string, run: AgentRun) {
    setRunModalAgentId(null);
    esRef.current?.close();

    setActiveRun({ runId: run.id, agentId });
    setAgentStates({ [agentId]: "running" });
    setExecBlocks([]);
    setMainTokens("");
    setShowResults(true);

    const es = createRunStream(run.id);
    esRef.current = es;

    es.onmessage = (e) => {
      const event = JSON.parse(e.data);

      if (event.type === "token") {
        setMainTokens((prev) => prev + event.content);

      } else if (event.type === "agent_output") {
        setAgentStates((prev) => ({ ...prev, [event.agent_id]: "done" }));
        setExecBlocks((prev) => [
          ...prev,
          { type: "sub", agentId: event.agent_id, agentName: event.agent_name, content: event.content },
        ]);

      } else if (event.type === "done") {
        const agentName = agents.find((a) => a.id === agentId)?.name ?? "Agent";
        setAgentStates((prev) => ({ ...prev, [agentId]: "done" }));
        setExecBlocks((prev) => [
          ...prev,
          { type: "main", agentId, agentName, content: event.output },
        ]);
        setMainTokens("");
        es.close();

      } else if (event.type === "error") {
        setAgentStates((prev) => ({ ...prev, [agentId]: "failed" }));
        es.close();
      }
    };

    es.onerror = () => {
      setAgentStates((prev) => ({ ...prev, [agentId]: "failed" }));
      es.close();
    };
  }

  function closeResults() {
    esRef.current?.close();
    setShowResults(false);
    setActiveRun(null);
    setAgentStates({});
    setExecBlocks([]);
    setMainTokens("");
  }

  const runModalAgent = agents.find((a) => a.id === runModalAgentId) ?? null;
  const isRunning = Object.values(agentStates).some((s) => s === "running");

  // Build display blocks for result panel: sub-agents first, then main
  const displayBlocks = execBlocks;
  const mainAgentName = agents.find((a) => a.id === activeRun?.agentId)?.name ?? "Agent";

  return (
    <div className="h-screen bg-surface flex flex-col overflow-hidden">
      {/* Header */}
      <header className="border-b border-border px-8 py-3 flex items-center justify-between shrink-0">
        <h1 className="text-base font-bold text-white">Squad Manager</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/dashboard/skills")}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border text-slate-400 hover:border-slate-500 text-sm transition-colors"
          >
            <Zap size={14} />
            Skills
          </button>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-2 px-3 py-1.5 bg-accent hover:bg-accent-hover text-white text-sm rounded-lg transition-colors"
          >
            <Plus size={14} />
            Novo agent
          </button>
          <button onClick={logout} className="p-2 text-slate-500 hover:text-white transition-colors">
            <LogOut size={16} />
          </button>
        </div>
      </header>

      {/* Create agent form */}
      {creating && (
        <div className="border-b border-border px-8 py-3 flex gap-3 bg-card shrink-0">
          <form onSubmit={createAgent} className="flex gap-3 flex-1">
            <input
              autoFocus
              placeholder="Nome do agent..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              maxLength={100}
              className="flex-1 px-4 py-2 bg-surface border border-accent rounded-lg text-white placeholder-slate-500 focus:outline-none text-sm"
            />
            <button type="submit" className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm">Criar</button>
            <button type="button" onClick={() => setCreating(false)} className="px-4 py-2 border border-border text-slate-400 hover:text-white rounded-lg text-sm">Cancelar</button>
          </form>
        </div>
      )}

      {/* Main: graph + results panel */}
      <div className="flex flex-1 min-h-0">

        {/* Graph */}
        <div className="flex-1 relative">
          {agents.length === 0 ? (
            <div className="h-full flex items-center justify-center text-slate-500">
              <div className="text-center">
                <Bot size={40} className="mx-auto mb-4 opacity-30" />
                <p className="text-lg mb-1">Nenhum agent ainda</p>
                <p className="text-sm">Clique em &quot;Novo agent&quot; para começar</p>
              </div>
            </div>
          ) : (
            <ConnectionGraph
              agents={agents}
              connections={connections}
              agentStates={agentStates}
              onConnect={handleConnect}
              onDisconnect={handleDisconnect}
              onNodeEdit={(id) => router.push(`/dashboard/agent/${id}`)}
              onNodeRun={(id) => setRunModalAgentId(id)}
              onNodeDelete={deleteAgent}
            />
          )}
        </div>

        {/* Results panel */}
        {showResults && (
          <div className="w-[420px] border-l border-border flex flex-col bg-card shrink-0">
            {/* Panel header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-white">Execução</span>
                {isRunning && (
                  <span className="flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-2 w-2 rounded-full bg-accent opacity-75" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
                  </span>
                )}
              </div>
              <button onClick={closeResults} className="p-1.5 text-slate-500 hover:text-white transition-colors">
                <X size={16} />
              </button>
            </div>

            {/* Panel body */}
            <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">

              {/* Streaming tokens (main agent, live) */}
              {mainTokens && (
                <div className="border border-accent/20 rounded-xl overflow-hidden">
                  <div className="flex items-center gap-2 px-4 py-2 bg-accent/10 border-b border-accent/20">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
                    </span>
                    <Bot size={13} className="text-accent" />
                    <span className="text-xs font-semibold text-accent">{mainAgentName}</span>
                  </div>
                  <pre className="px-4 py-3 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed font-mono">
                    {mainTokens}
                    <span className="inline-block w-2 h-4 bg-accent ml-0.5 animate-pulse align-middle" />
                  </pre>
                </div>
              )}

              {/* Completed blocks (in execution order) */}
              {displayBlocks.map((block, i) => (
                <div key={i} className="flex flex-col gap-1">
                  {/* Arrow between blocks */}
                  {i > 0 && (
                    <div className="flex items-center gap-2 px-2 py-1">
                      <ChevronRight size={14} className="text-slate-600" />
                      <span className="text-xs text-slate-600">encaminhou para</span>
                    </div>
                  )}
                  <div className={`border rounded-xl overflow-hidden ${
                    block.type === "sub"
                      ? "border-yellow-500/25 bg-yellow-500/5"
                      : "border-accent/25 bg-accent/5"
                  }`}>
                    <div className={`flex items-center gap-2 px-4 py-2 border-b ${
                      block.type === "sub"
                        ? "border-yellow-500/20 bg-yellow-500/10"
                        : "border-accent/20 bg-accent/10"
                    }`}>
                      <Bot size={13} className={block.type === "sub" ? "text-yellow-400" : "text-accent"} />
                      <span className={`text-xs font-semibold ${block.type === "sub" ? "text-yellow-400" : "text-accent"}`}>
                        {block.agentName}
                      </span>
                    </div>
                    <pre className="px-4 py-3 text-sm text-slate-300 whitespace-pre-wrap leading-relaxed font-mono max-h-[300px] overflow-y-auto">
                      {block.content}
                    </pre>
                  </div>
                </div>
              ))}

              {/* Empty state */}
              {!mainTokens && displayBlocks.length === 0 && (
                <div className="flex items-center justify-center h-full text-slate-600 text-sm">
                  Aguardando resposta...
                </div>
              )}

              <div ref={resultsEndRef} />
            </div>
          </div>
        )}
      </div>

      {/* Run modal (input only) */}
      {runModalAgent && (
        <RunModal
          agentId={runModalAgent.id}
          agentName={runModalAgent.name}
          onClose={() => setRunModalAgentId(null)}
          onRunStarted={(run) => handleRunStarted(runModalAgent.id, run)}
        />
      )}
    </div>
  );
}
