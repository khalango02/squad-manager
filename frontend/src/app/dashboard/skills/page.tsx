"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Plus, Pencil, Trash2, X, Save } from "lucide-react";
import { api, type Skill } from "@/lib/api";

interface SkillModalProps {
  skill: Skill | null;
  onSave: (data: { name: string; description: string; content: string }) => Promise<void>;
  onClose: () => void;
}

function SkillModal({ skill, onSave, onClose }: SkillModalProps) {
  const [name, setName] = useState(skill?.name ?? "");
  const [description, setDescription] = useState(skill?.description ?? "");
  const [content, setContent] = useState(skill?.content ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!name.trim()) return;
    setSaving(true);
    await onSave({ name: name.trim(), description: description.trim(), content });
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl bg-card border border-border rounded-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-semibold text-white">{skill ? "Editar skill" : "Nova skill"}</h2>
          <button onClick={onClose} className="p-2 text-slate-500 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Nome</label>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              placeholder="Ex: Especialista em Python"
              className="mt-1.5 w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-accent text-sm"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Descrição</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={255}
              placeholder="Breve descrição (opcional)"
              className="mt-1.5 w-full px-4 py-2.5 bg-surface border border-border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-accent text-sm"
            />
          </div>

          <div className="flex-1">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">Contexto</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              maxLength={500_000}
              placeholder="Escreva o contexto fixo que será enviado junto com as mensagens do agent..."
              rows={12}
              className="mt-1.5 w-full resize-none px-4 py-3 bg-surface border border-border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-accent text-sm font-mono leading-relaxed"
            />
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border">
          <button onClick={onClose} className="px-4 py-2 border border-border text-slate-400 hover:text-white rounded-lg text-sm transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={!name.trim() || saving}
            className="flex items-center gap-2 px-5 py-2 bg-accent hover:bg-accent-hover text-white text-sm rounded-lg transition-colors disabled:opacity-40"
          >
            <Save size={14} />
            {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function SkillsPage() {
  const router = useRouter();
  const [skills, setSkills] = useState<Skill[]>([]);
  const [modalSkill, setModalSkill] = useState<Skill | null | "new">(null);

  useEffect(() => {
    api.auth.me().catch(() => router.replace("/login"));
    api.skills.list().then(setSkills);
  }, [router]);

  async function handleSave(data: { name: string; description: string; content: string }) {
    if (modalSkill === "new") {
      const created = await api.skills.create(data);
      setSkills((prev) => [created, ...prev]);
    } else if (modalSkill) {
      const updated = await api.skills.update(modalSkill.id, data);
      setSkills((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    }
    setModalSkill(null);
  }

  async function handleDelete(id: string) {
    await api.skills.delete(id);
    setSkills((prev) => prev.filter((s) => s.id !== id));
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-border px-8 py-4 flex items-center gap-4">
        <button onClick={() => router.push("/dashboard")} className="p-2 text-slate-400 hover:text-white transition-colors">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-lg font-bold text-white flex-1">Skills</h1>
        <button
          onClick={() => setModalSkill("new")}
          className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent-hover text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={15} />
          Nova skill
        </button>
      </header>

      <main className="px-8 py-8 max-w-5xl mx-auto">
        {skills.length === 0 ? (
          <div className="text-center py-24 text-slate-500">
            <p className="text-lg mb-2">Nenhuma skill ainda</p>
            <p className="text-sm">Crie uma skill para reutilizar contexto entre agents</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {skills.map((skill) => (
              <div key={skill.id} className="bg-card border border-border rounded-xl p-5 flex flex-col gap-3 hover:border-slate-600 transition-colors">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-white truncate">{skill.name}</p>
                    {skill.description && (
                      <p className="text-xs text-slate-500 mt-0.5 truncate">{skill.description}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => setModalSkill(skill)}
                      className="p-1.5 text-slate-500 hover:text-white transition-colors rounded"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(skill.id)}
                      className="p-1.5 text-slate-500 hover:text-red-400 transition-colors rounded"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                {skill.content && (
                  <p className="text-xs text-slate-400 font-mono leading-relaxed line-clamp-4 bg-surface rounded-lg p-3">
                    {skill.content}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </main>

      {modalSkill !== null && (
        <SkillModal
          skill={modalSkill === "new" ? null : modalSkill}
          onSave={handleSave}
          onClose={() => setModalSkill(null)}
        />
      )}
    </div>
  );
}
