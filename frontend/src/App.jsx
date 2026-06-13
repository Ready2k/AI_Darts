import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Settings, LineChart, Target, Camera, Crosshair,
  Play, Square, RefreshCw, Layers, Trophy, Undo2, Plus, X, Check, Bug, Star,
  Maximize2, Minimize2, Menu, ChevronLeft
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell
} from 'recharts'
import DartBoard from './DartBoard'
import AvatarPicker from './components/AvatarPicker'
import OcheCam from './components/OcheCam'
import Caricature from './art/Caricature'
import { useThrowAnimation } from './hooks/useThrowAnimation'
import { ThrowState } from './config/timing'
import CinematicDemo from './cinematic/CinematicDemo'
import CinematicGame from './cinematic/CinematicGame'
import { unlockAudio, sound } from './cinematic/audio'
import { SCRIPTS } from './cinematic/scripts'
import { getAvatar } from './config/avatars'

const API_URL = 'http://localhost:8000/api'
const WS_URL = 'ws://localhost:8000/ws/game'
const JSON_HEADERS = { 'Content-Type': 'application/json' }

function scoreToWords(n) {
  if (n === 180) return 'One hundred and eighty!'
  const ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
    'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']
  const tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
  if (n === 0) return 'zero'
  if (n < 20) return ones[n]
  if (n < 100) { const t = Math.floor(n / 10), o = n % 10; return o ? `${tens[t]}-${ones[o]}` : tens[t] }
  const rem = n - 100
  if (rem === 0) return 'One hundred'
  if (rem < 20) return `One hundred and ${ones[rem]}`
  const t = Math.floor(rem / 10), o = rem % 10
  return `One hundred and ${o ? `${tens[t]}-${ones[o]}` : tens[t]}`
}

function visitTotalToSpeech(total, { bust = false, legWon = false } = {}) {
  if (bust) return 'No score!'
  const words = scoreToWords(total)
  const cap = words.charAt(0).toUpperCase() + words.slice(1)
  if (legWon) return `Game shot! ${total === 180 ? cap : cap + '!'}`
  return total === 180 ? cap : `${cap}.`
}

// ── Live game state via WebSocket push (auto-reconnecting) ──────────────────
function useGame() {
  const [game, setGame] = useState(null)

  useEffect(() => {
    let stopped = false
    let ws
    let retry

    const connect = () => {
      ws = new WebSocket(WS_URL)
      ws.onmessage = (e) => {
        let data
        try { data = JSON.parse(e.data) } catch { return }
        setGame(data)
      }
      ws.onclose = () => { if (!stopped) retry = setTimeout(connect, 1000) }
      ws.onerror = () => ws.close()
    }
    connect()

    return () => { stopped = true; clearTimeout(retry); if (ws) ws.close() }
  }, [])

  const refresh = useCallback(() => {}, [])
  return [game, refresh]
}

const hasGame = (g) => g && g.running !== false && Array.isArray(g.players)

// ── Scoreboard ─────────────────────────────────────────────────────────────
function PlayerRow({ p, active, avatar }) {
  const icon = getAvatar(avatar)
  return (
    <div className={`flex items-center justify-between rounded-xl px-5 py-4 border transition-all ${
      active ? 'bg-cyan-500/10 border-cyan-400/50 shadow-[0_0_25px_rgba(0,240,255,0.15)]'
             : 'bg-white/5 border-white/10'}`}>
      <div className="flex items-center gap-3">
        {icon && (
          <div className="w-8 h-8 rounded-full overflow-hidden border border-white/20" style={{ background: icon.bg }}>
            <Caricature variant={icon.variant} framing="bust" className="w-full h-full" />
          </div>
        )}
        {active && !icon && <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />}
        <div>
          <div className={`font-semibold tracking-wide ${active ? 'text-white' : 'text-white/70'}`}>{p.name}</div>
          <div className="text-[11px] text-white/40 uppercase tracking-wider">
            Sets {p.sets} · Legs {p.legs} · {p.avg.toFixed(1)} avg
          </div>
        </div>
      </div>
      <div className={`text-4xl font-bold tabular-nums ${active ? 'text-cyan-300' : 'text-white/50'}`}>
        {p.score}
      </div>
    </div>
  )
}

function Scoreboard({ game, avatarMap }) {
  if (!hasGame(game)) {
    return (
      <div className="text-center text-white/40 py-10 text-sm">
        No game yet — start one in <span className="text-cyan-400">Settings</span>.
      </div>
    )
  }
  return (
    <div className="space-y-3">
      {game.over && (
        <div className="flex items-center gap-3 rounded-xl px-5 py-4 bg-emerald-500/15 border border-emerald-400/50">
          <Trophy className="w-6 h-6 text-emerald-300" />
          <span className="text-lg font-semibold text-emerald-200">{game.message}</span>
        </div>
      )}
      {game.players.map((p, i) => (
        <PlayerRow key={i} p={p} active={i === game.current && !game.over} avatar={avatarMap[p.name]} />
      ))}
    </div>
  )
}

