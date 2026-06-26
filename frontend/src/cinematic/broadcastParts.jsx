// Shared broadcast-style presentational pieces used by both the scripted
// CinematicDemo and the live CinematicGame view: the blister-pack walk-on
// card, the flanking match-side caricatures, the lower-third score panel,
// the confetti burst, and the full cin-* stylesheet.
import { useMemo, useRef, useState, useEffect } from 'react'
import { Trophy, RotateCcw, X } from 'lucide-react'
import Caricature, { Accessory } from '../art/Caricature'
import BroadcastBoard from './BroadcastBoard'
import { mmToPct } from './geometry'
import { THEME_CSS, winSceneFor } from './modeThemes'
import { sound } from './audio'

export const HEART = 'M12,21 C5,16 2,11 2,7.5 C2,4.5 4.5,2.5 7,2.5 C9,2.5 10.8,3.6 12,5.4 ' +
  'C13.2,3.6 15,2.5 17,2.5 C19.5,2.5 22,4.5 22,7.5 C22,11 19,16 12,21 Z'

// ── Walk-on: blister-pack player card ───────────────────────────────────────
export function WalkOnCard({ pl }) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center gap-10 px-6">
      {/* Entrance spotlight + strobe sweep behind the blister-pack card. */}
      <div className="cin-walkon-spot" style={{ '--glow': pl.color }} />
      <div className="cin-walkon-strobe" />
      <div className="cin-card" style={{ '--glow': pl.color }}>
        <div className="cin-card-tab" />
        <svg className="cin-card-heart" viewBox="0 0 24 24"><path d={HEART} fill={pl.color} /></svg>
        <div className="text-center pt-2 px-6">
          <div className="text-neutral-900 font-black text-3xl tracking-tight uppercase leading-none">{pl.name}</div>
          <div className="mt-1.5 text-neutral-500 font-bold text-xs tracking-[0.3em] uppercase">{pl.nick}</div>
        </div>
        <div className="flex gap-3 px-5 pb-4 pt-4 flex-1 min-h-0">
          <div className="cin-blister flex-1" style={{ background: pl.cardBg }}>
            <Caricature variant={pl.variant} pose="idle" shirt={pl.color} flight={pl.color} className="w-full h-full" />
            <div className="cin-blister-shine" />
          </div>
          <div className="flex flex-col gap-3 w-20 justify-center">
            {pl.accessories.map((a) => (
              <div key={a} className="cin-acc"><Accessory type={a} color={pl.color} /></div>
            ))}
          </div>
        </div>
        <div className="text-center pb-4 px-4 text-[10px] tracking-widest text-neutral-500 font-bold uppercase">{pl.bio}</div>
      </div>
      <div className="max-w-sm hidden md:block">
        <div className="text-xs font-bold tracking-[0.45em] uppercase mb-4 cin-rise" style={{ color: pl.color }}>★ Walk-on</div>
        <div className="text-6xl font-black uppercase leading-[0.95] cin-rise2">{pl.name}</div>
        <div className="text-2xl text-white/60 font-light mt-3 cin-rise3">“{pl.nick}”</div>
      </div>
    </div>
  )
}

// ── Match-side characters flanking the board ───────────────────────────────
export function SideChar({ pl, pose, side, active, defeated }) {
  const finalPose = defeated ? 'defeated' : pose
  // A defeated/eliminated player slumps and trudges off-frame toward the wings.
  const slumpCls = defeated ? `cin-slump ${side === 'left' ? 'cin-slump-left' : 'cin-slump-right'}` : ''
  const motionCls = finalPose === 'idle' ? 'cin-bob' : ''
  return (
    <div className={`cin-sidechar ${side === 'left' ? 'left-[2%]' : 'right-[2%]'} ${slumpCls}`}
      style={{
        opacity: active || finalPose !== 'idle' ? 1 : 0.55,
        filter: active ? `drop-shadow(0 0 26px ${pl.color}66)` : 'saturate(0.6)',
      }}>
      <div className={defeated ? 'cin-slump-inner' : motionCls}>
        <Caricature variant={pl.variant} pose={finalPose} shirt={pl.color} flight={pl.color}
          className="w-full" style={side === 'right' ? { transform: 'scaleX(-1)' } : {}} />
      </div>
      <div className="text-center mt-1">
        <span className="px-3 py-1 rounded-full text-[10px] font-bold tracking-[0.2em] uppercase"
          style={{ background: `${pl.color}22`, color: pl.color, border: `1px solid ${pl.color}55` }}>
          {pl.name}
        </span>
      </div>
    </div>
  )
}

