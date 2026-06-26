// The Cinematic Demo: a full-screen, broadcast-style scripted darts final.
// Title card → blister-pack walk-ons → live match with caller audio, 180s,
// missed-double drama → game shot, confetti, slow-mo replay → winner card.
// Self-contained: pure SVG/CSS visuals, WebAudio + SpeechSynthesis sound.
import { useState, useEffect, useRef, useMemo } from 'react'
import { X, Volume2, VolumeX, FastForward } from 'lucide-react'
import BroadcastBoard from './BroadcastBoard'
import { mmToPct } from './geometry'
import { SCRIPTS } from './scripts'
import { sound } from './audio'
import { CSS, WalkOnCard, SideChar, Panel, Confetti, WinnerCard } from './broadcastParts'

const CANCEL = Symbol('cancelled')

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
          <WinnerCard
            winner={winner}
            crown="CHAMPION"
            accent={winner.color}
            stats={[
              ['3-DART AVG', finalStats[winnerIdx].avg.toFixed(1)],
              ['180s', finalStats[winnerIdx].maxima],
              ['CHECKOUT', checkoutPct],
              ['DARTS', finalStats[winnerIdx].darts],
            ]}
            onReplay={watchAgain}
            onExit={onExit}
          />
        </div>
      )}
    </div>
  )
}