// ── Game setup form ─────────────────────────────────────────────────────────
function GameSetup({ onStarted }) {
  const [players, setPlayers] = useState([{ name: 'Player 1', avatar: 'pubguy', is_ai: false, ai_level: 'Beginner' }])
  const [gameMode, setGameMode] = useState('501')
  const [startScore, setStartScore] = useState(501)
  const [doubleOut, setDoubleOut] = useState(true)
  const [legs, setLegs] = useState(3)
  const [busy, setBusy] = useState(false)

  const setPlayerName = (i, v) => setPlayers(players.map((p, j) => (j === i ? { ...p, name: v } : p)))
  const setPlayerAvatar = (i, v) => setPlayers(players.map((p, j) => (j === i ? { ...p, avatar: v } : p)))
  const setPlayerType = (i, is_ai) => setPlayers(players.map((p, j) => (j === i ? { ...p, is_ai } : p)))
  const setPlayerLevel = (i, ai_level) => setPlayers(players.map((p, j) => (j === i ? { ...p, ai_level } : p)))
  const addPlayer = () => players.length < 6 && setPlayers([...players, { name: `Player ${players.length + 1}`, avatar: 'pubguy', is_ai: false, ai_level: 'Beginner' }])
  const removePlayer = (i) => players.length > 1 && setPlayers(players.filter((_, j) => j !== i))

  const start = async () => {
    unlockAudio()
    setBusy(true)
    try {
      const playerConfigs = players.map(p => ({
        name: p.name,
        is_ai: p.is_ai || false,
        ai_level: p.ai_level || 'Beginner'
      }))
      await fetch(`${API_URL}/game/new`, {
        method: 'POST', headers: JSON_HEADERS,
        body: JSON.stringify({
          players: playerConfigs, start_score: startScore, double_in: false,
          double_out: doubleOut, legs_to_win: legs, sets_to_win: 1,
        }),
      })
      
      const pMap = {}
      players.forEach(p => pMap[p.name] = p.avatar)
      onStarted?.(pMap)
    } finally { setBusy(false) }
  }

  return (
    <div className="max-w-xl w-full mx-auto space-y-6 p-8">
      <div>
        <label className="text-xs uppercase tracking-widest text-white/40">Game Type</label>
        <div className="flex gap-2 mt-2">
          {['301', '501', '701', 'Cricket'].map(mode => (
            <button key={mode} onClick={() => {
              setGameMode(mode);
              if (mode !== 'Cricket') setStartScore(parseInt(mode, 10));
            }}
              className={`flex-1 py-2.5 rounded-xl text-sm font-semibold border transition-all ${
                gameMode === mode 
                  ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300 shadow-[0_0_15px_rgba(0,240,255,0.15)]' 
                  : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10'
              }`}>
              {mode}
            </button>
          ))}
        </div>
        {gameMode === 'Cricket' && (
          <div className="mt-3 text-xs text-amber-400/80 bg-amber-500/10 p-3 rounded-xl border border-amber-500/20">
            Cricket is currently in development. Please select an X01 game mode.
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs uppercase tracking-widest text-white/40">Out Rule</label>
          <div className="flex gap-2 mt-2">
            <button onClick={() => setDoubleOut(false)}
              className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all ${
                !doubleOut ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300 shadow-[0_0_15px_rgba(0,240,255,0.15)]' : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10'
              }`}>Straight Out</button>
            <button onClick={() => setDoubleOut(true)}
              className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all ${
                doubleOut ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300 shadow-[0_0_15px_rgba(0,240,255,0.15)]' : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10'
              }`}>Double Out</button>
          </div>
        </div>
        <div>
          <label className="text-xs uppercase tracking-widest text-white/40">Legs to Win</label>
          <div className="flex gap-2 mt-2">
            {[1, 3, 5].map(l => (
              <button key={l} onClick={() => setLegs(l)}
                className={`flex-1 py-2 rounded-xl text-sm font-semibold border transition-all ${
                  legs === l ? 'bg-cyan-500/20 border-cyan-400/50 text-cyan-300 shadow-[0_0_15px_rgba(0,240,255,0.15)]' : 'bg-white/5 border-white/10 text-white/50 hover:bg-white/10'
                }`}>{l}</button>
            ))}
          </div>
        </div>
      </div>

      <div>
        <label className="text-xs uppercase tracking-widest text-white/40">Players</label>
        <div className="space-y-4 mt-2">
          {players.map((p, i) => (
            <div key={i} className="flex flex-col gap-2 bg-white/5 p-3 rounded-xl border border-white/5">
              <div className="flex gap-4 items-center">
                <AvatarPicker selectedId={p.avatar} onChange={(id) => setPlayerAvatar(i, id)} />
                <div className="flex-1 flex gap-2">
                  <input value={p.name} onChange={(e) => setPlayerName(i, e.target.value)}
                    className="flex-1 px-4 py-2.5 rounded-lg bg-black/50 border border-white/10 focus:border-cyan-400/50 outline-none text-sm" />
                  {players.length > 1 && (
                    <button onClick={() => removePlayer(i)}
                      className="px-3 rounded-lg bg-white/5 hover:bg-red-500/20 border border-white/10 text-white/50 hover:text-red-300">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
              <div className="flex gap-2 justify-end items-center mt-1">
                <span className="text-xs text-white/40 uppercase">Type:</span>
                <select 
                  value={p.is_ai ? 'AI' : 'Human'} 
                  onChange={(e) => setPlayerType(i, e.target.value === 'AI')}
                  className="bg-black/50 border border-white/10 rounded-lg px-2 py-1 text-xs outline-none focus:border-cyan-400/50"
                >
                  <option value="Human">Human</option>
                  <option value="AI">AI Player</option>
                </select>
                {p.is_ai && (
                  <select 
                    value={p.ai_level || 'Beginner'} 
                    onChange={(e) => setPlayerLevel(i, e.target.value)}
                    className="bg-black/50 border border-white/10 rounded-lg px-2 py-1 text-xs outline-none focus:border-cyan-400/50 text-cyan-300"
                  >
                    <option value="Beginner">Beginner</option>
                    <option value="Semi Pro">Semi Pro</option>
                    <option value="Pro">Pro</option>
                  </select>
                )}
              </div>
            </div>
          ))}
          {players.length < 6 && (
            <button onClick={addPlayer}
              className="flex items-center gap-2 text-sm text-cyan-400/80 hover:text-cyan-300 px-2 py-1">
              <Plus className="w-4 h-4" /> Add player
            </button>
          )}
        </div>
      </div>
      <button onClick={start} disabled={busy || gameMode === 'Cricket'}
        className="w-full flex items-center justify-center gap-2 px-4 py-3.5 rounded-xl bg-gradient-to-r from-cyan-500/30 to-fuchsia-500/30 hover:from-cyan-500/40 hover:to-fuchsia-500/40 border border-cyan-400/30 font-semibold tracking-wide disabled:opacity-50">
        <Check className="w-5 h-5" /> Start game
      </button>
    </div>
  )
}

// ── MJPEG stream + input forwarding ────────────────────────────────────────
function StreamViewer({ scriptName }) {
  const [src] = useState(() => `${API_URL}/stream/${scriptName}?t=${Date.now()}`)
  const post = (body) =>
    fetch(`${API_URL}/event/${scriptName}`, {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body),
    }).catch(() => {})

  useEffect(() => {
    const onKey = (e) => post({ type: 'keydown', key: e.key })
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [scriptName])

  const mouse = (e, type) => {
    const img = e.currentTarget.querySelector('img')
    if (!img) return
    const rect = img.getBoundingClientRect()
    const nw = img.naturalWidth || 960
    const nh = img.naturalHeight || 540
    const imgRatio = nw / nh
    const rectRatio = rect.width / rect.height
    let rw = rect.width, rh = rect.height, ox = 0, oy = 0
    if (imgRatio > rectRatio) { rh = rect.width / imgRatio; oy = (rect.height - rh) / 2 }
    else { rw = rect.height * imgRatio; ox = (rect.width - rw) / 2 }
    const x = ((e.clientX - rect.left - ox) / rw) * nw
    const y = ((e.clientY - rect.top - oy) / rh) * nh
    post({ type, x, y })
  }

  return (
    <div
      className="relative w-full h-full flex items-center justify-center bg-black/40 rounded-xl overflow-hidden border border-white/10"
      onPointerDown={(e) => mouse(e, 'mousedown')}
      onPointerMove={(e) => e.buttons > 0 && mouse(e, 'mousemove')}
      onPointerUp={(e) => mouse(e, 'mouseup')}
    >
      <img src={src} className="max-w-full max-h-full object-contain pointer-events-none" alt={`${scriptName} stream`} />
    </div>
  )
}

function GameControls({ onRefresh, onNewGame }) {
  const [confirmEnd, setConfirmEnd] = useState(false)

  const undo = async () => {
    await fetch(`${API_URL}/game/undo`, { method: 'POST' }).catch(() => {})
    onRefresh?.()
  }
  const endGame = async () => {
    await fetch(`${API_URL}/game/end`, { method: 'POST' }).catch(() => {})
    setConfirmEnd(false)
    onRefresh?.()
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-3">
        <button onClick={undo} className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-sm font-semibold transition-colors">
          <Undo2 className="w-4 h-4" /> Undo dart
        </button>
        <button onClick={onNewGame} className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-400/30 text-cyan-200 text-sm font-semibold transition-colors">
          <RefreshCw className="w-4 h-4" /> New game
        </button>
      </div>
      <button onClick={async () => { await fetch(`${API_URL}/debug/simulate_hit`, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ label: "T20" }) }); onRefresh?.(); }}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-fuchsia-500/15 hover:bg-fuchsia-500/25 border border-fuchsia-400/30 text-fuchsia-200 text-sm font-semibold transition-colors">
        <Target className="w-4 h-4" /> Simulate Treble 20 Throw
      </button>

      {!confirmEnd ? (
        <button onClick={() => setConfirmEnd(true)} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-red-500/15 border border-white/10 hover:border-red-400/30 text-white/50 hover:text-red-300 text-sm font-semibold transition-colors">
          <Square className="w-4 h-4" /> End game
        </button>
      ) : (
        <div className="flex gap-2">
          <button onClick={endGame} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-red-500/20 hover:bg-red-500/30 border border-red-400/40 text-red-200 text-sm font-semibold transition-colors">
            <Check className="w-4 h-4" /> Confirm end
          </button>
          <button onClick={() => setConfirmEnd(false)} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 text-sm font-semibold transition-colors">
            <X className="w-4 h-4" /> Cancel
          </button>
        </div>
      )}
    </div>
  )
}

