"use client";
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Save, Plus, X, Zap } from "lucide-react";
import dynamic from "next/dynamic";
import { api, type Agent, type Skill } from "@/lib/api";

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

  const [attachedSkills, setAttachedSkills] = useState<Skill[]>([]);
  const [allSkills, setAllSkills] = useState<Skill[]>([]);
  const [showSkillPicker, setShowSkillPicker] = useState(false);

  useEffect(() => {
    api.agents.get(id).then((a) => {
      setAgent(a);
      setName(a.name);
      setDescription(a.description ?? "");
      setContent(a.md_content);
    });
    api.skills.listForAgent(id).then(setAttachedSkills);
    api.skills.list().then(setAllSkills);
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

  async function attachSkill(skill: Skill) {
    const updated = await api.skills.attach(id, skill.id);
    setAttachedSkills(updated);
    setShowSkillPicker(false);
  }

  async function detachSkill(skillId: string) {
    const updated = await api.skills.detach(id, skillId);
    setAttachedSkills(updated);
  }

  const attachedIds = new Set(attachedSkills.map((s) => s.id));
  const availableToAttach = allSkills.filter((s) => !attachedIds.has(s.id));

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

      {/* Skills bar */}
      <div className="border-b border-border px-8 py-3 flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider shrink-0">
          <Zap size={12} />
          Skills
        </div>

        {attachedSkills.map((skill) => (
          <span
            key={skill.id}
            className="flex items-center gap-1.5 px-3 py-1 bg-accent/10 border border-accent/30 text-accent text-xs rounded-full"
          >
            {skill.name}
            <button
              onClick={() => detachSkill(skill.id)}
              className="hover:text-white transition-colors"
            >
              <X size={11} />
            </button>
          </span>
        ))}

        <div className="relative">
          <button
            onClick={() => setShowSkillPicker((v) => !v)}
            disabled={availableToAttach.length === 0}
            className="flex items-center gap-1 px-2.5 py-1 border border-dashed border-border text-slate-500 hover:border-slate-500 hover:text-slate-300 text-xs rounded-full transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <Plus size={11} />
            Adicionar
          </button>

          {showSkillPicker && availableToAttach.length > 0 && (
            <div className="absolute top-full left-0 mt-2 w-56 bg-card border border-border rounded-xl shadow-xl z-10 overflow-hidden">
              {availableToAttach.map((skill) => (
                <button
                  key={skill.id}
                  onClick={() => attachSkill(skill)}
                  className="w-full text-left px-4 py-2.5 text-sm text-slate-300 hover:bg-surface hover:text-white transition-colors"
                >
                  <p className="font-medium">{skill.name}</p>
                  {skill.description && (
                    <p className="text-xs text-slate-500 truncate">{skill.description}</p>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {allSkills.length === 0 && (
          <button
            onClick={() => router.push("/dashboard/skills")}
            className="text-xs text-slate-600 hover:text-slate-400 transition-colors"
          >
            Criar skills →
          </button>
        )}
      </div>

      <div className="flex-1 p-8" data-color-mode="dark">
        <MDEditor
          value={content}
          onChange={(val) => scheduleSave(val ?? "")}
          height="100%"
          style={{ minHeight: "calc(100vh - 200px)", background: "#1a1d27" }}
        />
      </div>
    </div>
  );
}
