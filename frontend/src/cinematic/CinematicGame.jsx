// Live cinematic broadcast view for a real 2-player X01 game.
// Unlike CinematicDemo (a canned scripted final), this is driven entirely by
// the live game state pushed over the WebSocket plus the shared throw-animation
// state from App. It reuses the broadcast presentational parts (walk-on cards,
// flanking caricatures, lower-third score panels) and the cin-* stylesheet.
import { useState, useEffect, useRef } from 'react'
import { X, Volume2, VolumeX, Star } from 'lucide-react'
import BroadcastBoard from './BroadcastBoard'
import { CSS, WalkOnCard, SideChar, Panel } from './broadcastParts'
import { sound } from './audio'
import { getAvatar } from '../config/avatars'
import { ThrowState } from '../config/timing'

// Player accent colours — left = cyan, right = rose, matching the demo.
const COLORS = ['#22d3ee', '#fb7185']
const DEFAULT_ACCESSORIES = ['darts', 'trophy', 'pint']
const ROTS = [-7, 6, 13] // slight per-dart tilt so the three darts don't overlap perfectly

// Map a live game player + chosen avatar into the broadcast `pl` shape.
function toCinPlayer(p, idx, avatarMap) {
  const av = getAvatar(avatarMap[p.name])
  return {
    name: p.name,
    nick: av.name,
    variant: av.variant,
    color: COLORS[idx] || COLORS[0],
    cardBg: av.bg,
    accessories: DEFAULT_ACCESSORIES,
    bio: p.darts > 0 ? `Average ${p.avg} · ${p.legs} legs won` : 'Stepping up to the oche',
  }
}

// Throw-animation phase → caricature pose for the player currently throwing.
function poseForState(animState) {
  switch (animState) {
    case ThrowState.AIMING: return 'aim'
    case ThrowState.THROWING:
    case ThrowState.DART_FLIGHT:
    case ThrowState.IMPACT: return 'throw'
    case ThrowState.CELEBRATING: return 'celebrate'
    default: return 'idle'
  }
}