// ── How-to-play card (shown after the walk-ons, before the match) ───────────
export function RulesCard({ rules, players = [], onStart, theme }) {
  const accent = theme?.accent || '#fbbf24'
  return (
    <div className={`absolute inset-0 z-20 flex items-center justify-center px-6 ${theme?.cls || ''}`}>
      <div className="cin-rules" style={{ boxShadow: `0 40px 120px rgba(0,0,0,.7), 0 0 90px ${accent}22` }}>
        {theme?.emblem && <div className="th-emblem">{theme.emblem}</div>}
        <div className="text-xs font-bold tracking-[0.45em] uppercase mb-2 cin-rise"
          style={{ color: accent }}>★ How to play</div>
        <div className="cin-rules-title cin-rise2">{rules.title}</div>
        <div className="text-lg text-white/55 font-light mb-6 cin-rise3">{rules.tagline}</div>
        <ul className="space-y-3 text-left max-w-xl mx-auto">
          {rules.lines.map((l, i) => (
            <li key={i} className="flex items-start gap-3 cin-rise3"
              style={{ animationDelay: `${0.4 + i * 0.12}s` }}>
              <span className="mt-1 w-5 h-5 rounded-full shrink-0 flex items-center justify-center text-[11px] font-black"
                style={{ background: `${accent}22`, color: accent, border: `1px solid ${accent}66` }}>{i + 1}</span>
              <span className="text-white/85 text-base leading-snug">{l}</span>
            </li>
          ))}
        </ul>
        {players.length > 0 && (
          <div className="mt-7 flex items-center justify-center gap-2 flex-wrap">
            {players.map((p, i) => (
              <span key={i} className="px-3 py-1 rounded-full text-[11px] font-bold tracking-[0.15em] uppercase"
                style={{ background: `${p.color}22`, color: p.color, border: `1px solid ${p.color}55` }}>
                {p.name}
              </span>
            ))}
          </div>
        )}
        <button onClick={onStart} className="cin-rules-go cin-rise3"
          style={{ animationDelay: '0.7s', background: `linear-gradient(180deg, ${accent}, ${accent}cc)`, boxShadow: `0 10px 30px ${accent}66` }}>
          Let’s play ▶
        </button>
      </div>
    </div>
  )
}

