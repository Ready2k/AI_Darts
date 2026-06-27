import { useState } from 'react';
import { ChevronLeft, ChevronRight, Plus, Pencil } from 'lucide-react';
import Caricature from '../art/Caricature';
import { getAllPersonas, isCustomId } from '../config/avatars';
import PersonaEditor from './PersonaEditor';

export default function AvatarPicker({ selectedId, onChange }) {
  const [editing, setEditing] = useState(null);   // { persona } | null
  const [version, setVersion] = useState(0);       // bump to re-read localStorage

  const personas = getAllPersonas();
  const currentIndex = personas.findIndex(a => a.id === selectedId);
  const idx = currentIndex !== -1 ? currentIndex : 0;
  const avatar = personas[idx];

  const next = () => onChange(personas[(idx + 1) % personas.length].id);
  const prev = () => onChange(personas[(idx - 1 + personas.length) % personas.length].id);

  const onSaved = (saved) => {
    setEditing(null);
    setVersion(v => v + 1);
    if (saved) onChange(saved.id);              // select the new/edited persona
    else if (isCustomId(avatar.id)) onChange(personas[0].id); // deleted → fall back
  };

  return (
    <div className="flex items-center gap-2" data-v={version}>
      <button onClick={prev} className="p-1 rounded bg-white/5 hover:bg-white/10 text-white/50 hover:text-white">
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="flex flex-col items-center flex-1">
        <div className="w-16 h-16 rounded-lg border border-white/10 overflow-hidden mb-1" style={{ background: avatar.bg }}>
          <Caricature variant={avatar.variant} framing="bust" className="w-full h-full" />
        </div>
        <span className="text-[10px] uppercase tracking-wider font-bold text-cyan-300">{avatar.name}</span>
        <div className="flex gap-1 mt-1">
          <button onClick={() => setEditing({ persona: null })}
            className="flex items-center gap-0.5 text-[9px] uppercase tracking-wider text-white/40 hover:text-cyan-300">
            <Plus className="w-3 h-3" /> New
          </button>
          <button onClick={() => setEditing({ persona: avatar })}
            className="flex items-center gap-0.5 text-[9px] uppercase tracking-wider text-white/40 hover:text-cyan-300"
            title={isCustomId(avatar.id) ? 'Edit this persona' : 'Customise a copy of this preset'}>
            <Pencil className="w-3 h-3" /> {isCustomId(avatar.id) ? 'Edit' : 'Copy'}
          </button>
        </div>
      </div>

      <button onClick={next} className="p-1 rounded bg-white/5 hover:bg-white/10 text-white/50 hover:text-white">
        <ChevronRight className="w-4 h-4" />
      </button>

      {editing && (
        <PersonaEditor persona={editing.persona} onSave={onSaved} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}
