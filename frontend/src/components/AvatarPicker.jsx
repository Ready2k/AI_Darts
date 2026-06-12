import { AVATARS } from '../config/avatars';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import Caricature from '../art/Caricature';

export default function AvatarPicker({ selectedId, onChange }) {
  const currentIndex = AVATARS.findIndex(a => a.id === selectedId);
  const avatar = AVATARS[currentIndex !== -1 ? currentIndex : 0];

  const next = () => {
    onChange(AVATARS[(currentIndex + 1) % AVATARS.length].id);
  };

  const prev = () => {
    onChange(AVATARS[(currentIndex - 1 + AVATARS.length) % AVATARS.length].id);
  };

  return (
    <div className="flex items-center gap-3">
      <button onClick={prev} className="p-1 rounded bg-white/5 hover:bg-white/10 text-white/50 hover:text-white">
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="flex flex-col items-center flex-1">
        <div className="w-16 h-16 rounded-lg border border-white/10 overflow-hidden mb-1" style={{ background: avatar.bg }}>
          <Caricature variant={avatar.variant} framing="bust" className="w-full h-full" />
        </div>
        <span className="text-[10px] uppercase tracking-wider font-bold text-cyan-300">{avatar.name}</span>
      </div>

      <button onClick={next} className="p-1 rounded bg-white/5 hover:bg-white/10 text-white/50 hover:text-white">
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
