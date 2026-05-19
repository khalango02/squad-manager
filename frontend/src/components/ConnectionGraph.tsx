"use client";
import { useCallback, useEffect } from "react";
import {
  ReactFlow,
  addEdge,
  Background,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  type OnConnect,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Bot, Play } from "lucide-react";
import type { Agent, Connection } from "@/lib/api";

export type AgentStatus = "idle" | "running" | "done" | "failed";

interface Props {
  agents: Agent[];
  connections: Connection[];
  agentStates: Record<string, AgentStatus>;
  onConnect: (sourceId: string, targetId: string) => Promise<void>;
  onDisconnect: (connectionId: string) => Promise<void>;
  onNodeEdit: (agentId: string) => void;
  onNodeRun: (agentId: string) => void;
  onNodeDelete: (agentId: string) => void;
}

function AgentNode({ data }: NodeProps) {
  const { label, description, status, onEdit, onRun, onDelete } = data as {
    label: string;
    description?: string;
    status: AgentStatus;
    onEdit: () => void;
    onRun: () => void;
    onDelete: () => void;
  };

  const borderClass =
    status === "running" ? "border-accent shadow-lg shadow-accent/25" :
    status === "done"    ? "border-green-500/60" :
    status === "failed"  ? "border-red-500/60" :
    "border-border hover:border-slate-500";

  return (
    <div className={`bg-card border-2 ${borderClass} rounded-xl transition-all duration-300 min-w-[160px] group`}>
      <Handle type="target" position={Position.Left} className="!bg-slate-500 !border-none !w-3 !h-3" />

      <div className="px-4 pt-3 pb-2">
        <div className="flex items-center gap-2 mb-1">
          {status === "running" && (
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
          )}
          {status === "done" && <span className="w-2 h-2 rounded-full bg-green-400 shrink-0" />}
          {status === "failed" && <span className="w-2 h-2 rounded-full bg-red-400 shrink-0" />}
          {status === "idle" && <Bot size={13} className="text-accent shrink-0" />}
          <span className="text-sm font-semibold text-white truncate max-w-[130px]">{label}</span>
        </div>
        {description && (
          <p className="text-xs text-slate-500 truncate max-w-[160px]">{description}</p>
        )}
      </div>

      {/* Action buttons (visible on hover) */}
      <div className="flex border-t border-border opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={(e) => { e.stopPropagation(); onEdit(); }}
          className="flex-1 py-1.5 text-xs text-slate-400 hover:text-white hover:bg-surface transition-colors rounded-bl-xl"
        >
          Editar
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onRun(); }}
          className="flex-1 py-1.5 text-xs text-accent hover:bg-accent/10 transition-colors flex items-center justify-center gap-1 border-l border-border"
        >
          <Play size={10} />
          Run
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          className="px-2.5 py-1.5 text-xs text-slate-600 hover:text-red-400 hover:bg-red-400/10 transition-colors rounded-br-xl border-l border-border"
        >
          ✕
        </button>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-slate-500 !border-none !w-3 !h-3" />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };

function buildNodes(
  agents: Agent[],
  agentStates: Record<string, AgentStatus>,
  handlers: { onEdit: (id: string) => void; onRun: (id: string) => void; onDelete: (id: string) => void },
): Node[] {
  return agents.map((a, i) => ({
    id: a.id,
    type: "agentNode",
    data: {
      label: a.name,
      description: a.description ?? "",
      status: agentStates[a.id] ?? "idle",
      onEdit: () => handlers.onEdit(a.id),
      onRun: () => handlers.onRun(a.id),
      onDelete: () => handlers.onDelete(a.id),
    },
    position: { x: (i % 3) * 260, y: Math.floor(i / 3) * 160 },
  }));
}

function buildEdges(connections: Connection[], agentStates: Record<string, AgentStatus>): Edge[] {
  return connections.map((c) => {
    const active =
      agentStates[c.source_id] === "running" || agentStates[c.target_id] === "running";
    return {
      id: c.id,
      source: c.source_id,
      target: c.target_id,
      animated: active,
      style: { stroke: active ? "#f97316" : "#6c63ff", strokeWidth: active ? 2 : 1.5 },
    };
  });
}

export default function ConnectionGraph({
  agents,
  connections,
  agentStates,
  onConnect,
  onDisconnect,
  onNodeEdit,
  onNodeRun,
  onNodeDelete,
}: Props) {
  const handlers = { onEdit: onNodeEdit, onRun: onNodeRun, onDelete: onNodeDelete };

  const [nodes, setNodes, onNodesChange] = useNodesState(
    buildNodes(agents, agentStates, handlers)
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    buildEdges(connections, agentStates)
  );

  // Sync node data (status, handlers) when agents or agentStates change
  useEffect(() => {
    setNodes(buildNodes(agents, agentStates, handlers));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents, agentStates]);

  // Sync edge animation when agentStates changes
  useEffect(() => {
    setEdges(buildEdges(connections, agentStates));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connections, agentStates]);

  const handleConnect: OnConnect = useCallback(
    async (params) => {
      if (!params.source || !params.target) return;
      await onConnect(params.source, params.target);
    },
    [onConnect]
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={handleConnect}
      onEdgeClick={(_, edge) => onDisconnect(edge.id)}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      colorMode="dark"
    >
      <Background color="#2a2d3e" />
      <Controls />
    </ReactFlow>
  );
}