export default function CinematicGame({ game, avatarMap = {}, animState, boardDarts, cameraSrc, onExit }) {
  const [muted, setMuted] = useState(!sound.enabled)
  const [phase, setPhase] = useState('match') // 'walkon' | 'match'
  const [walkonIdx, setWalkonIdx] = useState(0)
  const [bigCall, setBigCall] = useState(null)

  const seenSigRef = useRef(null)
  const walkTimers = useRef([])
  const prevSeqRef = useRef(game?.dart_seq ?? 0)
  const bigCallTimer = useRef(null)

  const players = game?.players ?? []
  const cinPlayers = players.map((p, i) => toCinPlayer(p, i, avatarMap))
  const activeIdx = game?.over ? -1 : (game?.current ?? 0)
  const winnerIdx = game?.over && game?.winner != null
    ? players.findIndex((p) => p.name === game.winner)
    : null

  // ── Walk-on intro: only for a freshly-started game ────────────────────────
  const sig = players.map((p) => p.name).join('|') + '@' + (game?.start_score ?? '')
  const isFresh = !!game && !game.over && (game.dart_seq ?? 0) === 0 &&
    players.every((p) => p.score === game.start_score)

  useEffect(() => {
    if (!game) return
    if (sig === seenSigRef.current) return
    seenSigRef.current = sig

    walkTimers.current.forEach(clearTimeout)
    walkTimers.current = []

    // Deferred (setTimeout 0) to avoid synchronous setState inside the effect body.
    if (isFresh && players.length === 2) {
      walkTimers.current.push(setTimeout(() => { setPhase('walkon'); setWalkonIdx(0) }, 0))
      walkTimers.current.push(setTimeout(() => setWalkonIdx(1), 2300))
      walkTimers.current.push(setTimeout(() => setPhase('match'), 4600))
    } else {
      walkTimers.current.push(setTimeout(() => setPhase('match'), 0))
    }
  }, [sig, isFresh, game, players.length])

  useEffect(() => () => walkTimers.current.forEach(clearTimeout), [])

  const skipIntro = () => {
    walkTimers.current.forEach(clearTimeout)
    walkTimers.current = []
    setPhase('match')
  }

  // ── Big-call overlay on visit completion (180 / game shot) ────────────────
  useEffect(() => {
    if (!game) return
    const seq = game.dart_seq ?? 0
    const prev = prevSeqRef.current
    prevSeqRef.current = seq
    if (seq <= prev) return // undo / reset / no change

    const disp = game.display_turn || []
    const visitOver = (game.turn?.length ?? 0) === 0 && disp.length > 0
    if (!visitOver) return

    const total = disp.reduce((s, d) => s + (d.points || 0), 0)
    const msg = game.message || ''
    let call = null
    if (game.over) call = { text: 'GAME SHOT', sub: 'AND THE MATCH' }
    else if (/wins the set/i.test(msg)) call = { text: 'GAME SHOT', sub: 'AND THE SET' }
    else if (/wins the leg/i.test(msg)) call = { text: 'GAME SHOT', sub: 'THE LEG' }
    else if (total === 180) call = { text: '180', sub: 'MAXIMUM' }
    else if (total >= 100) call = { text: String(total), sub: 'BIG SCORE' }

    if (call) {
      clearTimeout(bigCallTimer.current)
      // Deferred to avoid synchronous setState inside the effect body.
      setTimeout(() => setBigCall(call), 0)
      bigCallTimer.current = setTimeout(() => setBigCall(null), 2200)
    }
  }, [game])

  useEffect(() => () => clearTimeout(bigCallTimer.current), [])

  const toggleMute = () => {
    const next = !muted
    setMuted(next)
    sound.setEnabled(!next)
  }

  if (!game || players.length < 2) return null

  const activeColor = COLORS[Math.max(0, activeIdx)] || COLORS[0]
  const darts = (boardDarts || [])
    .filter((d) => d.pos)
    .map((d, i) => ({
      id: `d${i}-${Math.round(d.pos[0])}-${Math.round(d.pos[1])}`,
      x: d.pos[0],
      y: d.pos[1],
      rot: ROTS[i] ?? ((i * 13) % 19) - 9,
      color: activeColor,
    }))

  const visitDarts = (boardDarts || []).map((d) => ({ label: d.label }))
  const poses = cinPlayers.map((_, i) => {
    if (winnerIdx != null) return i === winnerIdx ? 'celebrate' : 'defeated'
    return i === activeIdx ? poseForState(animState) : 'idle'
  })

  const stat = (p) => ({ darts: p.darts, pts: (p.avg * p.darts) / 3 })

  return (
    <div className="relative w-full h-full overflow-hidden rounded-2xl text-white">
      <style>{CSS}</style>
      <div className="cin-bg" />
      <div className="cin-spot cin-spot-a" />
      <div className="cin-spot cin-spot-b" />

      {/* Top bar */}
      <div className="absolute top-0 inset-x-0 flex items-center justify-between px-6 py-4 z-50">
        <div className="flex items-center gap-3">
          <span className="cin-live">● LIVE</span>
          <span className="text-white/60 text-[11px] font-bold tracking-[0.3em] uppercase hidden sm:flex items-center gap-1.5">
            <Star className="w-3.5 h-3.5 text-amber-400" /> Cinematic mode
          </span>
        </div>
        <div className="flex items-center gap-2">
          {phase === 'walkon' && (
            <button onClick={skipIntro} className="cin-chipbtn">Skip intro</button>
          )}
          <button onClick={toggleMute} className="cin-chipbtn" title="Toggle sound">
            {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
          <button onClick={onExit} className="cin-chipbtn" title="Exit cinematic mode">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Walk-on intro */}
      {phase === 'walkon' && <WalkOnCard key={walkonIdx} pl={cinPlayers[walkonIdx]} />}

      {/* Match stage */}
      {phase === 'match' && (
        <div className="absolute inset-0 z-10 flex flex-col pt-14">
          <div className="flex-1 relative flex items-center justify-center min-h-0 py-2">
            <div className="cin-board-glow" />
            <div className="cin-zoom h-full max-h-[58vh] aspect-square">
              <BroadcastBoard darts={darts} />
            </div>
            <SideChar pl={cinPlayers[0]} pose={poses[0]} side="left" active={activeIdx === 0}
              defeated={winnerIdx != null && winnerIdx !== 0} />
            <SideChar pl={cinPlayers[1]} pose={poses[1]} side="right" active={activeIdx === 1}
              defeated={winnerIdx != null && winnerIdx !== 1} />

            {/* Live camera inset */}
            {cameraSrc && (
              <div className="absolute bottom-2 right-2 w-36 sm:w-44 aspect-video rounded-lg overflow-hidden border border-white/15 bg-black/60 shadow-2xl z-20">
                <img src={cameraSrc} alt="camera" className="w-full h-full object-cover" />
                <span className="absolute top-1 left-1 text-[8px] font-bold tracking-[0.2em] text-white/70 bg-black/50 px-1.5 py-0.5 rounded">CAM</span>
              </div>
            )}
          </div>

          {game.checkout && activeIdx >= 0 && (
            <div className="cin-hint self-center" style={{ borderColor: `${activeColor}99`, color: activeColor }}>
              CHECKOUT · {game.checkout}
            </div>
          )}

          <div className="flex gap-3 items-stretch px-5 pb-5 pt-3 z-30">
            <Panel pl={cinPlayers[0]} idx={0} score={players[0].score} stat={stat(players[0])}
              active={activeIdx === 0} visitDarts={activeIdx === 0 ? visitDarts : []} winnerIdx={winnerIdx} />
            <div className="hidden lg:flex flex-col items-center justify-center px-4 text-center shrink-0">
              <div className="text-2xl font-black text-white/85 tabular-nums">{game.start_score}</div>
              <div className="text-[9px] tracking-[0.3em] text-white/40 font-bold uppercase">
                {game.double_out ? 'Double out' : 'Straight out'}
              </div>
            </div>
            <Panel pl={cinPlayers[1]} idx={1} score={players[1].score} stat={stat(players[1])}
              active={activeIdx === 1} visitDarts={activeIdx === 1 ? visitDarts : []} winnerIdx={winnerIdx} />
          </div>
        </div>
      )}

      {/* Big calls */}
      {bigCall && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center pointer-events-none px-4">
          <div className="cin-flash" />
          <div className="cin-bigcall">{bigCall.text}</div>
          <div className="cin-bigcall-sub">{bigCall.sub}</div>
        </div>
      )}
    </div>
  )
}
