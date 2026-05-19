"use client";
import { useCallback } from "react";
import {
  ReactFlow,
  addEdge,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type OnConnect,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Agent, Connection } from "@/lib/api";

interface Props {
  agents: Agent[];
  connections: Connection[];
  onConnect: (sourceId: string, targetId: string) => Promise<void>;
  onDisconnect: (connectionId: string) => Promise<void>;
}

function agentsToNodes(agents: Agent[]): Node[] {
  return agents.map((a, i) => ({
    id: a.id,
    data: { label: a.name },
    position: { x: (i % 4) * 200, y: Math.floor(i / 4) * 120 },
    style: {
      background: "#1a1d27",
      color: "#e2e8f0",
      border: "1px solid #2a2d3e",
      borderRadius: 10,
      padding: "8px 16px",
      fontSize: 13,
    },
  }));
}

function connectionsToEdges(connections: Connection[]): Edge[] {
  return connections.map((c) => ({
    id: c.id,
    source: c.source_id,
    target: c.target_id,
    label: c.label || undefined,
    style: { stroke: "#6c63ff" },
    labelStyle: { fill: "#94a3b8", fontSize: 11 },
  }));
}

export default function ConnectionGraph({ agents, connections, onConnect, onDisconnect }: Props) {
  const [nodes, , onNodesChange] = useNodesState(agentsToNodes(agents));
  const [edges, setEdges, onEdgesChange] = useEdgesState(connectionsToEdges(connections));

  const handleConnect: OnConnect = useCallback(
    async (params) => {
      if (!params.source || !params.target) return;
      await onConnect(params.source, params.target);
      setEdges((eds) => addEdge({ ...params, style: { stroke: "#6c63ff" } }, eds));
    },
    [onConnect, setEdges]
  );

  return (
    <div className="w-full h-[420px] rounded-xl overflow-hidden border border-border">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={handleConnect}
        onEdgeClick={(_, edge) => onDisconnect(edge.id)}
        fitView
        colorMode="dark"
      >
        <Background color="#2a2d3e" />
        <Controls />
      </ReactFlow>
    </div>
  );
}