function DebugSnapshot() {
  const [status, setStatus] = useState(null)
  const snap = async () => {
    setStatus('saving…')
    try {
      const r = await fetch(`${API_URL}/debug/snapshot`, { method: 'POST' })
      const d = await r.json()
      setStatus(`✓ ${d.ts}`)
    } catch { setStatus('failed') }
    setTimeout(() => setStatus(null), 4000)
  }
  return (
    <button onClick={snap} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 hover:bg-amber-500/15 border border-white/10 hover:border-amber-400/30 text-white/40 hover:text-amber-300 text-xs font-semibold transition-colors">
      <Bug className="w-3.5 h-3.5" />
      {status ?? 'Debug snapshot'}
    </button>
  )
}

function Placeholder({ icon: Icon, title, text }) {
  return (
    <div className="text-center space-y-5 opacity-60">
      <Icon className="w-20 h-20 mx-auto text-white/20" strokeWidth={1} />
      <div>
        <h3 className="text-xl font-light tracking-wider mb-2">{title}</h3>
        <p className="text-white/50 max-w-md mx-auto text-sm">{text}</p>
      </div>
    </div>
  )
}

function StreamPanel({ script, label, hint, extraButtons, allowPopout }) {
  const [on, setOn] = useState(false)
  const [popout, setPopout] = useState(false)
  
  const content = (
    <div className="w-full h-full flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <button onClick={() => setOn(!on)} className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-colors ${on ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30' : 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30'}`}>
          {on ? <><Square className="w-3 h-3" /> Stop</> : <><Play className="w-3 h-3" /> Start {label}</>}
        </button>
        {on && extraButtons}
        {allowPopout && on && (
          <button onClick={() => setPopout(true)} className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 text-xs font-bold transition-colors ml-auto">
            <Maximize2 className="w-4 h-4" />
          </button>
        )}
        {!allowPopout && <span className="text-xs text-white/40">{hint}</span>}
      </div>
      <div className="flex-1 min-h-0 relative" onClick={() => { if (allowPopout && on) setPopout(true) }}>
        {on ? (
          <div className={allowPopout ? "w-full h-full cursor-pointer hover:ring-2 hover:ring-cyan-400/50 rounded-xl transition-all" : "w-full h-full"}>
            <StreamViewer scriptName={script} />
          </div>
        ) : (
          <div className="w-full h-full flex items-center justify-center rounded-xl bg-black/30 border border-white/10 p-4">
            <Placeholder icon={Camera} title={`${label} idle`} text="Press Start to open the camera stream." />
          </div>
        )}
      </div>
    </div>
  )

  if (popout) {
    return (
      <>
        {content}
        <div className="fixed inset-0 z-50 bg-black/95 flex flex-col items-center justify-center p-4 sm:p-8 backdrop-blur-md"
             onClick={() => setPopout(false)}>
          <div className="w-full max-w-7xl h-full flex flex-col gap-4 relative" onClick={e => e.stopPropagation()}>
             <div className="flex justify-between items-center shrink-0">
                <div className="flex items-center gap-3">
                  <Camera className="w-6 h-6 text-cyan-400" />
                  <h3 className="text-xl tracking-wide font-light uppercase">{label} Stream</h3>
                </div>
                <button onClick={() => setPopout(false)} className="p-3 rounded-xl bg-white/10 hover:bg-white/20 text-white transition-colors flex items-center gap-2">
                  <Minimize2 className="w-5 h-5" /> <span className="text-sm font-medium pr-1">Close</span>
                </button>
             </div>
             <div className="flex-1 min-h-0 rounded-xl overflow-hidden border border-white/20 bg-black shadow-2xl relative flex items-center justify-center">
                <StreamViewer scriptName={script} />
             </div>
          </div>
        </div>
      </>
    )
  }

  return content
}

