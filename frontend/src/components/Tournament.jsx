import { useState } from 'react'
import { Trophy, Plus, X, Play, Swords, Flag } from 'lucide-react'

const MODES = ['501', '301', '701', 'Cricket', 'Around the Clock', 'Shanghai', 'Count Up']
const LEVELS = ['Beginner', 'Semi Pro', 'Pro']

function roundLabel(matchCount, idx) {
  if (matchCount === 1) return 'Final'
  if (matchCount === 2) return 'Semi-finals'
  if (matchCount === 4) return 'Quarter-finals'
  return `Round ${idx + 1}`
}

// Build the new-cup payload from the setup form (mirrors GameSetup).
function buildPayload(players, mode) {
  const isX01 = ['501', '301', '701'].includes(mode)
  return {
    players: players.filter(p => p.name.trim()),
    mode: isX01 ? 'X01' : mode,
    start_score: isX01 ? parseInt(mode, 10) : undefined,
    double_out: isX01,
    legs_to_win: 1, sets_to_win: 1,
  }
}

export default function Tournament({ tournament, onStart, onNext, onEnd, onGoLive }) {
  const [players, setPlayers] = useState([
    { name: 'Player 1', is_ai: false, ai_level: 'Pro' },
    { name: 'Player 2', is_ai: true, ai_level: 'Semi Pro' },
    { name: 'Player 3', is_ai: true, ai_level: 'Beginner' },
    { name: 'Player 4', is_ai: true, ai_level: 'Semi Pro' },
  ])
  const [mode, setMode] = useState('501')

  const setP = (i, patch) => setPlayers(players.map((p, j) => j === i ? { ...p, ...patch } : p))
  const addP = () => players.length < 8 && setPlayers([...players, { name: `Player ${players.length + 1}`, is_ai: true, ai_level: 'Semi Pro' }])
  const rmP = (i) => players.length > 2 && setPlayers(players.filter((_, j) => j !== i))

  // ── Active cup: bracket view ────────────────────────────────────────────
  if (tournament && tournament.status) {
    const t = tournament
    const champ = t.champion
    // Next pending tie (both opponents real, no winner yet)
    let nextTie = null
    for (const m of (t.rounds[t.cur_round] || [])) {
      if (m.winner == null && m.a && m.b) { nextTie = m; break }
    }
    return (
      <div className="w-full max-w-5xl mx-auto p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Trophy className="w-6 h-6 text-amber-400" />
            <div>
              <div className="text-lg font-bold tracking-wide">{t.mode === 'X01' ? `${t.config?.start_score ?? 501}` : t.mode} Cup</div>
              <div className="text-xs text-white/40 uppercase tracking-widest">{t.players.length} players · single elimination</div>
            </div>
          </div>
          <button onClick={onEnd} className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold text-red-300 hover:bg-red-500/15 border border-red-400/20">
            <Flag className="w-3.5 h-3.5" /> End cup
          </button>
        </div>

        {champ && (
          <div className="rounded-2xl bg-gradient-to-br from-amber-500/20 to-amber-700/10 border border-amber-400/30 p-6 text-center">
            <Trophy className="w-10 h-10 text-amber-300 mx-auto mb-2" />
            <div className="text-xs uppercase tracking-[0.3em] text-amber-200/70">Champion</div>
            <div className="text-3xl font-black text-amber-100 mt-1">{champ}</div>
          </div>
        )}

        {!champ && nextTie && (
          <div className="flex items-center justify-between rounded-xl bg-cyan-500/10 border border-cyan-400/30 px-5 py-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-cyan-300/70">Next tie</div>
              <div className="text-sm font-bold text-white">{nextTie.a.name} <span className="text-white/40">vs</span> {nextTie.b.name}</div>
            </div>
            <button onClick={() => { onNext?.(); onGoLive?.() }}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider bg-cyan-500/25 border border-cyan-400/50 text-cyan-100 hover:bg-cyan-500/35">
              <Play className="w-3.5 h-3.5" /> Play tie
            </button>
          </div>
        )}

        {/* Bracket: rounds as columns */}
        <div className="flex gap-4 overflow-x-auto pb-2">
          {t.rounds.map((rnd, ri) => (
            <div key={ri} className="flex-1 min-w-[180px] space-y-3">
              <div className="text-[10px] uppercase tracking-widest text-white/40 text-center">{roundLabel(rnd.length, ri)}</div>
              <div className="space-y-3 flex flex-col justify-around h-full">
                {rnd.map((m, mi) => (
                  <div key={mi} className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
                    {[m.a, m.b].map((pl, k) => {
                      const name = pl?.name ?? (k === 1 ? 'bye' : '—')
                      const won = m.winner && m.winner === name
                      const lost = m.winner && pl && m.winner !== name
                      return (
                        <div key={k} className={`flex items-center justify-between px-3 py-2 text-sm ${k === 0 ? 'border-b border-white/10' : ''} ${
                          won ? 'bg-emerald-500/15 text-emerald-200 font-bold' : lost ? 'text-white/30 line-through' : 'text-white/80'}`}>
                          <span className="truncate">{name}{pl?.is_ai ? ' 🤖' : ''}</span>
                          {won && <Trophy className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                        </div>
                      )
                    })}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ── Setup ───────────────────────────────────────────────────────────────
  const field = 'px-3 py-2 rounded-lg bg-black/50 border border-white/10 focus:border-cyan-400/50 outline-none text-sm'
  return (
    <div className="w-full max-w-xl mx-auto p-8 space-y-6">
      <div className="flex items-center gap-3">
        <Swords className="w-6 h-6 text-cyan-400" />
        <div>
          <div className="text-lg font-bold">New Cup</div>
          <div className="text-xs text-white/40 uppercase tracking-widest">Single-elimination · 2–8 players</div>
        </div>
      </div>

      <div>
        <label className="text-xs uppercase tracking-widest text-white/40">Game type</label>
        <div className="grid grid-cols-4 gap-2 mt-2">
          {MODES.map(m => (
            <button key={m} onClick={() => setMode(m)}
              className={`py-2 rounded-xl text-xs font-semibold border transition-all ${
                mode === m ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300' : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10'}`}>
              {m}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs uppercase tracking-widest text-white/40">Players ({players.length})</label>
        <div className="space-y-2 mt-2">
          {players.map((p, i) => (
            <div key={i} className="flex items-center gap-2 bg-white/5 p-2 rounded-xl border border-white/5">
              <input value={p.name} onChange={e => setP(i, { name: e.target.value })} className={field + ' flex-1'} />
              <button onClick={() => setP(i, { is_ai: !p.is_ai })}
                className={`px-2.5 py-2 rounded-lg text-xs font-bold border ${p.is_ai ? 'bg-violet-500/20 border-violet-400/50 text-violet-200' : 'bg-white/5 border-white/10 text-white/50'}`}>
                {p.is_ai ? 'AI' : 'Human'}
              </button>
              {p.is_ai && (
                <select value={p.ai_level} onChange={e => setP(i, { ai_level: e.target.value })} className={field}>
                  {LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
                </select>
              )}
              {players.length > 2 && (
                <button onClick={() => rmP(i)} className="px-2 py-2 rounded-lg bg-white/5 hover:bg-red-500/20 border border-white/10 text-white/50 hover:text-red-300">
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
        {players.length < 8 && (
          <button onClick={addP} className="mt-2 flex items-center gap-1.5 text-xs text-cyan-300/80 hover:text-cyan-200">
            <Plus className="w-4 h-4" /> Add player
          </button>
        )}
      </div>

      <button onClick={() => onStart?.(buildPayload(players, mode))}
        disabled={players.filter(p => p.name.trim()).length < 2}
        className="w-full py-3 rounded-xl text-sm font-bold uppercase tracking-wider bg-cyan-500/20 border border-cyan-400/50 text-cyan-200 hover:bg-cyan-500/30 disabled:opacity-40">
        Start Cup 🏆
      </button>
    </div>
  )
}
