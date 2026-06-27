import { useState } from 'react'
import { X, Trash2, Check } from 'lucide-react'
import Caricature, { Accessory } from '../art/Caricature'
import {
  VARIANT_IDS, ACCESSORY_IDS, THEME_IDS,
  saveCustomPersona, deleteCustomPersona, isCustomId,
} from '../config/avatars'

const BG_SWATCHES = ['#8aa9d6', '#b48ad6', '#9fd1a8', '#d6a98a', '#6a8dac', '#c49a5a', '#7c3f91', '#4a7a6a', '#d67a7a', '#3a3f55']

// Modal to author/edit a custom persona. `persona` = existing persona to edit
// (custom or a built-in used as a starting template), or null for a fresh one.
// onSave(savedPersona) fires after persist; onClose dismisses.
export default function PersonaEditor({ persona, onSave, onClose }) {
  const editingCustom = persona && isCustomId(persona.id)
  const [name, setName] = useState(persona?.name || '')
  const [variant, setVariant] = useState(persona?.variant || 'pubguy')
  const [bg, setBg] = useState(persona?.bg || BG_SWATCHES[0])
  const [theme, setTheme] = useState(persona?.theme || 'fanfare')
  const [accessories, setAccessories] = useState(persona?.accessories?.length ? persona.accessories : ['darts'])
  const [catchphrase, setCatchphrase] = useState(persona?.catchphrase || '')

  const toggleAccessory = (a) => {
    setAccessories((cur) =>
      cur.includes(a) ? cur.filter((x) => x !== a) : cur.length >= 3 ? cur : [...cur, a],
    )
  }

  const save = () => {
    const saved = saveCustomPersona({
      // Editing a custom keeps its id; editing a built-in template forks a new custom.
      id: editingCustom ? persona.id : undefined,
      name, variant, bg, theme, accessories, catchphrase,
    })
    onSave?.(saved)
  }

  const remove = () => {
    if (editingCustom) { deleteCustomPersona(persona.id); onSave?.(null) }
  }

  const field = 'w-full px-3 py-2 rounded-lg bg-black/50 border border-white/10 focus:border-cyan-400/50 outline-none text-sm'

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onClick={onClose}>
      <div className="w-full max-w-2xl rounded-2xl bg-[#15161f] border border-white/10 shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
          <h3 className="text-sm font-bold uppercase tracking-widest text-white/80">
            {editingCustom ? 'Edit persona' : 'Create persona'}
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10 text-white/60">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex flex-col sm:flex-row gap-5 p-5">
          {/* Live preview card */}
          <div className="shrink-0 mx-auto sm:mx-0">
            <div className="w-40 rounded-2xl border border-white/10 overflow-hidden" style={{ background: bg }}>
              <Caricature variant={variant} framing="full" className="w-full" />
            </div>
            <div className="text-center mt-2 text-xs font-bold uppercase tracking-wider text-cyan-300">
              {name || 'Nickname'}
            </div>
            <div className="flex justify-center gap-1.5 mt-2">
              {accessories.map((a) => (
                <span key={a} className="w-7 h-7 rounded-md bg-white/5 border border-white/10 p-0.5">
                  <Accessory type={a} />
                </span>
              ))}
            </div>
          </div>

          {/* Controls */}
          <div className="flex-1 space-y-4">
            <div>
              <label className="text-[10px] uppercase tracking-widest text-white/40">Nickname</label>
              <input value={name} maxLength={24} onChange={(e) => setName(e.target.value)}
                placeholder="e.g. The Hammer" className={field + ' mt-1'} />
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-widest text-white/40">Character</label>
              <div className="flex flex-wrap gap-2 mt-1">
                {VARIANT_IDS.map((v) => (
                  <button key={v} onClick={() => setVariant(v)}
                    className={`w-11 h-11 rounded-lg border overflow-hidden transition-all ${
                      variant === v ? 'border-cyan-400 ring-2 ring-cyan-400/40' : 'border-white/10 hover:border-white/30'}`}
                    style={{ background: bg }} title={v}>
                    <Caricature variant={v} framing="bust" className="w-full h-full" />
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-4">
              <div className="flex-1">
                <label className="text-[10px] uppercase tracking-widest text-white/40">Card colour</label>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {BG_SWATCHES.map((c) => (
                    <button key={c} onClick={() => setBg(c)}
                      className={`w-6 h-6 rounded-md border-2 ${bg === c ? 'border-white' : 'border-transparent'}`}
                      style={{ background: c }} title={c} />
                  ))}
                </div>
              </div>
              <div className="w-32">
                <label className="text-[10px] uppercase tracking-widest text-white/40">Walk-on theme</label>
                <select value={theme} onChange={(e) => setTheme(e.target.value)} className={field + ' mt-1 capitalize'}>
                  {THEME_IDS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-widest text-white/40">Accessories (up to 3)</label>
              <div className="flex flex-wrap gap-2 mt-1">
                {ACCESSORY_IDS.map((a) => {
                  const on = accessories.includes(a)
                  return (
                    <button key={a} onClick={() => toggleAccessory(a)}
                      className={`w-9 h-9 rounded-md border p-0.5 transition-all ${
                        on ? 'border-cyan-400 bg-cyan-400/10' : 'border-white/10 bg-white/5 hover:border-white/30'}`}
                      title={a}>
                      <Accessory type={a} />
                    </button>
                  )
                })}
              </div>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-widest text-white/40">Walk-on catchphrase (MC shouts it)</label>
              <input value={catchphrase} maxLength={60} onChange={(e) => setCatchphrase(e.target.value)}
                placeholder="e.g. Let's have a look at that!" className={field + ' mt-1'} />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between px-5 py-3 border-t border-white/10">
          {editingCustom ? (
            <button onClick={remove}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-red-300 hover:bg-red-500/15 border border-red-400/20">
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button onClick={onClose} className="px-4 py-2 rounded-lg text-xs font-semibold text-white/60 hover:bg-white/10 border border-white/10">
              Cancel
            </button>
            <button onClick={save}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider bg-cyan-500/20 border border-cyan-400/50 text-cyan-200 hover:bg-cyan-500/30">
              <Check className="w-3.5 h-3.5" /> Save persona
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