// ── Lower-third scoreboard ──────────────────────────────────────────────────
export function Panel({ pl, idx, score, stat, active, visitDarts, winnerIdx, mirror }) {
  const right = mirror ?? (idx === 1)
  const avg = stat.darts ? ((3 * stat.pts) / stat.darts).toFixed(1) : '—'
  const won = winnerIdx === idx
  return (
    <div className={`flex-1 flex items-center gap-4 rounded-2xl px-5 py-3 border backdrop-blur-md transition-all duration-300 ${right ? 'flex-row-reverse text-right' : ''}`}
      style={active || won
        ? { background: `${pl.color}14`, borderColor: `${pl.color}88`, boxShadow: `0 0 30px ${pl.color}33` }
        : { background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.1)' }}>
      <div className="w-12 h-12 rounded-full overflow-hidden border-2 shrink-0" style={{ borderColor: pl.color, background: pl.cardBg }}>
        <Caricature variant={pl.variant} pose={won ? 'celebrate' : 'idle'} framing="bust" shirt={pl.color} className="w-full h-full" />
      </div>
      <div className="min-w-0">
        <div className="font-extrabold tracking-wide uppercase text-sm truncate">
          {pl.name} {won && <Trophy className="inline w-4 h-4 text-amber-400 -mt-1" />}
        </div>
        <div className="text-[10px] text-white/45 tracking-[0.2em] uppercase">“{pl.nick}” · avg {avg}</div>
        <div className={`flex gap-1.5 mt-1.5 ${right ? 'justify-end' : ''}`}>
          {[0, 1, 2].map((i) => {
            const d = active ? visitDarts[i] : null
            const conf = d?.confidence
            const chipBorder = conf === 'low' ? '1px solid #f87171'
              : conf === 'provisional' ? '1px solid #fbbf24'
              : `1px solid ${pl.color}66`
            return (
              <span key={i} className="relative w-10 h-5 rounded text-[10px] font-bold flex items-center justify-center tabular-nums"
                style={d
                  ? { background: `${pl.color}2a`, color: d.label === 'MISS' ? '#f87171' : '#fff', border: chipBorder }
                  : { background: 'rgba(255,255,255,0.04)', border: '1px dashed rgba(255,255,255,0.15)', color: 'transparent' }}>
                {d ? d.label : '·'}
                {conf === 'provisional' && <span className="absolute -top-1 -right-1 w-1.5 h-1.5 rounded-full bg-amber-400" title="provisional" />}
                {conf === 'low' && <span className="absolute -top-1 -right-1 w-1.5 h-1.5 rounded-full bg-red-400" title="low confidence" />}
              </span>
            )
          })}
        </div>
      </div>
      <div className="ml-auto text-5xl font-black tabular-nums shrink-0"
        style={{ color: active || won ? pl.color : 'rgba(255,255,255,0.5)', ...(right ? { marginLeft: 0, marginRight: 'auto' } : {}) }}>
        {score}
      </div>
    </div>
  )
}

// ── Cricket marks scoreboard ────────────────────────────────────────────────
// Shows each target (20-15 + Bull) with per-player closing progress as three
// pips (filled = a mark, empty = still needed) so a player can see exactly how
// many more they need to close. A number goes grey/"dead" once every player has
// closed it — no more points are available on it. Points only ever go up when a
// closed number is hit while an opponent is still open.
const CRICKET_TARGETS = [20, 19, 18, 17, 16, 15, 25]

function MarkPips({ marks, color, dead }) {
  return (
    <span className="inline-flex gap-[3px] items-center">
      {[0, 1, 2].map((i) => (
        <span key={i} className="w-2 h-2 rounded-full"
          style={{
            background: i < marks ? (dead ? '#6b7280' : color) : 'transparent',
            border: `1.5px solid ${i < marks ? (dead ? '#6b7280' : color) : 'rgba(255,255,255,0.25)'}`,
          }} />
      ))}
    </span>
  )
}

export function CricketScoreboard({ game, players, activeIdx, winnerIdx }) {
  const gp = game.players || []
  const isDead = (t) => gp.every((p) => (p.state?.marks?.[String(t)] ?? 0) >= 3)
  return (
    <div className="mx-auto mb-4 w-full max-w-3xl rounded-2xl border border-white/10 bg-black/45 backdrop-blur-md px-4 py-3 z-30">
      <div className="grid items-center gap-x-3 gap-y-1.5"
        style={{ gridTemplateColumns: `auto repeat(${players.length}, minmax(0,1fr))` }}>
        {/* header: player names + points */}
        <div />
        {players.map((p, i) => (
          <div key={i} className="text-center min-w-0">
            <div className="font-extrabold uppercase tracking-wide text-xs truncate"
              style={{ color: i === activeIdx || i === winnerIdx ? p.color : 'rgba(255,255,255,0.6)' }}>
              {p.name} {i === winnerIdx && <Trophy className="inline w-3.5 h-3.5 text-amber-400 -mt-0.5" />}
            </div>
            <div className="text-lg font-black tabular-nums"
              style={{ color: i === activeIdx || i === winnerIdx ? p.color : 'rgba(255,255,255,0.5)' }}>
              {gp[i]?.score ?? 0}
            </div>
          </div>
        ))}
        {/* one row per target */}
        {CRICKET_TARGETS.map((t) => {
          const dead = isDead(t)
          return (
            <div key={t} className="contents">
              <div className={`text-right font-black tabular-nums text-sm pr-1 ${dead ? 'text-white/25 line-through' : 'text-white/80'}`}>
                {t === 25 ? 'Bull' : t}
              </div>
              {players.map((p, i) => {
                const m = gp[i]?.state?.marks?.[String(t)] ?? 0
                return (
                  <div key={i} className="flex justify-center">
                    <MarkPips marks={m} color={p.color} dead={dead} />
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Killer scoreboard ───────────────────────────────────────────────────────
// One card per player: assigned number, lives as heart pips, and an ARMED /
// OUT status so the elimination race is readable at a glance.
export function KillerScoreboard({ game, players, activeIdx, winnerIdx }) {
  const gp = game.players || []
  const maxLives = game.lives ?? Math.max(1, ...gp.map((p) => p.state?.lives ?? 1))
  // Track each player's previous `out` state in an effect so the elimination
  // card-shatter animation only fires on the frame a player transitions out
  // (not on every re-render while they stay out). `justOut` is a transient flag
  // set true on the transition and cleared after the animation plays.
  const prevOutRef = useRef(players.map((_, i) => !!gp[i]?.state?.out))
  const [justOut, setJustOut] = useState(() => players.map(() => false))
  const outSig = players.map((_, i) => (gp[i]?.state?.out ? '1' : '0')).join('')
  useEffect(() => {
    const prev = prevOutRef.current
    const next = players.map((_, i) => {
      const nowOut = !!gp[i]?.state?.out
      return nowOut && prev[i] === false   // strict false→true transition only
    })
    prevOutRef.current = players.map((_, i) => !!gp[i]?.state?.out)
    if (next.some(Boolean)) {
      setJustOut(next)
      const t = setTimeout(() => setJustOut(players.map(() => false)), 1500)
      return () => clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outSig])
  return (
    <div className="mx-auto mb-4 w-full max-w-4xl flex flex-wrap justify-center gap-3 px-4 z-30">
      {players.map((pl, i) => {
        const s = gp[i]?.state || {}
        const out = s.out
        const armed = s.killer
        const live = s.lives ?? 0
        const hot = i === activeIdx || i === winnerIdx
        return (
          <div key={i} className={`relative flex flex-col items-center gap-1 rounded-2xl px-4 py-2.5 border backdrop-blur-md transition-all min-w-[112px] ${out ? 'opacity-40 grayscale' : ''} ${justOut[i] ? 'cin-shatter' : ''}`}
            style={hot && !out
              ? { background: `${pl.color}16`, borderColor: `${pl.color}88`, boxShadow: `0 0 24px ${pl.color}33` }
              : { background: 'rgba(255,255,255,0.04)', borderColor: 'rgba(255,255,255,0.1)' }}>
            {justOut[i] && (
              <span className="cin-shatter-crack" aria-hidden="true">
                <svg viewBox="0 0 112 90" preserveAspectRatio="none" className="w-full h-full">
                  <path d="M0,42 L34,38 L48,52 L40,66 L66,58 L58,40 L82,46 L74,30 L112,38
                           M48,52 L52,90 M58,40 L60,0 M40,66 L20,90 M74,30 L88,0"
                    fill="none" stroke="#fca5a5" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
                </svg>
              </span>
            )}
            <div className="font-extrabold uppercase tracking-wide text-xs truncate max-w-[100px]"
              style={{ color: hot && !out ? pl.color : 'rgba(255,255,255,0.7)' }}>
              {pl.name} {i === winnerIdx && <Trophy className="inline w-3.5 h-3.5 text-amber-400 -mt-0.5" />}
            </div>
            <div className="text-3xl font-black tabular-nums leading-none"
              style={{ color: hot && !out ? pl.color : 'rgba(255,255,255,0.55)' }}>{s.number}</div>
            <div className="flex gap-1 mt-0.5">
              {Array.from({ length: maxLives }).map((_, k) => (
                <span key={k} className="text-sm leading-none" style={{ opacity: k < live ? 1 : 0.2 }}>
                  {k < live ? '❤️' : '🖤'}
                </span>
              ))}
            </div>
            <span className="mt-0.5 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-[0.15em] uppercase"
              style={out
                ? { background: 'rgba(239,68,68,0.18)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.4)' }
                : armed
                  ? { background: 'rgba(249,115,22,0.18)', color: '#fdba74', border: '1px solid rgba(249,115,22,0.5)' }
                  : { background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)', border: '1px solid rgba(255,255,255,0.12)' }}>
              {out ? 'Out' : armed ? '☠ Armed'
                : (game.arm_mode === 'marks' ? `Arm ${s.arm ?? 0}/3` : 'Unarmed')}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── Winner card (trophy + caricature + stat grid) ───────────────────────────
// Shared between the scripted demo finale and the live game-over moment. `stats`
// is an array of [label, value] pairs (already formatted by the caller, so the
// same card renders X01 averages or Killer survival numbers). `onReplay` and
// `onExit` wire the two action buttons; either may be omitted to hide it.
export function WinnerCard({ winner, crown = 'CHAMPION', accent, stats = [], onReplay, onExit, replayLabel = 'Winning dart', exitLabel = 'Exit show' }) {
  if (!winner) return null
  const col = accent || winner.color
  return (
    <div className="cin-winner">
      <Trophy className="w-10 h-10 text-amber-400 mx-auto" />
      <div className="text-[11px] tracking-[0.55em] text-amber-300/90 font-bold mt-2">{crown}</div>
      <div className="w-36 h-36 mx-auto my-5 rounded-full overflow-hidden border-4"
        style={{ borderColor: winner.color, background: winner.cardBg, boxShadow: `0 0 50px ${winner.color}55` }}>
        <Caricature variant={winner.variant} pose="celebrate" framing="bust" shirt={winner.color} className="w-full h-full" />
      </div>
      <div className="text-3xl font-black uppercase tracking-wide">{winner.name}</div>
      <div className="text-white/50 tracking-[0.3em] text-xs font-bold uppercase mt-1">“{winner.nick}”</div>

      {stats.length > 0 && (
        <div className="grid gap-2 mt-6" style={{ gridTemplateColumns: `repeat(${Math.min(stats.length, 4)}, minmax(0,1fr))` }}>
          {stats.map(([k, v]) => (
            <div key={k} className="rounded-xl bg-white/5 border border-white/10 py-3">
              <div className="text-xl font-black tabular-nums" style={{ color: col }}>{v}</div>
              <div className="text-[9px] tracking-[0.2em] text-white/40 font-bold mt-0.5">{k}</div>
            </div>
          ))}
        </div>
      )}

      {(onReplay || onExit) && (
        <div className="flex gap-2 mt-6">
          {onReplay && (
            <button onClick={onReplay} className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/15 text-sm font-bold tracking-wider uppercase transition-colors">
              <RotateCcw className="w-4 h-4" /> {replayLabel}
            </button>
          )}
          {onExit && (
            <button onClick={onExit} className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-bold tracking-wider uppercase transition-colors"
              style={{ background: `${col}22`, borderColor: `${col}77`, color: col }}>
              <X className="w-4 h-4" /> {exitLabel}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// ── WinScene: winning-dart slow-mo replay → winner card ──────────────────────
// The full win-moment finale, self-contained and theme-parameterised. Plays a
// zoom/slow-mo replay of the winning dart (if a board position is supplied),
// then reveals the WinnerCard. Used by both CinematicDemo and the live
// CinematicGame. It owns its own replay board overlay + zoom so it never has to
// mutate the caller's match board state.
//
// Props:
//   winner   – the broadcast `pl` shape for the champion
//   pos      – [x_mm, y_mm] of the winning dart, or null/undefined to skip the
//              replay and go straight to the card (graceful degrade)
//   rot      – dart tilt for the replay (default 6)
//   mode     – game mode key → pulls the per-mode winScene descriptor
//   theme    – mode theme (accent, confetti) for headline + colours
//   stats    – [label, value] pairs for the card grid
//   muteReplaySound – when true, the replay whoosh/thud SFX are suppressed (the
//                     live path leaves audio to the commentary agent)
//   onReplay – called when the card's replay button re-runs the scene
//   onExit   – card exit action
export function WinScene({ winner, pos, rot = 6, mode = 'X01', theme, stats = [],
  muteReplaySound = false, onExit }) {
  const desc = winSceneFor(mode)
  const accent = theme?.accent || winner?.color || '#fbbf24'
  const canReplay = !!(desc.replay && pos && pos.length === 2)

  // phase: 'replay' (zoom + slow-mo) → 'card'. With no position we open on 'card'.
  const [phase, setPhase] = useState(canReplay ? 'replay' : 'card')
  const [zoom, setZoom] = useState(null)
  const [showDart, setShowDart] = useState(false)
  const shakeRef = useRef(null)
  const timersRef = useRef([])

  const shake = () => {
    shakeRef.current?.animate?.([
      { transform: 'translate(0,0)' }, { transform: 'translate(4px,-3px)' },
      { transform: 'translate(-3px,2px)' }, { transform: 'translate(2px,-1.5px)' },
      { transform: 'translate(0,0)' },
    ], { duration: 380, easing: 'ease-out' })
  }

  const runReplay = () => {
    timersRef.current.forEach(clearTimeout)
    timersRef.current = []
    if (!canReplay) { setPhase('card'); return }
    const T = (fn, ms) => timersRef.current.push(setTimeout(fn, ms))
    setPhase('replay')
    setShowDart(false)
    const [ox, oy] = mmToPct(pos)
    setZoom({ transform: 'scale(2.05)', transformOrigin: `${ox}% ${oy}%` })
    T(() => { if (!muteReplaySound) sound.whoosh?.(); setShowDart(true) }, 950)
    T(() => { if (!muteReplaySound) sound.thud?.(); shake() }, 1850)
    T(() => setZoom(null), 3150)
    T(() => setPhase('card'), 3950)
  }

  // Kick off the replay once on mount (or skip straight to the card). Deferred
  // (setTimeout 0) so the initial setState lands outside the effect body.
  useEffect(() => {
    if (canReplay) {
      const t = setTimeout(runReplay, 0)
      timersRef.current.push(t)
    }
    return () => timersRef.current.forEach(clearTimeout)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const replayDart = showDart && pos
    ? [{ id: 'win', x: pos[0], y: pos[1], color: winner?.color, rot, slow: true, win: true }]
    : []

  return (
    <>
      {phase === 'replay' && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="cin-zoom h-full max-h-[58vh] aspect-square" style={zoom || {}}>
            <div ref={shakeRef} className="w-full h-full">
              <BroadcastBoard darts={replayDart} />
            </div>
          </div>
          <div className="cin-replay-badge">● REPLAY</div>
          <div className="cin-winscene-headline">{desc.headline}</div>
        </div>
      )}
      {phase === 'card' && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-sm px-4">
          <WinnerCard winner={winner} crown={desc.crown} accent={accent} stats={stats}
            onReplay={canReplay ? runReplay : undefined} onExit={onExit} />
        </div>
      )}
    </>
  )
}

// ── Confetti burst ──────────────────────────────────────────────────────────
export function Confetti({ colors: palette } = {}) {
  const pieces = useMemo(() => {
    // Pure index-based hash keeps this render-pure (and the burst identical each run).
    const rnd = (i, salt) => {
      const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453
      return x - Math.floor(x)
    }
    const colors = palette && palette.length
      ? palette
      : ['#fbbf24', '#fb7185', '#22d3ee', '#a78bfa', '#34d399', '#f8fafc']
    return Array.from({ length: 130 }, (_, i) => ({
      left: rnd(i, 1) * 100,
      delay: rnd(i, 2) * 2.5,
      dur: 2.8 + rnd(i, 3) * 2.4,
      w: 5 + rnd(i, 4) * 7,
      h: 8 + rnd(i, 5) * 8,
      sway: `${rnd(i, 6) * 160 - 80}px`,
      color: colors[i % colors.length],
    }))
  }, [palette])
  return (
    <div className="cin-confetti">
      {pieces.map((p, i) => (
        <i key={i} style={{
          left: `${p.left}%`, width: p.w, height: p.h, background: p.color,
          animationDuration: `${p.dur}s`, animationDelay: `${p.delay}s`, '--sway': p.sway,
        }} />
      ))}
    </div>
  )
}

// ── Full broadcast stylesheet (shared by demo + live cinematic game) ─────────
export const CSS = `
/* Arena backdrop is venue-skinnable: a venue sets --cin-bg-1/2/3 (gradient
   stops) and --cin-spot-a/b (the two roving spotlight tints) on the cinematic
   root. Fallbacks keep the default deep-blue stage if no venue is applied. */
.cin-bg { position:absolute; inset:0; background:
  radial-gradient(120% 90% at 50% -10%,
    var(--cin-bg-1, #222b4d) 0%,
    var(--cin-bg-2, #0a0d18) 55%,
    var(--cin-bg-3, #04050a) 100%); }
.cin-spot { position:absolute; width:160vmax; height:160vmax; left:50%; top:-80vmax;
  margin-left:-80vmax; mix-blend-mode:screen; pointer-events:none; }
.cin-spot-a { background: conic-gradient(from 175deg at 50% 50%,
  transparent 0deg, var(--cin-spot-a, rgba(125,170,255,0.10)) 4deg, transparent 9deg,
  transparent 22deg, var(--cin-spot-b, rgba(255,130,180,0.08)) 26deg, transparent 31deg);
  animation: cin-sweep 11s ease-in-out infinite alternate; }
.cin-spot-b { background: conic-gradient(from 168deg at 50% 50%,
  transparent 0deg, var(--cin-spot-c, rgba(160,255,220,0.06)) 5deg, transparent 11deg);
  animation: cin-sweep 13s ease-in-out -4s infinite alternate-reverse; }
@keyframes cin-sweep { from { transform: rotate(-16deg); } to { transform: rotate(16deg); } }

.cin-live { color:#f87171; font-weight:800; font-size:10px; letter-spacing:.2em;
  background:rgba(248,113,113,.12); border:1px solid rgba(248,113,113,.4);
  padding:4px 10px; border-radius:999px; animation: cin-blink 1.6s infinite; }
@keyframes cin-blink { 50% { opacity:.5; } }

.cin-chipbtn { display:flex; align-items:center; gap:6px; padding:7px 12px;
  border-radius:10px; background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.14);
  color:rgba(255,255,255,.75); font-size:11px; font-weight:700; letter-spacing:.12em;
  text-transform:uppercase; cursor:pointer; transition:background .2s; }
.cin-chipbtn:hover { background:rgba(255,255,255,.14); color:#fff; }

.cin-title-text { font-size:clamp(48px, 9vw, 116px); line-height:.95; font-weight:900;
  background:linear-gradient(100deg, #fff 20%, #8be3ff 40%, #fff 60%, #ff9ad5 80%);
  background-size:200% 100%; -webkit-background-clip:text; background-clip:text; color:transparent;
  animation: cin-shine 3.5s linear infinite, cin-pop-in .8s cubic-bezier(.2,1.4,.3,1) both; }
@keyframes cin-shine { to { background-position:200% 0; } }
@keyframes cin-pop-in { 0% { opacity:0; transform:scale(.82) translateY(30px); } 100% { opacity:1; transform:none; } }
.cin-rise  { animation: cin-up .7s .05s both ease-out; }
.cin-rise2 { animation: cin-up .7s .3s both ease-out; }
.cin-rise3 { animation: cin-up .7s .55s both ease-out; }
@keyframes cin-up { from { opacity:0; transform:translateY(26px); } to { opacity:1; transform:translateY(0); } }

.cin-card { width:min(340px, 80vw); height:min(560px, 78vh); background:#eadfc6; border-radius:22px;
  position:relative; display:flex; flex-direction:column;
  box-shadow: 0 30px 90px rgba(0,0,0,.65), 0 0 80px var(--glow, transparent);
  animation: cin-card-in 1s cubic-bezier(.2,1.3,.3,1) both, cin-card-float 4.5s 1s ease-in-out infinite alternate; }
@keyframes cin-card-in { 0% { opacity:0; transform:perspective(900px) rotateY(42deg) translateY(70px) scale(.82); }
  100% { opacity:1; transform:perspective(900px) rotateY(-4deg); } }
@keyframes cin-card-float { from { transform:perspective(900px) rotateY(-4deg) translateY(0); }
  to { transform:perspective(900px) rotateY(6deg) translateY(-8px); } }
.cin-walkon-spot { position:absolute; inset:0; pointer-events:none; z-index:0;
  background:
    radial-gradient(60% 80% at 50% 120%, var(--glow, #fff) 0%, transparent 60%),
    conic-gradient(from 270deg at 50% 110%, transparent 64deg,
      rgba(255,255,255,.16) 84deg, transparent 96deg,
      transparent 264deg, rgba(255,255,255,.16) 276deg, transparent 288deg);
  opacity:.35; mix-blend-mode:screen;
  animation: cin-walkon-spot-in .8s ease-out both, cin-walkon-spot-sway 4.5s 0.8s ease-in-out infinite alternate; }
@keyframes cin-walkon-spot-in { from { opacity:0; } to { opacity:.35; } }
@keyframes cin-walkon-spot-sway { from { transform:rotate(-5deg); } to { transform:rotate(5deg); } }
.cin-walkon-strobe { position:absolute; inset:0; pointer-events:none; z-index:1;
  background:linear-gradient(105deg, transparent 40%, rgba(255,255,255,.22) 50%, transparent 60%);
  mix-blend-mode:screen; animation: cin-walkon-strobe 2.6s ease-in-out infinite; }
@keyframes cin-walkon-strobe { 0% { transform:translateX(-120%); } 55%,100% { transform:translateX(120%); } }
.cin-card-tab { width:64px; height:16px; background:#d9cdb0; border-radius:0 0 12px 12px;
  margin:0 auto 6px; box-shadow:inset 0 -2px 4px rgba(0,0,0,.15); }
.cin-card-tab::after { content:''; display:block; width:26px; height:7px; border-radius:999px;
  background:#0a0d18; margin:4px auto 0; }
.cin-card-heart { position:absolute; top:14px; right:16px; width:26px; height:26px; }
.cin-blister { border-radius:18px; position:relative; overflow:hidden; padding:10px;
  box-shadow: inset 0 0 0 4px rgba(255,255,255,.55), inset 0 12px 34px rgba(255,255,255,.35), 0 4px 12px rgba(0,0,0,.18); }
.cin-blister-shine { position:absolute; inset:0; pointer-events:none;
  background:linear-gradient(115deg, transparent 32%, rgba(255,255,255,.5) 46%, transparent 60%);
  animation: cin-sheen 2.8s ease-in-out infinite; }
@keyframes cin-sheen { 0% { transform:translateX(-130%); } 55%, 100% { transform:translateX(130%); } }
.cin-acc { background:#f6efdd; border-radius:12px; padding:5px; aspect-ratio:1;
  box-shadow: inset 0 0 0 3px rgba(255,255,255,.6), 0 2px 6px rgba(0,0,0,.12); }

.cin-board-glow { position:absolute; width:62vmin; height:62vmin; border-radius:50%;
  background:radial-gradient(circle, rgba(110,160,255,.16), transparent 65%); filter:blur(10px); }
.cin-zoom { transition: transform .95s cubic-bezier(.5,0,.2,1); will-change: transform;
  filter: drop-shadow(0 26px 60px rgba(0,0,0,.7)); }

.cin-sidechar { position:absolute; bottom:0; width:clamp(100px, 12vw, 180px);
  transition: opacity .4s, filter .4s; z-index:5; }
.cin-bob { animation: cin-bob 2.6s ease-in-out infinite; }
@keyframes cin-bob { 0%, 100% { transform:translateY(0); } 50% { transform:translateY(-6px); } }

.cin-replay-badge { position:absolute; top:16%; left:50%; transform:translateX(-50%);
  padding:7px 18px; border-radius:999px; background:rgba(220,38,38,.85); color:#fff;
  font-weight:800; font-size:12px; letter-spacing:.3em; animation: cin-blink 1s infinite; z-index:20; }
.cin-winscene-headline { position:absolute; bottom:9%; left:50%; transform:translateX(-50%);
  font-weight:900; font-size:clamp(20px, 4vw, 48px); letter-spacing:.12em; text-align:center;
  white-space:nowrap; color:#fff; text-shadow:0 6px 30px rgba(0,0,0,.7);
  animation: cin-up .5s .3s both; z-index:21; }
.cin-banner { position:absolute; bottom:5%; left:50%; transform:translateX(-50%);
  padding:10px 28px; border-radius:999px; background:rgba(8,10,18,.82); backdrop-filter:blur(8px);
  border:1px solid rgba(255,255,255,.18); font-weight:800; letter-spacing:.28em; font-size:13px;
  white-space:nowrap; animation: cin-up .45s both; z-index:20; }
.cin-drama { position:absolute; top:13%; left:50%;
  font-size:clamp(22px, 3.4vw, 42px); font-weight:900; font-style:italic; color:#fca5a5;
  text-shadow:0 4px 26px rgba(248,113,113,.55); letter-spacing:.05em; white-space:nowrap;
  animation: cin-drama-in .5s cubic-bezier(.2,1.4,.3,1) both; z-index:20; }
@keyframes cin-drama-in { 0% { opacity:0; transform:translateX(-50%) scale(2.4); }
  100% { opacity:1; transform:translateX(-50%) scale(1); } }

.cin-hint { margin-bottom:6px; padding:8px 24px; border-radius:12px; border:1px solid;
  background:rgba(10,12,20,.78); font-weight:800; letter-spacing:.18em; font-size:12px;
  animation: cin-up .4s both; z-index:30; }

.cin-bigcall { font-size:clamp(80px, 17vw, 210px); font-weight:900; line-height:.9; text-align:center;
  background:linear-gradient(180deg, #fff7d6, #ffd75e 45%, #f59e0b);
  -webkit-background-clip:text; background-clip:text; color:transparent;
  filter:drop-shadow(0 10px 44px rgba(245,158,11,.45));
  animation: cin-call-in .55s cubic-bezier(.2,1.5,.3,1) both; }
.cin-bigcall-sub { margin-top:10px; font-weight:800; letter-spacing:.42em; text-align:center;
  color:rgba(255,255,255,.88); font-size:clamp(12px, 1.6vw, 20px); animation: cin-up .5s .15s both; }
@keyframes cin-call-in { 0% { opacity:0; transform:scale(2.6); } 60% { opacity:1; transform:scale(.96); }
  100% { transform:scale(1); } }
.cin-flash { position:absolute; inset:0; background:#fff; animation: cin-flash-out .6s ease-out both; }
@keyframes cin-flash-out { 0% { opacity:.6; } 100% { opacity:0; } }

.cin-confetti { position:absolute; inset:0; overflow:hidden; pointer-events:none; z-index:45; }
.cin-confetti i { position:absolute; top:-6vh; border-radius:2px; opacity:.95;
  animation-name: cin-fall; animation-timing-function: linear; animation-iteration-count: infinite; }
@keyframes cin-fall { 0% { transform:translateY(-6vh) rotate(0) translateX(0); }
  100% { transform:translateY(115vh) rotate(680deg) translateX(var(--sway, 0px)); } }

.cin-rules { width:min(680px, 92vw); border-radius:26px; padding:34px 36px 30px; text-align:center;
  background:linear-gradient(180deg, rgba(18,21,31,.96), rgba(10,12,18,.96));
  border:1px solid rgba(255,255,255,.12);
  box-shadow: 0 40px 120px rgba(0,0,0,.7), 0 0 90px rgba(125,170,255,.12);
  animation: cin-pop-in .6s cubic-bezier(.2,1.4,.3,1) both; }
.cin-rules-title { font-size:clamp(40px, 7vw, 76px); line-height:.95; font-weight:900;
  background:linear-gradient(100deg, #fff 20%, #8be3ff 45%, #fff 60%, #ff9ad5 82%);
  background-size:200% 100%; -webkit-background-clip:text; background-clip:text; color:transparent;
  animation: cin-shine 3.5s linear infinite; }
.cin-rules-go { margin-top:26px; padding:13px 40px; border-radius:14px; cursor:pointer;
  font-weight:800; letter-spacing:.18em; text-transform:uppercase; font-size:15px; color:#06121a;
  background:linear-gradient(180deg, #7ff0ff, #22d3ee); border:none;
  box-shadow: 0 10px 30px rgba(34,211,238,.4); transition: transform .15s, box-shadow .15s; }
.cin-rules-go:hover { transform:translateY(-2px); box-shadow: 0 16px 40px rgba(34,211,238,.55); }
.cin-rules-go:active { transform:translateY(0); }

.cin-winner { width:min(460px, 94vw); border-radius:28px; padding:30px 28px 26px; text-align:center;
  background:linear-gradient(180deg, #12151f, #0a0c12); border:1px solid rgba(255,255,255,.12);
  box-shadow: 0 40px 120px rgba(0,0,0,.7), 0 0 90px rgba(245,158,11,.12);
  animation: cin-pop-in .6s cubic-bezier(.2,1.4,.3,1) both; }

/* ── Losing / elimination: SideChar slump + trudge off-frame ──────────────── */
/* The defeated pose (sagging shoulders) is the static beat; on top we settle
   the whole figure down, dim it, and shuffle it toward the wings. The inner
   wrapper adds a slow body-sag bob so it never looks frozen. */
.cin-slump { animation: cin-slump-settle 1.1s ease-out both; }
.cin-slump-left  { animation: cin-slump-settle 1.1s ease-out both, cin-trudge-left  6s 1.1s ease-in-out infinite; }
.cin-slump-right { animation: cin-slump-settle 1.1s ease-out both, cin-trudge-right 6s 1.1s ease-in-out infinite; }
.cin-slump-inner { animation: cin-slump-sag 3.4s 1.1s ease-in-out infinite; transform-origin: 50% 100%; }
@keyframes cin-slump-settle {
  0%   { transform: translateY(0) scale(1); }
  100% { transform: translateY(14px) scale(.94); opacity:.85; } }
@keyframes cin-slump-sag {
  0%,100% { transform: translateY(0) rotate(0); }
  50%     { transform: translateY(5px) rotate(-1.5deg); } }
/* Slow shuffle off toward each wing, then a tiny dejected bob back — never fully
   leaves so the panel/label stay readable. */
@keyframes cin-trudge-left {
  0%   { transform: translateY(14px) scale(.94) translateX(0); }
  60%  { transform: translateY(14px) scale(.94) translateX(-26%); }
  100% { transform: translateY(14px) scale(.94) translateX(-18%); } }
@keyframes cin-trudge-right {
  0%   { transform: translateY(14px) scale(.94) translateX(0); }
  60%  { transform: translateY(14px) scale(.94) translateX(26%); }
  100% { transform: translateY(14px) scale(.94) translateX(18%); } }

/* ── Killer elimination: card shatter / crack-and-grey ────────────────────── */
/* Fired once on the false-to-true out transition of a Killer row. A sharp shake
   + flash, the row greys out (its base classes already drop opacity/grayscale),
   and a crack overlay draws across it. */
.cin-shatter { animation: cin-shatter-shake .6s cubic-bezier(.36,.07,.19,.97) both; }
@keyframes cin-shatter-shake {
  0%   { transform: translateX(0) rotate(0); box-shadow: 0 0 0 0 rgba(239,68,68,.0); }
  10%  { transform: translateX(-6px) rotate(-2deg); box-shadow: 0 0 30px 4px rgba(239,68,68,.55); }
  25%  { transform: translateX(7px) rotate(2.5deg); }
  40%  { transform: translateX(-5px) rotate(-1.5deg); }
  55%  { transform: translateX(4px) rotate(1deg); }
  70%  { transform: translateX(-2px) rotate(-.5deg); }
  100% { transform: translateX(0) rotate(0); box-shadow: 0 0 0 0 rgba(239,68,68,0); } }
.cin-shatter-crack { position:absolute; inset:0; pointer-events:none; z-index:2;
  border-radius:16px; overflow:hidden; opacity:0;
  animation: cin-crack-draw 1.4s ease-out forwards; }
.cin-shatter-crack path { stroke-dasharray: 360; stroke-dashoffset: 360;
  animation: cin-crack-stroke 1s .15s ease-out forwards; }
@keyframes cin-crack-draw { 0%{ opacity:0; } 12%{ opacity:1; } 70%{ opacity:1; } 100%{ opacity:.45; } }
@keyframes cin-crack-stroke { to { stroke-dashoffset: 0; } }

/* ── Crowd silhouettes ────────────────────────────────────────────────────── */
/* A darkened band of heads behind the stage. A constant gentle sway idles; the
   .cin-crowd-react modifier bounces/roars on big moments. */
.cin-crowd { position:absolute; left:0; right:0; bottom:0; height:clamp(64px, 14vh, 150px);
  pointer-events:none; z-index:2; overflow:hidden;
  -webkit-mask-image: linear-gradient(to top, #000 60%, transparent);
  mask-image: linear-gradient(to top, #000 60%, transparent); }
.cin-crowd svg { width:100%; height:100%; display:block; }
.cin-crowd-sway { transform-origin: 50% 100%; animation: cin-crowd-sway 5.5s ease-in-out infinite; }
@keyframes cin-crowd-sway {
  0%,100% { transform: translateX(0) skewX(0deg); }
  50%     { transform: translateX(1.4%) skewX(-.6deg); } }
.cin-crowd-react .cin-crowd-sway { animation: cin-crowd-roar 1.1s ease-out; }
@keyframes cin-crowd-roar {
  0%   { transform: translateY(0) scaleY(1); }
  18%  { transform: translateY(-9px) scaleY(1.06); }
  40%  { transform: translateY(-3px) scaleY(1.02); }
  62%  { transform: translateY(-6px) scaleY(1.04); }
  100% { transform: translateY(0) scaleY(1); } }
` + THEME_CSS
