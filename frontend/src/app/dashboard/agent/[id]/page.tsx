"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save } from "lucide-react";
import dynamic from "next/dynamic";
import { api, type Agent } from "@/lib/api";

const MDEditor = dynamic(() => import("@uiw/react-md-editor"), { ssr: false });

export default function AgentEditorPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const saveTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    api.agents.get(id).then((a) => {
      setAgent(a);
      setName(a.name);
      setDescription(a.description ?? "");
      setContent(a.md_content);
    });
  }, [id]);

  function scheduleSave(nextContent: string) {
    setContent(nextContent);
    setSaved(false);
    clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => save(nextContent), 1500);
  }

  async function save(md?: string) {
    if (!agent) return;
    setSaving(true);
    await api.agents.update(id, {
      name,
      description: description || undefined,
      md_content: md ?? content,
    });
    setSaving(false);
    setSaved(true);
  }

  if (!agent) {
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center text-slate-500">
        Loading...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface flex flex-col">
      <header className="border-b border-border px-8 py-4 flex items-center gap-4">
        <button onClick={() => router.push("/dashboard")} className="p-2 text-slate-400 hover:text-white transition-colors">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 flex items-center gap-4">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="text-lg font-semibold bg-transparent text-white border-b border-transparent hover:border-border focus:border-accent focus:outline-none pb-0.5 transition-colors"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description..."
            className="text-sm bg-transparent text-slate-400 border-b border-transparent hover:border-border focus:border-accent focus:outline-none pb-0.5 transition-colors flex-1"
          />
        </div>
        <div className="flex items-center gap-2">
          {saved && <span className="text-xs text-green-400">Saved</span>}
          {saving && <span className="text-xs text-slate-500">Saving...</span>}
          <button
            onClick={() => save()}
            className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm rounded-lg transition-colors"
          >
            <Save size={14} />
            Save
          </button>
        </div>
      </header>

      <div className="flex-1 p-8" data-color-mode="dark">
        <MDEditor
          value={content}
          onChange={(val) => scheduleSave(val ?? "")}
          height="100%"
          style={{ minHeight: "calc(100vh - 140px)", background: "#1a1d27" }}
        />
      </div>
    </div>
  );
}
