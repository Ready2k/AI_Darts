// The Cinematic Demo: a full-screen, broadcast-style scripted darts final.
// Title card → blister-pack walk-ons → live match with caller audio, 180s,
// missed-double drama → game shot, confetti, slow-mo replay → winner card.
// Self-contained: pure SVG/CSS visuals, WebAudio + SpeechSynthesis sound.
import { useState, useEffect, useRef, useMemo } from 'react'
import { X, Volume2, VolumeX, Trophy, RotateCcw, FastForward } from 'lucide-react'
import BroadcastBoard from './BroadcastBoard'
import { mmToPct } from './geometry'
import { SCRIPTS } from './scripts'
import { sound } from './audio'
import Caricature, { Accessory } from '../art/Caricature'

const CANCEL = Symbol('cancelled')

const HEART = 'M12,21 C5,16 2,11 2,7.5 C2,4.5 4.5,2.5 7,2.5 C9,2.5 10.8,3.6 12,5.4 ' +
  'C13.2,3.6 15,2.5 17,2.5 C19.5,2.5 22,4.5 22,7.5 C22,11 19,16 12,21 Z'

// ── Walk-on: blister-pack player card ───────────────────────────────────────
function WalkOnCard({ pl }) {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center gap-10 px-6">
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
function SideChar({ pl, pose, side, active, defeated }) {
  const finalPose = defeated ? 'defeated' : pose
  return (
    <div className={`cin-sidechar ${side === 'left' ? 'left-[2%]' : 'right-[2%]'}`}
      style={{
        opacity: active || finalPose !== 'idle' ? 1 : 0.55,
        filter: active ? `drop-shadow(0 0 26px ${pl.color}66)` : 'saturate(0.6)',
      }}>
      <div className={finalPose === 'idle' ? 'cin-bob' : ''}>
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

// ── Lower-third scoreboard ──────────────────────────────────────────────────
function Panel({ pl, idx, score, stat, active, visitDarts, winnerIdx }) {
  const right = idx === 1
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
            return (
              <span key={i} className="w-10 h-5 rounded text-[10px] font-bold flex items-center justify-center tabular-nums"
                style={d
                  ? { background: `${pl.color}2a`, color: d.label === 'MISS' ? '#f87171' : '#fff', border: `1px solid ${pl.color}66` }
                  : { background: 'rgba(255,255,255,0.04)', border: '1px dashed rgba(255,255,255,0.15)', color: 'transparent' }}>
                {d ? d.label : '·'}
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

function Confetti() {
  const pieces = useMemo(() => {
    // Pure index-based hash keeps this render-pure (and the burst identical each run).
    const rnd = (i, salt) => {
      const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453
      return x - Math.floor(x)
    }
    const colors = ['#fbbf24', '#fb7185', '#22d3ee', '#a78bfa', '#34d399', '#f8fafc']
    return Array.from({ length: 130 }, (_, i) => ({
      left: rnd(i, 1) * 100,
      delay: rnd(i, 2) * 2.5,
      dur: 2.8 + rnd(i, 3) * 2.4,
      w: 5 + rnd(i, 4) * 7,
      h: 8 + rnd(i, 5) * 8,
      sway: `${rnd(i, 6) * 160 - 80}px`,
      color: colors[i % colors.length],
    }))
  }, [])
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

// ── The show ────────────────────────────────────────────────────────────────
export default function CinematicDemo({ onExit, script = SCRIPTS[0] }) {
  const { MATCH, PLAYERS, VISITS, matchStats } = script
  const [phase, setPhase] = useState('title') // title | walkon | match | winner
  const [walkonIdx, setWalkonIdx] = useState(0)
  const [scores, setScores] = useState([MATCH.startScore, MATCH.startScore])
  const [stats, setStats] = useState([{ pts: 0, darts: 0 }, { pts: 0, darts: 0 }])
  const [activeP, setActiveP] = useState(0)
  const [visitDarts, setVisitDarts] = useState([])
  const [boardDarts, setBoardDarts] = useState([])
  const [pops, setPops] = useState([])
  const [poses, setPoses] = useState(['idle', 'idle'])
  const [bigCall, setBigCall] = useState(null)
  const [drama, setDrama] = useState(null)
  const [hint, setHint] = useState(null)
  const [banner, setBanner] = useState(null)
  const [confetti, setConfetti] = useState(false)
  const [zoom, setZoom] = useState(null)
  const [replaying, setReplaying] = useState(false)
  const [winnerIdx, setWinnerIdx] = useState(null)
  const [muted, setMuted] = useState(!sound.enabled)

  const tokenRef = useRef(null)
  const skipRef = useRef(null)
  const shakeRef = useRef(null)
  const idRef = useRef(0)
  const replayDartRef = useRef(null)
  const busyRef = useRef(false)

  const makeW = (token) => (ms) =>
    new Promise((res, rej) => setTimeout(() => (token.cancelled ? rej(CANCEL) : res()), ms))

  const setPose = (i, pose) =>
    setPoses((prev) => { const n = [...prev]; n[i] = pose; return n })

  const shake = (mag = 1) => {
    shakeRef.current?.animate?.([
      { transform: 'translate(0,0)' },
      { transform: `translate(${4 * mag}px, ${-3 * mag}px)` },
      { transform: `translate(${-3 * mag}px, ${2 * mag}px)` },
      { transform: `translate(${2 * mag}px, ${-1.5 * mag}px)` },
      { transform: 'translate(0,0)' },
    ], { duration: 380, easing: 'ease-out' })
  }

  const runReplay = async (token) => {
    const W = makeW(token)
    const rd = replayDartRef.current
    if (!rd) return
    setReplaying(true)
    setBoardDarts((p) => p.filter((b) => b.id !== rd.id))
    const [ox, oy] = mmToPct(rd.pos)
    setZoom({ transform: 'scale(2.05)', transformOrigin: `${ox}% ${oy}%` })
    await W(950)
    sound.whoosh()
    const id = ++idRef.current
    replayDartRef.current = { ...rd, id }
    setBoardDarts((p) => [...p, { id, x: rd.pos[0], y: rd.pos[1], color: rd.color, rot: rd.rot, slow: true, win: true }])
    await W(900)
    sound.thud()
    shake(1)
    await W(1300)
    setZoom(null)
    await W(800)
    setReplaying(false)
  }

  useEffect(() => {
    const token = { cancelled: false }
    tokenRef.current = token
    const W = makeW(token)

    const throwOne = async (d, p, pl, scores_, stats_) => {
      setPose(p, 'aim')
      await W(700)
      setPose(p, 'throw')
      sound.whoosh()
      await W(180)
      const id = ++idRef.current
      setBoardDarts((prev) => [...prev, { id, x: d.pos[0], y: d.pos[1], color: pl.color, rot: d.rot, win: d.win }])
      if (d.win) replayDartRef.current = { id, pos: d.pos, rot: d.rot, color: pl.color }
      await W(340)
      sound.thud()
      shake(d.miss ? 0.6 : d.score >= 50 ? 1.5 : 1)
      setPops((prev) => [...prev, {
        id, x: d.pos[0], y: d.pos[1],
        text: d.miss ? 'NO SCORE' : d.label,
        color: d.miss ? '#f87171' : '#ffffff',
      }])
      scores_[p] -= d.score
      stats_[p].pts += d.score
      stats_[p].darts += 1
      setScores([...scores_])
      setStats(stats_.map((s) => ({ ...s })))
      setVisitDarts((prev) => [...prev, { label: d.miss ? 'MISS' : d.label }])
      await W(500)
      setPose(p, 'idle')
      if (d.drama) {
        setDrama(d.drama)
        await W(1500)
        setDrama(null)
      } else {
        await W(280)
      }
    }

    const show = async () => {
      // ── Intro (skippable) ──
      let skipped = false
      const skipP = new Promise((res) => { skipRef.current = () => { skipped = true; res() } })
      const WS = (ms) => Promise.race([W(ms), skipP])

      setPhase('title')
      sound.say(`Welcome... to the ${MATCH.title}!`, { rate: 1.0, pitch: 1.0 })
      await WS(4400)
      for (let i = 0; i < PLAYERS.length && !skipped; i++) {
        setWalkonIdx(i)
        setPhase('walkon')
        sound.stop()
        sound.cheer(false)
        sound.say(PLAYERS[i].announce, { rate: 1.02, pitch: 1.05 })
        await WS(5600)
      }
      skipRef.current = null
      sound.stop()

      // ── Game on ──
      setPhase('match')
      setBigCall({ text: 'GAME ON!', sub: MATCH.subtitle })
      sound.say('Game... on!', { rate: 0.88 })
      sound.cheer(false)
      await W(2400)
      setBigCall(null)

      const scores_ = [MATCH.startScore, MATCH.startScore]
      const stats_ = [{ pts: 0, darts: 0 }, { pts: 0, darts: 0 }]

      for (const visit of VISITS) {
        const p = visit.p
        const pl = PLAYERS[p]
        setActiveP(p)
        setVisitDarts([])
        setHint(visit.hint || null)
        setBanner(`${pl.name.toUpperCase()} TO THROW`)
        if (visit.requireCall) sound.say(visit.requireCall, { rate: 0.96 })
        await W(visit.requireCall ? 2800 : 1500)
        setBanner(null)

        for (const d of visit.darts) {
          await throwOne(d, p, pl, scores_, stats_)
        }
        setHint(null)

        await W(350)
        if (visit.gameShot) {
          // ── Finale ──
          sound.cheer(true)
          sound.say(visit.call, { rate: 0.88, pitch: 1.0 })
          setBigCall({ text: 'GAME SHOT!', sub: `${pl.name.toUpperCase()} IS THE CHAMPION` })
          setConfetti(true)
          setPose(p, 'celebrate')
          setWinnerIdx(p)
          await W(3600)
          setBigCall(null)
          setHint(null)
          await runReplay(token)
          setPhase('winner')
          return
        }
        if (visit.big) {
          sound.cheer(true)
          shake(2)
          setBigCall({ text: '180', sub: 'ONE HUNDRED AND EIGHTY!' })
          sound.say(visit.call, { rate: 0.82, pitch: 1.05 })
          setPose(p, 'celebrate')
          await W(2800)
          setBigCall(null)
          setPose(p, 'idle')
        } else {
          sound.say(visit.call, { rate: 0.98 })
          if (visit.total >= 100) sound.cheer(false)
          await W(1600)
        }

        setBoardDarts([])
        setPops([])
        setHint(null)
        await W(450)
      }
    }

    show().catch((e) => { if (e !== CANCEL) throw e })
    return () => {
      token.cancelled = true
      sound.stop()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const winner = winnerIdx != null ? PLAYERS[winnerIdx] : null
  const finalStats = useMemo(() => matchStats(), [])
  const checkoutPct = useMemo(() => {
    if (winnerIdx == null) return '—'
    const doubles = VISITS.filter((v) => v.p === winnerIdx).flatMap((v) => v.darts).filter((d) => d.label.startsWith('D'))
    const hits = doubles.filter((d) => !d.miss).length
    return doubles.length ? `${Math.round((hits / doubles.length) * 100)}%` : '—'
  }, [winnerIdx])

  const watchAgain = async () => {
    if (busyRef.current) return
    busyRef.current = true
    try { await runReplay(tokenRef.current) }
    catch (e) { if (e !== CANCEL) throw e }
    finally { busyRef.current = false }
  }

  const inMatch = phase === 'match' || phase === 'winner'

  return (
    <div className="fixed inset-0 z-50 overflow-hidden text-white select-none">
      <style>{CSS}</style>
      <div className="cin-bg" />
      <div className="cin-spot cin-spot-a" />
      <div className="cin-spot cin-spot-b" />

      {/* Top bar */}
      <div className="absolute top-0 inset-x-0 flex items-center justify-between px-6 py-4 z-50">
        <div className="flex items-center gap-3">
          <span className="cin-live">● LIVE</span>
          <span className="text-white/60 text-[11px] font-bold tracking-[0.3em] uppercase hidden sm:block">
            {MATCH.title}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {(phase === 'title' || phase === 'walkon') && (
            <button onClick={() => skipRef.current?.()} className="cin-chipbtn">
              <FastForward className="w-3.5 h-3.5" /> Skip intro
            </button>
          )}
          <button onClick={() => { sound.setEnabled(muted); setMuted(!muted) }} className="cin-chipbtn" title="Toggle sound">
            {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
          <button onClick={onExit} className="cin-chipbtn" title="Exit demo">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Title card */}
      {phase === 'title' && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center text-center px-6">
          <div className="cin-rise text-xs tracking-[0.55em] text-white/50 font-bold mb-5">DARTS.AI PRESENTS</div>
          <h1 className="cin-title-text">WORLD<br />CHAMPIONSHIP</h1>
          <div className="cin-rise2 mt-5 text-white/70 tracking-[0.4em] font-bold text-sm">{MATCH.subtitle}</div>
          <div className="cin-rise3 mt-10 flex items-center gap-5">
            <span className="text-xl font-black uppercase" style={{ color: PLAYERS[0].color }}>{PLAYERS[0].name}</span>
            <span className="text-white/40 font-light text-2xl italic">vs</span>
            <span className="text-xl font-black uppercase" style={{ color: PLAYERS[1].color }}>{PLAYERS[1].name}</span>
          </div>
        </div>
      )}

      {/* Walk-on */}
      {phase === 'walkon' && <WalkOnCard key={walkonIdx} pl={PLAYERS[walkonIdx]} />}

      {/* Match stage */}
      {inMatch && (
        <div className="absolute inset-0 z-10 flex flex-col pt-14">
          <div className="flex-1 relative flex items-center justify-center min-h-0 py-2">
            <div className="cin-board-glow" />
            <div className="cin-zoom h-full max-h-[58vh] aspect-square" style={zoom || {}}>
              <div ref={shakeRef} className="w-full h-full">
                <BroadcastBoard darts={boardDarts} pops={pops} />
              </div>
            </div>
            {replaying && <div className="cin-replay-badge">● REPLAY</div>}
            {banner && <div className="cin-banner">{banner} 🎯</div>}
            {drama && <div className="cin-drama">{drama}</div>}
            <SideChar pl={PLAYERS[0]} pose={poses[0]} side="left" active={activeP === 0}
              defeated={winnerIdx != null && winnerIdx !== 0} />
            <SideChar pl={PLAYERS[1]} pose={poses[1]} side="right" active={activeP === 1}
              defeated={winnerIdx != null && winnerIdx !== 1} />
          </div>

          {hint && (
            <div className="cin-hint self-center" style={{ borderColor: `${PLAYERS[activeP].color}99`, color: PLAYERS[activeP].color }}>
              CHECKOUT · {hint}
            </div>
          )}

          <div className="flex gap-3 items-stretch px-5 pb-5 pt-3 z-30">
            <Panel pl={PLAYERS[0]} idx={0} score={scores[0]} stat={stats[0]}
              active={activeP === 0 && winnerIdx == null} visitDarts={activeP === 0 ? visitDarts : []} winnerIdx={winnerIdx} />
            <div className="hidden lg:flex flex-col items-center justify-center px-4 text-center shrink-0">
              <div className="text-2xl font-black text-white/85 tabular-nums">501</div>
              <div className="text-[9px] tracking-[0.3em] text-white/40 font-bold uppercase">Double out</div>
            </div>
            <Panel pl={PLAYERS[1]} idx={1} score={scores[1]} stat={stats[1]}
              active={activeP === 1 && winnerIdx == null} visitDarts={activeP === 1 ? visitDarts : []} winnerIdx={winnerIdx} />
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

      {confetti && <Confetti />}

      {/* Winner card */}
      {phase === 'winner' && !replaying && winner && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-sm px-4">
          <div className="cin-winner">
            <Trophy className="w-10 h-10 text-amber-400 mx-auto" />
            <div className="text-[11px] tracking-[0.55em] text-amber-300/90 font-bold mt-2">CHAMPION</div>
            <div className="w-36 h-36 mx-auto my-5 rounded-full overflow-hidden border-4"
              style={{ borderColor: winner.color, background: winner.cardBg, boxShadow: `0 0 50px ${winner.color}55` }}>
              <Caricature variant={winner.variant} pose="celebrate" framing="bust" shirt={winner.color} className="w-full h-full" />
            </div>
            <div className="text-3xl font-black uppercase tracking-wide">{winner.name}</div>
            <div className="text-white/50 tracking-[0.3em] text-xs font-bold uppercase mt-1">“{winner.nick}”</div>

            <div className="grid grid-cols-4 gap-2 mt-6">
              {[
                ['3-DART AVG', finalStats[winnerIdx].avg.toFixed(1)],
                ['180s', finalStats[winnerIdx].maxima],
                ['CHECKOUT', checkoutPct],
                ['DARTS', finalStats[winnerIdx].darts],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-white/5 border border-white/10 py-3">
                  <div className="text-xl font-black tabular-nums" style={{ color: winner.color }}>{v}</div>
                  <div className="text-[9px] tracking-[0.2em] text-white/40 font-bold mt-0.5">{k}</div>
                </div>
              ))}
            </div>

            <div className="flex gap-2 mt-6">
              <button onClick={watchAgain} className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/15 text-sm font-bold tracking-wider uppercase transition-colors">
                <RotateCcw className="w-4 h-4" /> Winning dart
              </button>
              <button onClick={onExit} className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border text-sm font-bold tracking-wider uppercase transition-colors"
                style={{ background: `${winner.color}22`, borderColor: `${winner.color}77`, color: winner.color }}>
                <X className="w-4 h-4" /> Exit show
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const CSS = `
.cin-bg { position:absolute; inset:0; background:
  radial-gradient(120% 90% at 50% -10%, #222b4d 0%, #0a0d18 55%, #04050a 100%); }
.cin-spot { position:absolute; width:160vmax; height:160vmax; left:50%; top:-80vmax;
  margin-left:-80vmax; mix-blend-mode:screen; pointer-events:none; }
.cin-spot-a { background: conic-gradient(from 175deg at 50% 50%,
  transparent 0deg, rgba(125,170,255,0.10) 4deg, transparent 9deg,
  transparent 22deg, rgba(255,130,180,0.08) 26deg, transparent 31deg);
  animation: cin-sweep 11s ease-in-out infinite alternate; }
.cin-spot-b { background: conic-gradient(from 168deg at 50% 50%,
  transparent 0deg, rgba(160,255,220,0.06) 5deg, transparent 11deg);
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

.cin-winner { width:min(460px, 94vw); border-radius:28px; padding:30px 28px 26px; text-align:center;
  background:linear-gradient(180deg, #12151f, #0a0c12); border:1px solid rgba(255,255,255,.12);
  box-shadow: 0 40px 120px rgba(0,0,0,.7), 0 0 90px rgba(245,158,11,.12);
  animation: cin-pop-in .6s cubic-bezier(.2,1.4,.3,1) both; }
`