function AlignButtons() {
  const send = (type) => fetch(`${API_URL}/event/align`, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ type }) }).catch(() => {})
  return (
    <>
      <button onClick={() => send('auto')} className="px-3 py-2 rounded-lg bg-fuchsia-500/15 text-fuchsia-200 text-xs font-bold uppercase tracking-wider hover:bg-fuchsia-500/25">Auto-detect</button>
      <button onClick={() => send('confirm')} className="px-3 py-2 rounded-lg bg-cyan-500/15 text-cyan-200 text-xs font-bold uppercase tracking-wider hover:bg-cyan-500/25">Confirm camera</button>
      <button onClick={() => send('reset')} className="px-3 py-2 rounded-lg bg-white/5 text-white/60 text-xs font-bold uppercase tracking-wider hover:bg-white/10">Reset</button>
      <DebugSnapshot />
    </>
  )
}

function CorrectionBoard({ game, onRefresh, isLarge, boardDarts, ocheCam }) {
  const [armed, setArmed] = useState(false)
  const darts = boardDarts ?? game?.turn ?? []
  if (!hasGame(game)) {
    return (
      <div className={`rounded-xl bg-black/30 border border-white/10 p-4 space-y-3 relative ${isLarge ? 'h-full flex flex-col' : ''}`}>
         {isLarge && ocheCam && (
           <div className="absolute top-4 left-4 z-20">
             {ocheCam}
           </div>
         )}
         <div className="flex items-center justify-end shrink-0 min-h-[32px]">
           {!isLarge && <span className="text-xs uppercase tracking-widest text-white/40 mr-auto">Board</span>}
         </div>
         <div className={isLarge ? 'flex-1 min-h-0 flex items-center justify-center relative' : 'relative'}>
           <DartBoard darts={[]} />
         </div>
      </div>
    )
  }

  const pick = async (x_mm, y_mm) => {
    await fetch(`${API_URL}/game/correct`, {
      method: 'POST', headers: JSON_HEADERS, body: JSON.stringify({ x_mm, y_mm }),
    }).catch(() => {})
    setArmed(false)
    onRefresh?.()
  }
  const hasDart = game.turn && game.turn.some((d) => d.pos)

  return (
    <div className={`rounded-xl bg-black/30 border border-white/10 p-4 space-y-3 relative ${isLarge ? 'h-full flex flex-col' : ''}`}>
      {isLarge && ocheCam && (
        <div className="absolute top-4 left-4 z-20">
          {ocheCam}
        </div>
      )}
      <div className="flex items-center justify-end shrink-0 min-h-[32px]">
        {!isLarge && <span className="text-xs uppercase tracking-widest text-white/40 mr-auto">Board</span>}
        <button onClick={() => setArmed(!armed)} disabled={!hasDart}
          className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wider border transition-colors relative z-20 ${
            armed ? 'bg-cyan-500/25 border-cyan-400/50 text-cyan-200'
                  : 'bg-white/5 border-white/10 text-white/60 hover:bg-white/10'} disabled:opacity-40`}>
          {armed ? 'Cancel' : 'Correct last dart'}
        </button>
      </div>
      <div className={isLarge ? 'flex-1 min-h-0 flex items-center justify-center relative' : 'relative'}>
        <DartBoard darts={darts} armed={armed} onPick={pick} />
      </div>
    </div>
  )
}

function MatchHistory() {
  const [rows, setRows] = useState([])
  useEffect(() => { fetch(`${API_URL}/history`).then((r) => r.json()).then(setRows).catch(() => setRows([])) }, [])
  if (rows.length === 0) return null
  return (
    <div className="rounded-xl bg-black/30 border border-white/10 p-4">
      <div className="text-xs uppercase tracking-widest text-white/40 mb-3">Recent matches</div>
      <div className="space-y-2">
        {rows.map((m, i) => (
          <div key={i} className="flex items-center justify-between text-sm border-b border-white/5 last:border-0 pb-2 gap-3">
            <div className="flex items-center gap-2 shrink-0">
              <Trophy className="w-4 h-4 text-emerald-300" />
              <span className="font-medium">{m.winner}</span>
              <span className="text-white/40 text-xs">{m.start_score}·{m.double_out ? 'DO' : 'SO'}</span>
            </div>
            <div className="text-white/50 text-xs truncate">
              {m.players.map((p) => `${p.name} ${p.sets}-${p.legs} (${p.avg})`).join('  ·  ')}
            </div>
            <span className="text-white/30 text-xs shrink-0">{m.ts}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Stats({ game }) {
  const data = hasGame(game) ? game.players.map((p) => ({ name: p.name, avg: Number(p.avg.toFixed(1)) })) : []
  const colors = ['#22d3ee', '#e879f9', '#34d399', '#fbbf24', '#f87171', '#a78bfa']
  return (
    <div className="w-full max-w-3xl mx-auto space-y-6">
      {!hasGame(game) && <Placeholder icon={LineChart} title="No active game" text="Start a game to see live averages." />}
      {hasGame(game) && (<>
      <div className="h-64 rounded-xl bg-black/30 border border-white/10 p-4">
        <div className="text-xs uppercase tracking-widest text-white/40 mb-2">3-dart average</div>
        <ResponsiveContainer width="100%" height="90%">
          <BarChart data={data}>
            <XAxis dataKey="name" tick={{ fill: '#ffffff80', fontSize: 12 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: '#ffffff60', fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: '#ffffff10' }} contentStyle={{ background: '#111', border: '1px solid #333', borderRadius: 8 }} />
            <Bar dataKey="avg" radius={[6, 6, 0, 0]}>
              {data.map((_, i) => <Cell key={i} fill={colors[i % colors.length]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="rounded-xl bg-black/30 border border-white/10 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-white/40 uppercase tracking-wider text-[11px]">
            <tr className="border-b border-white/10">
              <th className="text-left px-5 py-3">Player</th>
              <th className="text-right px-5 py-3">Remaining</th>
              <th className="text-right px-5 py-3">Darts</th>
              <th className="text-right px-5 py-3">Avg</th>
              <th className="text-right px-5 py-3">Legs</th>
              <th className="text-right px-5 py-3">Sets</th>
            </tr>
          </thead>
          <tbody>
            {game.players.map((p, i) => (
              <tr key={i} className="border-b border-white/5 last:border-0">
                <td className="px-5 py-3 font-medium">{p.name}</td>
                <td className="px-5 py-3 text-right tabular-nums">{p.score}</td>
                <td className="px-5 py-3 text-right tabular-nums text-white/60">{p.darts}</td>
                <td className="px-5 py-3 text-right tabular-nums text-cyan-300">{p.avg.toFixed(1)}</td>
                <td className="px-5 py-3 text-right tabular-nums">{p.legs}</td>
                <td className="px-5 py-3 text-right tabular-nums">{p.sets}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </>)}
      <MatchHistory />
    </div>
  )
}

const TABS = [
  { name: 'Dashboard', icon: Layers },
  { name: 'Live Track', icon: Target },
  { name: 'Align', icon: Crosshair },
  { name: 'Cameras', icon: Camera },
  { name: 'Stats', icon: LineChart },
  { name: 'Leaderboard', icon: Trophy },
  { name: 'Settings', icon: Settings },
]

function Leaderboard() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/leaderboard`)
      .then(res => res.json())
      .then(d => {
        setData(d)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6">
      {loading ? (
        <div className="text-white/40 text-center py-8 flex justify-center items-center gap-2">
           <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" /> Loading...
        </div>
      ) : data.length === 0 ? (
        <Placeholder icon={Trophy} title="No Data" text="Play some games to see the leaderboard." />
      ) : (
        <div className="rounded-xl bg-black/30 border border-white/10 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="text-white/40 uppercase tracking-wider text-[11px]">
              <tr className="border-b border-white/10 bg-black/40">
                <th className="text-center px-4 py-4 w-16">Rank</th>
                <th className="text-left px-5 py-4">Player</th>
                <th className="text-right px-5 py-4">Played</th>
                <th className="text-right px-5 py-4">Won</th>
                <th className="text-right px-5 py-4">Lost</th>
                <th className="text-right px-5 py-4">Win %</th>
                <th className="text-right px-5 py-4">Avg</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p, i) => (
                <tr key={i} className="border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors">
                  <td className="px-4 py-4 text-center font-bold text-white/50">{p.rank}</td>
                  <td className="px-5 py-4 font-medium text-cyan-300">{p.name}</td>
                  <td className="px-5 py-4 text-right tabular-nums text-white/60">{p.played}</td>
                  <td className="px-5 py-4 text-right tabular-nums text-emerald-400">{p.won}</td>
                  <td className="px-5 py-4 text-right tabular-nums text-red-400/80">{p.lost}</td>
                  <td className="px-5 py-4 text-right tabular-nums">{p.win_rate.toFixed(1)}%</td>
                  <td className="px-5 py-4 text-right tabular-nums font-bold text-fuchsia-300">{p.avg.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Cinematic-mode toggle (used in Settings + Live Track) ────────────────────
function CinematicToggle({ on, onChange, disabled = false }) {
  return (
    <button
      onClick={() => !disabled && onChange(!on)}
      disabled={disabled}
      title={disabled ? 'Cinematic mode needs a 2-player game' : undefined}
      className={`flex items-center gap-3 px-4 py-2.5 rounded-xl border text-sm font-semibold transition-all ${
        disabled
          ? 'bg-white/5 border-white/10 text-white/30 cursor-not-allowed'
          : on
            ? 'bg-gradient-to-r from-orange-500/25 to-fuchsia-500/25 border-orange-400/40 text-orange-200'
            : 'bg-white/5 border-white/10 text-white/70 hover:bg-white/10'
      }`}>
      <Star className={`w-4 h-4 ${on && !disabled ? 'text-amber-400' : ''}`} />
      Cinematic mode
      <span className={`ml-1 relative w-9 h-5 rounded-full transition-colors ${on && !disabled ? 'bg-orange-400/80' : 'bg-white/15'}`}>
        <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all ${on && !disabled ? 'left-4' : 'left-0.5'}`} />
      </span>
    </button>
  )
}

// ── App shell ───────────────────────────────────────────────────────────────
function App() {
  const [activeTab, setActiveTab] = useState('Dashboard')
  const [game] = useGame()
  const [avatarMap, setAvatarMap] = useState({})
  const [showDemo, setShowDemo] = useState(false)
  const [demoScript, setDemoScript] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [cinematicMode, setCinematicMode] = useState(
    () => localStorage.getItem('cinematicMode') === '1'
  )

  // Toggle cinematic mode; enabling it is a user gesture so we can unlock audio
  // and switch the caller voice on for the live broadcast.
  const setCinematic = useCallback((on) => {
    setCinematicMode(on)
    localStorage.setItem('cinematicMode', on ? '1' : '0')
    if (on) { unlockAudio(); sound.setEnabled(true) }
  }, [])

  const { animState, currentDart, triggerThrow, triggerWalkOn } = useThrowAnimation()
  const pendingAnnouncement = useRef(null)

  const launchDemo = useCallback(() => {
    setDemoScript(SCRIPTS[Math.floor(Math.random() * SCRIPTS.length)])
    setShowDemo(true)
  }, [])

  useEffect(() => {
    window.addEventListener('start-demo', launchDemo)
    return () => window.removeEventListener('start-demo', launchDemo)
  }, [launchDemo])

  const leader = hasGame(game) ? [...game.players].sort((a, b) => a.score - b.score)[0] : null

  // animatingTurn holds the full set of darts to show on the board during a
  // throw animation. Cleared in onScored. Needed for the 3rd dart: game.turn
  // resets to [] synchronously in the backend, so we capture display_turn
  // (which includes the just-completed visit via _last_visit_turn) before it
  // disappears from the game state.
  const [animatingTurn, setAnimatingTurn] = useState(null)
  const [displayedGame, setDisplayedGame] = useState(game)
  const uiGame = displayedGame || game

  // Dart detection via dart_seq (monotonic) rather than turn.length so that
  // the 3rd dart of a visit is detected even after game.turn has reset to [].
  useEffect(() => {
    if (!hasGame(game) || !hasGame(displayedGame)) {
      setTimeout(() => { setAnimatingTurn(null); setDisplayedGame(game) }, 0)
      return
    }

    const prevSeq = displayedGame.dart_seq ?? 0
    const nextSeq = game.dart_seq ?? 0

    if (nextSeq > prevSeq) {
      // New dart — get it from display_turn (handles the 3rd-dart reset case)
      const dispTurn = game.display_turn || game.turn || []
      const newDart = dispTurn[dispTurn.length - 1]
      // Capture game in a const so the closure below always sees this snapshot
      const capturedGame = game

      // Compute visit-total announcement when this dart ends the visit.
      // turn resets to [] in the backend on turn completion, so an empty turn
      // with a non-empty display_turn means the visit just finished.
      const turnOver = (capturedGame.turn?.length ?? 1) === 0
      if (turnOver && dispTurn.length > 0) {
        const visitTotal = dispTurn.reduce((sum, d) => sum + (d.points || 0), 0)
        const isBust = capturedGame.message?.includes('BUST') ?? false
        const isLegWon = capturedGame.message?.includes('wins') ?? false
        pendingAnnouncement.current = {
          text: visitTotalToSpeech(visitTotal, { bust: isBust, legWon: isLegWon }),
          visitTotal,
          legWon: isLegWon,
        }
      } else {
        pendingAnnouncement.current = null
      }

      setTimeout(() => {
        if (!newDart) { setDisplayedGame(capturedGame); return }
        setAnimatingTurn(dispTurn)
        triggerThrow({
          dartResult: newDart,
          mode: 'detected',
          onScored: () => {
            setAnimatingTurn(null)
            setDisplayedGame(capturedGame)
          },
        })
      }, 0)
    } else if (nextSeq < prevSeq) {
      // Undo or game reset
      setTimeout(() => { setAnimatingTurn(null); setDisplayedGame(game) }, 0)
    }
    // Player changes are handled automatically via setDisplayedGame(game) in onScored
  }, [game, triggerThrow, displayedGame])

  // Walk-on animation when the active player changes (fires after onScored updates displayedGame)
  const prevPlayerRef = useRef(-1)
  useEffect(() => {
    if (!hasGame(displayedGame) || displayedGame.over) { prevPlayerRef.current = -1; return }
    if (prevPlayerRef.current !== displayedGame.current) {
      prevPlayerRef.current = displayedGame.current
      triggerWalkOn()
    }
  }, [displayedGame, triggerWalkOn])

  // Sound effects tied to the throw animation lifecycle
  useEffect(() => {
    if (animState === ThrowState.THROWING) {
      sound.whoosh()
    } else if (animState === ThrowState.IMPACT) {
      sound.thud()
    } else if (animState === ThrowState.SCORING && currentDart) {
      const ann = pendingAnnouncement.current
      if (ann) {
        pendingAnnouncement.current = null
        if (ann.legWon) sound.cheer(true)
        else if (ann.visitTotal >= 100) sound.cheer(false)
        sound.say(ann.text, { rate: ann.legWon ? 0.85 : 0.9, pitch: ann.legWon ? 1.05 : 1.0 })
      }
    } else if (animState === ThrowState.CELEBRATING) {
      sound.cheer(true)
    }
  }, [animState, currentDart])

  const refresh = async () => {}

  return (
    <div className="flex h-screen bg-black text-white font-sans overflow-hidden">
      <div className="absolute inset-0 z-0 opacity-40 mix-blend-screen pointer-events-none">
        <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-[#FF0055] rounded-full blur-[150px] animate-pulse-slow" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-[#00F0FF] rounded-full blur-[150px] animate-pulse-slow" style={{ animationDelay: '2s' }} />
        <div className="absolute top-[40%] left-[40%] w-[30%] h-[30%] bg-[#7000FF] rounded-full blur-[120px] animate-pulse-slow" style={{ animationDelay: '4s' }} />
      </div>

      {/* Sidebar */}
      <aside className={`flex flex-col z-10 glass-panel border-r border-white/5 m-4 rounded-2xl shadow-2xl transition-all duration-300 ${sidebarCollapsed ? 'w-20 items-center' : 'w-64'}`}>
        <div className={`p-6 pb-2 flex items-center ${sidebarCollapsed ? 'justify-center p-4' : 'justify-between'}`}>
          {!sidebarCollapsed && (
            <div className="overflow-hidden">
              <h1 className="text-2xl font-bold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-fuchsia-500 mb-1 whitespace-nowrap">
                DARTS.AI
              </h1>
              <p className="text-xs text-white/50 tracking-widest uppercase whitespace-nowrap">Pro Vision System</p>
            </div>
          )}
          <button onClick={() => setSidebarCollapsed(!sidebarCollapsed)} className="p-2 -mr-2 rounded-lg hover:bg-white/10 text-white/50 hover:text-white transition-colors shrink-0">
            {sidebarCollapsed ? <Menu className="w-5 h-5" /> : <ChevronLeft className="w-5 h-5" />}
          </button>
        </div>
        <nav className={`flex-1 py-6 space-y-2 ${sidebarCollapsed ? 'px-2' : 'px-4'}`}>
          {TABS.map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.name
            return (
              <button key={tab.name} onClick={() => setActiveTab(tab.name)}
                title={sidebarCollapsed ? tab.name : undefined}
                className={`w-full flex items-center space-x-3 py-3 rounded-xl transition-all group ${
                  sidebarCollapsed ? 'justify-center px-0' : 'px-4'
                } ${
                  isActive ? 'bg-white/10 text-white shadow-[0_0_15px_rgba(255,255,255,0.1)]'
                           : 'text-white/60 hover:bg-white/5 hover:text-white'}`}>
                <Icon className={`w-5 h-5 shrink-0 ${isActive ? 'scale-110 text-cyan-400' : 'group-hover:text-cyan-400'}`} />
                {!sidebarCollapsed && <span className="font-medium tracking-wide text-sm whitespace-nowrap">{tab.name}</span>}
                {isActive && !sidebarCollapsed && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />}
              </button>
            )
          })}
        </nav>
        {!sidebarCollapsed ? (
          <div className="p-4 m-4 rounded-xl bg-gradient-to-br from-white/5 to-white/0 border border-white/10 overflow-hidden">
            <div className="flex items-center space-x-3 mb-2">
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
              <span className="text-xs font-semibold text-white/80 uppercase tracking-wider whitespace-nowrap">
                {hasGame(uiGame) ? (uiGame.over ? 'Game over' : 'Game live') : 'Idle'}
              </span>
            </div>
            <p className="text-[10px] text-white/40 whitespace-nowrap">
              {hasGame(uiGame) ? `${uiGame.start_score} · ${uiGame.double_out ? 'double out' : 'straight out'}` : 'No game running'}
            </p>
          </div>
        ) : (
          <div className="p-4 mb-4 flex justify-center shrink-0">
             <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col z-10 p-4 pl-0">
        <header className="h-16 flex items-center justify-between px-8 glass-panel rounded-2xl shadow-xl mb-4 border border-white/5">
          <h2 className="text-xl font-light tracking-wide">{activeTab}</h2>
          {leader && !uiGame.over && (
            <div className="text-sm text-white/50">
              Leader: <span className="text-cyan-300 font-semibold">{leader.name}</span> · {leader.score}
            </div>
          )}
        </header>

        <div className="flex-1 glass-panel rounded-2xl shadow-2xl border border-white/5 p-8 overflow-auto">
          {activeTab === 'Dashboard' && (
            <div className="h-full flex flex-col items-center justify-center gap-8">
              <Placeholder icon={Target} title="Welcome to DARTS.AI"
                text="3-camera computer-vision dart scoring with full X01 game logic, checkout suggestions and live stats." />
              <div className="flex gap-3 flex-wrap justify-center">
                <button onClick={() => setActiveTab('Settings')}
                  className="px-5 py-3 rounded-xl bg-cyan-500/15 border border-cyan-400/30 text-cyan-200 font-semibold text-sm">New game</button>
                <button onClick={() => setActiveTab('Live Track')}
                  className="px-5 py-3 rounded-xl bg-white/5 border border-white/10 font-semibold text-sm">Live tracking</button>
                <button onClick={() => setActiveTab('Align')}
                  className="px-5 py-3 rounded-xl bg-white/5 border border-white/10 font-semibold text-sm">Align cameras</button>
                <button onClick={() => { unlockAudio(); launchDemo() }}
                  className="flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-r from-orange-500/25 to-fuchsia-500/25 border border-orange-400/40 text-orange-200 font-semibold text-sm">
                  <Star className="w-4 h-4" /> Cinematic demo
                </button>
              </div>
            </div>
          )}

          {activeTab === 'Live Track' && (
            cinematicMode && hasGame(uiGame) && uiGame.players?.length === 2 ? (
              <div className="h-full">
                <CinematicGame
                  game={uiGame}
                  avatarMap={avatarMap}
                  animState={animState}
                  boardDarts={animatingTurn ?? uiGame?.turn}
                  cameraSrc={`${API_URL}/stream/detect`}
                  onExit={() => setCinematic(false)}
                />
              </div>
            ) : (
              <div className="h-full flex flex-col gap-4">
                <div className="flex items-center justify-end">
                  <CinematicToggle
                    on={cinematicMode}
                    onChange={setCinematic}
                    disabled={!hasGame(uiGame) || uiGame.players?.length !== 2}
                  />
                </div>
                <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-6 min-h-0">
                  <div className="flex flex-col gap-3 min-h-0">
                    <CorrectionBoard
                      game={uiGame}
                      onRefresh={refresh}
                      isLarge
                      boardDarts={animatingTurn ?? uiGame?.turn}
                      ocheCam={<OcheCam avatar={getAvatar(avatarMap[uiGame?.players?.[uiGame?.current]?.name])} animState={animState} />}
                    />
                  </div>
                  <div className="flex flex-col space-y-4 overflow-auto">
                    <Scoreboard game={uiGame} avatarMap={avatarMap} />
                    {hasGame(uiGame) && <GameControls onRefresh={refresh} onNewGame={() => setActiveTab('Settings')} />}
                    <div className="flex-1 min-h-[300px]">
                      <StreamPanel script="detect" label="detection"
                        hint="Click to popout"
                        extraButtons={<DebugSnapshot />}
                        allowPopout />
                    </div>
                  </div>
                </div>
              </div>
            )
          )}

          {activeTab === 'Align' && (
            <StreamPanel script="align" label="alignment" extraButtons={<AlignButtons />}
              hint="Auto-detect to fit the board, rotate handles so numbers line up, then Confirm each camera." />
          )}

          {activeTab === 'Cameras' && (
            <StreamPanel script="check" label="cameras"
              hint="Live feed + FPS for every USB camera." />
          )}

          {activeTab === 'Stats' && <Stats game={uiGame} />}
          {activeTab === 'Leaderboard' && <Leaderboard />}

          {activeTab === 'Settings' && (
            <div className="w-full">
              <div className="max-w-xl mx-auto px-8 pt-2 flex items-center justify-between gap-4">
                <div>
                  <div className="text-sm font-semibold text-white/80">Cinematic mode</div>
                  <div className="text-xs text-white/40">Broadcast-style live view (2-player games)</div>
                </div>
                <CinematicToggle on={cinematicMode} onChange={setCinematic} />
              </div>
              <GameSetup onStarted={(pMap) => { setAvatarMap(pMap); refresh(); setActiveTab('Live Track') }} />
            </div>
          )}
        </div>
      </main>

      {showDemo && demoScript && <CinematicDemo script={demoScript} onExit={() => setShowDemo(false)} />}
    </div>
  )
}

export default App
