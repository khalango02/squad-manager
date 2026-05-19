"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, LogOut, Network } from "lucide-react";
import { api, type Agent, type AgentRun, type Connection } from "@/lib/api";
import AgentCard from "@/components/AgentCard";
import dynamic from "next/dynamic";

const ConnectionGraph = dynamic(() => import("@/components/ConnectionGraph"), { ssr: false });
const RunModal = dynamic(() => import("@/components/RunModal"), { ssr: false });

export default function DashboardPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [showGraph, setShowGraph] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  // Runner state
  const [activeRuns, setActiveRuns] = useState<Record<string, AgentRun>>({});  // agentId -> run
  const [runModalAgent, setRunModalAgent] = useState<Agent | null>(null);

  useEffect(() => {
    api.auth.me().catch(() => router.replace("/login"));
    Promise.all([api.agents.list(), api.connections.list()]).then(([a, c]) => {
      setAgents(a);
      setConnections(c);
    });
  }, [router]);

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
    setActiveRuns((prev) => { const next = { ...prev }; delete next[id]; return next; });
  }

  async function handleConnect(sourceId: string, targetId: string) {
    const conn = await api.connections.create({ source_id: sourceId, target_id: targetId });
    setConnections((prev) => [...prev, conn]);
  }

  async function handleDisconnect(connectionId: string) {
    await api.connections.delete(connectionId);
    setConnections((prev) => prev.filter((c) => c.id !== connectionId));
  }

  function handleRunStart(agentId: string, run: AgentRun) {
    setActiveRuns((prev) => ({ ...prev, [agentId]: run }));
  }

  function handleRunEnd(agentId: string, run: AgentRun) {
    setActiveRuns((prev) => ({ ...prev, [agentId]: run }));
  }

  function openRunModal(agent: Agent) {
    setRunModalAgent(agent);
  }

  async function logout() {
    await api.auth.logout();
    router.push("/login");
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-border px-8 py-4 flex items-center justify-between">
        <h1 className="text-lg font-bold text-white">Squad Manager</h1>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowGraph((v) => !v)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors ${
              showGraph ? "border-accent bg-accent/10 text-accent" : "border-border text-slate-400 hover:border-slate-500"
            }`}
          >
            <Network size={15} />
            Graph
          </button>
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm rounded-lg transition-colors"
          >
            <Plus size={15} />
            New Agent
          </button>
          <button onClick={logout} className="p-2 text-slate-500 hover:text-white transition-colors">
            <LogOut size={18} />
          </button>
        </div>
      </header>

      <main className="px-8 py-8 max-w-7xl mx-auto">
        {creating && (
          <form onSubmit={createAgent} className="mb-8 flex gap-3">
            <input
              autoFocus
              placeholder="Agent name..."
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              maxLength={100}
              className="flex-1 px-4 py-2.5 bg-card border border-accent rounded-lg text-white placeholder-slate-500 focus:outline-none"
            />
            <button type="submit" className="px-4 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm">Create</button>
            <button type="button" onClick={() => setCreating(false)} className="px-4 py-2.5 border border-border text-slate-400 hover:text-white rounded-lg text-sm">Cancel</button>
          </form>
        )}

        {showGraph && agents.length > 0 && (
          <div className="mb-10">
            <h2 className="text-sm font-medium text-slate-400 mb-3">
              Agent connections — drag between agents to connect, click an edge to remove
            </h2>
            <ConnectionGraph
              agents={agents}
              connections={connections}
              onConnect={handleConnect}
              onDisconnect={handleDisconnect}
            />
          </div>
        )}

        {agents.length === 0 ? (
          <div className="text-center py-24 text-slate-500">
            <p className="text-lg mb-2">No agents yet</p>
            <p className="text-sm">Click &quot;New Agent&quot; to get started</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                isRunning={activeRuns[agent.id]?.status === "running"}
                onClick={() => {
                  if (activeRuns[agent.id]) {
                    openRunModal(agent);
                  } else {
                    router.push(`/dashboard/agent/${agent.id}`);
                  }
                }}
                onDelete={() => deleteAgent(agent.id)}
                onRun={() => openRunModal(agent)}
              />
            ))}
          </div>
        )}
      </main>

      {runModalAgent && (
        <RunModal
          agentId={runModalAgent.id}
          agentName={runModalAgent.name}
          onClose={() => setRunModalAgent(null)}
          onRunStart={(run) => handleRunStart(runModalAgent.id, run)}
          onRunEnd={(run) => handleRunEnd(runModalAgent.id, run)}
        />
      )}
    </div>
  );
}
