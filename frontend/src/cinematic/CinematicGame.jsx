// Live cinematic broadcast view for a real 2-player X01 game.
// Unlike CinematicDemo (a canned scripted final), this is driven entirely by
// the live game state pushed over the WebSocket plus the shared throw-animation
// state from App. It reuses the broadcast presentational parts (walk-on cards,
// flanking caricatures, lower-third score panels) and the cin-* stylesheet.
import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Volume2, VolumeX, Star, Move, Pause, Play } from 'lucide-react'
import BroadcastBoard from './BroadcastBoard'
import { CSS, WalkOnCard, RulesCard, SideChar, Panel, CricketScoreboard, KillerScoreboard, Confetti, WinScene } from './broadcastParts'
import { themeFor, venueFor } from './modeThemes'
import CrowdRow from '../art/CrowdRow'
import KillerSpin from './KillerSpin'
import { sound, crowd } from './audio'
import { pickLine } from './commentary'
import { getAvatar } from '../config/avatars'
import { ThrowState } from '../config/timing'

// Player accent colours — cyan / rose first (matching the demo), then a spread
// for 3-6 player games.
const COLORS = ['#22d3ee', '#fb7185', '#a78bfa', '#34d399', '#fbbf24', '#f97316']
const DEFAULT_ACCESSORIES = ['darts', 'trophy', 'pint']
const ROTS = [-7, 6, 13] // slight per-dart tilt so the three darts don't overlap perfectly

// Per-mode rules shown on the intro card (and announced by the caller). `text`
// uses the live game dict so round counts / start scores are accurate.
function rulesFor(game) {
  const mode = game?.mode ?? 'X01'
  const rounds = game?.rounds
  switch (mode) {
    case 'Cricket':
      return {
        title: 'Cricket',
        tagline: 'Close it out',
        lines: [
          'Targets are 20, 19, 18, 17, 16, 15 and the bull.',
          'Three marks closes a number for YOU (single = 1, double = 2, treble = 3) — it stays open for everyone else.',
          'Once you have closed a number, more hits score its value as points — but only while an opponent still has it open.',
          'A number is dead (no points) once everyone has closed it.',
          'Win by closing all your numbers with the points lead (or level).',
        ],
        say: 'Cricket. Close twenty down to fifteen and the bull. Closing is per player. Score points on your closed numbers while an opponent is still open, then finish with the lead to win.',
      }
    case 'Around the Clock':
      return {
        title: 'Around the Clock',
        tagline: '1 → 20 → Bull',
        lines: [
          'Hit every number in order: 1 through 20, then the bull.',
          'Any single, double or treble of your target counts.',
          'First player to clear the bull wins.',
        ],
        say: 'Around the Clock. Hit one through twenty in order, then the bull. First to finish wins.',
      }
    case 'Shanghai':
      return {
        title: 'Shanghai',
        tagline: `Target 1 → ${rounds ?? 7}`,
        lines: [
          'Each round targets one number, climbing from 1.',
          'Single, double and treble of that number score.',
          `Highest total after ${rounds ?? 7} rounds wins…`,
          'Hit the single, double AND treble in one visit for an instant Shanghai!',
        ],
        say: 'Shanghai. Hit the round number for points. Land a single, double and treble in one visit to win outright.',
      }
    case 'Killer': {
      const hard = game?.arm_mode === 'double'
      const armLine = hard
        ? 'Arm yourself: hit the DOUBLE of YOUR own number to become a killer.'
        : 'Arm yourself: land 3 hits on YOUR own number to become a killer (a treble arms you at once).'
      return {
        title: 'Killer',
        tagline: hard ? 'Last one standing · Hard' : 'Last one standing',
        lines: [
          'Everyone is given a number and a set of lives.',
          armLine,
          'Then hit an opponent\'s number to take lives — single 1, double 2, treble 3.',
          'Careful: once armed, hitting your OWN number costs YOU lives.',
          'Lose all your lives and you\'re out. Last player alive wins.',
        ],
        say: hard
          ? 'Killer. Arm on your own double, then knock the lives off everyone else. Last one standing wins. Watch your own number!'
          : 'Killer. Hit your own number three times to arm, then knock the lives off everyone else. Last one standing wins. Watch your own number!',
      }
    }
    case 'Count Up':
      return {
        title: 'Count Up',
        tagline: `${rounds ?? 8} rounds`,
        lines: [
          'Every dart scores its face value.',
          'Pile on as many points as you can.',
          `Highest total after ${rounds ?? 8} rounds takes it.`,
        ],
        say: `Count Up. Score as many points as you can over ${rounds ?? 8} rounds. Highest total wins.`,
      }
    default: {
      const ci = game?.check_in === 'master' ? 'Master in'
        : game?.check_in === 'double' ? 'Double in' : 'Straight in'
      return {
        title: `${game?.start_score ?? 501}`,
        tagline: `${ci} · ${game?.double_out ? 'Double out' : 'Straight out'}`,
        lines: [
          `First player to reach exactly zero from ${game?.start_score ?? 501}.`,
          `${ci}${game?.double_out ? ', and you must finish on a double.' : '.'}`,
          'Three darts a visit — go bust and the visit is wiped.',
        ],
        say: `${game?.start_score ?? 501}, ${ci.toLowerCase()}${game?.double_out ? ', double out' : ''}. First to zero wins.`,
      }
    }
  }
}

// Per-mode winner-card stat grid, built from the live player dict. Only uses
// fields the backend already exposes (avg, darts, legs, sets, score, state) so
// it degrades gracefully — anything missing shows as a dash. Returns up to 4
// [label, value] pairs.
function winStats(game, p) {
  if (!p) return []
  const mode = game?.mode ?? 'X01'
  const dash = (v) => (v == null || v === '' ? '—' : v)
  switch (mode) {
    case 'Cricket':
      return [
        ['POINTS', dash(p.score)],
        ['LEGS', dash(p.legs)],
        ['DARTS', dash(p.darts)],
      ]
    case 'Killer': {
      const lives = p.state?.lives
      return [
        ['LIVES LEFT', dash(lives)],
        ['NUMBER', dash(p.state?.number)],
        ['DARTS', dash(p.darts)],
      ]
    }
    case 'Around the Clock':
      return [
        ['DARTS', dash(p.darts)],
        ['LEGS', dash(p.legs)],
      ]
    case 'Shanghai':
    case 'Count Up':
      return [
        ['SCORE', dash(p.score)],
        ['DARTS', dash(p.darts)],
      ]
    default: // X01
      return [
        ['3-DART AVG', dash(p.avg)],
        ['LEGS', dash(p.legs)],
        ['SETS', dash(p.sets)],
        ['DARTS', dash(p.darts)],
      ]
  }
}

// Map a live game player + chosen avatar into the broadcast `pl` shape.
function toCinPlayer(p, idx, avatarMap) {
  const av = getAvatar(avatarMap[p.name])
  return {
    name: p.name,
    nick: av.name,
    variant: av.variant,
    color: COLORS[idx] || COLORS[0],
    cardBg: av.bg,
    theme: av.theme,
    accessories: DEFAULT_ACCESSORIES,
    bio: p.darts > 0 ? `Average ${p.avg} · ${p.legs} legs won` : 'Stepping up to the oche',
  }
}

// Live Autodarts board-manager status chip. Reads the status pushed on the
// game-state WS (game.autodarts) and ticks once a second so a STUCK board (e.g.
// stuck mid-takeout, or no activity) becomes obvious instead of a silent hang.
function AutodartsStatus({ status }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  if (!status) return null

  const age = status.ts ? Math.max(0, Math.floor(now / 1000 - status.ts)) : null
  const ev = (status.event || '').toLowerCase()
  let dot = 'bg-emerald-400', label = 'Board ready', pulse = false
  if (!status.connected) {
    dot = 'bg-red-500'; label = 'Board offline'; pulse = true
  } else if (status.awaiting_takeout) {
    dot = 'bg-amber-400'; label = 'Take out darts'; pulse = true
  } else if (ev.includes('takeout') || ev.includes('take out')) {
    dot = 'bg-amber-400'; label = 'Takeout'; pulse = true
  } else if (ev.includes('throw')) {
    dot = 'bg-cyan-400'; label = 'Throw detected'; pulse = true
  } else if (ev.includes('reset')) {
    dot = 'bg-white/50'; label = 'Board reset'
  }
  // Connected but no board activity for a while during a takeout/awaiting state
  // → likely stuck. Surface it loudly.
  const watching = !status.connected || status.awaiting_takeout || ev.includes('takeout')
  const stuck = status.connected && watching && age != null && age >= 12

  return (
    <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-bold tracking-[0.15em] uppercase border"
      style={stuck
        ? { background: 'rgba(239,68,68,0.15)', borderColor: 'rgba(239,68,68,0.5)', color: '#fca5a5' }
        : { background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.75)' }}
      title="Autodarts board-manager status">
      <span className={`w-2 h-2 rounded-full ${stuck ? 'bg-red-500' : dot} ${pulse ? 'animate-pulse' : ''}`} />
      {stuck ? `Stuck? ${label} · ${age}s` : label}
      {!stuck && age != null && age >= 4 && watching && <span className="opacity-50">· {age}s</span>}
    </span>
  )
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

// Per-turn spoken intro: what the active player needs this visit. Mode-aware so
// every game gets a quick "{player} needs …" call when their turn comes around.
function turnIntro(game, i) {
  const p = game?.players?.[i]
  if (!p) return null
  const name = p.name || 'Player'
  const st = p.state || {}
  switch (game.mode ?? 'X01') {
    case 'Around the Clock': {
      const t = st.target
      return t ? `${name} needs ${t === 'Bull' ? 'bull' : t}` : `${name} to throw`
    }
    case 'Shanghai':
      return `${name} needs ${st.target ?? game.round}`
    case 'Killer':
      if (st.out) return null
      return st.killer ? `${name}, you're a killer` : `${name}, arm on ${st.number ?? 'your number'}`
    case 'Cricket':
    case 'Count Up':
      return `${name} to throw`
    default: // X01
      return `${name} needs ${p.score}`
  }
}

// A monotonic "progress" metric for the active player, used to fire a success
// sound the moment they hit what they needed. Only target-based modes qualify;
// modes where every dart scores (X01 / Count Up) return null (no discrete hit).
function activeProgress(game, i) {
  const p = game?.players?.[i]
  if (!p) return null
  if ((game.mode ?? 'X01') === 'Around the Clock') return p.state?.idx ?? 0
  if ((game.mode ?? 'X01') === 'Shanghai') return p.score ?? 0
  return null
}

export default function CinematicGame({ game, avatarMap = {}, animState, boardDarts, cameraSrc, onExit, onAssignNumbers, onPause }) {
  const [muted, setMuted] = useState(!sound.enabled)
  const [phase, setPhase] = useState('match') // 'walkon' | 'match'
  const [walkonIdx, setWalkonIdx] = useState(0)
  const [bigCall, setBigCall] = useState(null)
  const [crowdReact, setCrowdReact] = useState(false)  // visual crowd roar bounce
  const [winScene, setWinScene] = useState(null)       // { winnerIdx, pos } once per game-over

  const winFiredRef = useRef(null)   // game-over signature already shown (once-only guard)

  const seenSigRef = useRef(null)
  const crowdReactTimer = useRef(null)
  const walkTimers = useRef([])
  const prevSeqRef = useRef(game?.dart_seq ?? 0)
  const bigCallTimer = useRef(null)
  const prevKillerRef = useRef(null)
  const prevCricketRef = useRef(null)
  const prevTurnRef = useRef(null)
  const prevProgressRef = useRef(null)
  const prevCheckoutRef = useRef(false)
  const wasOnCheckoutRef = useRef(false)   // owned by the big-call effect (miss detection)
  const prevLeaderRef = useRef(null)

  // ── Draggable camera inset ────────────────────────────────────────────────
  // Position is the inset's top-left within the board stage, in px. null = the
  // default bottom-right corner. Persisted so it sticks across sessions.
  const stageRef = useRef(null)
  const camRef = useRef(null)
  const dragRef = useRef(null)
  const [camPos, setCamPos] = useState(() => {
    try { return JSON.parse(localStorage.getItem('cinematicCamPos')) || null } catch { return null }
  })
  const camPosRef = useRef(camPos)
  const [dragging, setDragging] = useState(false)

  const onCamPointerDown = useCallback((e) => {
    const stage = stageRef.current
    const cam = camRef.current
    if (!stage || !cam) return
    const stageRect = stage.getBoundingClientRect()
    const camRect = cam.getBoundingClientRect()
    dragRef.current = {
      offX: e.clientX - camRect.left,
      offY: e.clientY - camRect.top,
      stageRect,
      camW: camRect.width,
      camH: camRect.height,
    }
    cam.setPointerCapture?.(e.pointerId)
    setDragging(true)
    e.preventDefault()
  }, [])

  const onCamPointerMove = useCallback((e) => {
    const d = dragRef.current
    if (!d) return
    const x = Math.max(0, Math.min(e.clientX - d.stageRect.left - d.offX, d.stageRect.width - d.camW))
    const y = Math.max(0, Math.min(e.clientY - d.stageRect.top - d.offY, d.stageRect.height - d.camH))
    const pos = { x, y }
    camPosRef.current = pos
    setCamPos(pos)
  }, [])

  const onCamPointerUp = useCallback((e) => {
    if (!dragRef.current) return
    dragRef.current = null
    setDragging(false)
    camRef.current?.releasePointerCapture?.(e.pointerId)
    if (camPosRef.current) {
      localStorage.setItem('cinematicCamPos', JSON.stringify(camPosRef.current))
    }
  }, [])

  const players = game?.players ?? []
  const cinPlayers = players.map((p, i) => toCinPlayer(p, i, avatarMap))
  const activeIdx = game?.over ? -1 : (game?.current ?? 0)
  const winnerIdx = game?.over && game?.winner != null
    ? players.findIndex((p) => p.name === game.winner)
    : null

  // ── Walk-on intro: only for a freshly-started game ────────────────────────
  // Freshness = a new game with no darts thrown yet. (Don't tie this to score
  // matching start_score — modes like Killer start each player above 0, so that
  // check wrongly suppressed the intro.)
  const sig = players.map((p) => p.name).join('|') + '@' +
    (game?.mode ?? '') + ':' + (game?.start_score ?? '') + ':' + (game?.lives ?? game?.rounds ?? '')
  const isFresh = !!game && !game.over && (game.dart_seq ?? 0) === 0

  useEffect(() => {
    if (!game) return
    if (sig === seenSigRef.current) return
    seenSigRef.current = sig

    walkTimers.current.forEach(clearTimeout)
    walkTimers.current = []

    // Walk-on: every player gets a 3s blister-pack card, then a rules card
    // explaining the mode, then play. The camera feed is mounted throughout
    // (see render) so it warms up during the intro. Deferred (setTimeout 0) to
    // avoid synchronous setState.
    if (isFresh && players.length >= 1) {
      const intro = cinPlayers
      const rules = rulesFor(game)
      const announce = (pl) => {
        sound.cheer(false)
        sound.walkOnTheme(pl.theme)   // persona entrance sting
        sound.say(`Introducing... ${pl.name}. ${pl.nick}!`, { rate: 1.0, pitch: 1.04 })
      }
      sound.stop()
      const STEP = 3000
      intro.forEach((pl, i) => {
        walkTimers.current.push(setTimeout(() => {
          setPhase('walkon'); setWalkonIdx(i); announce(pl)
        }, i === 0 ? 0 : i * STEP))
      })
      const afterWalkons = intro.length * STEP
      // Rules card stays up until the user clicks "Let's play" — no auto-close.
      walkTimers.current.push(setTimeout(() => {
        setPhase('rules')
        sound.cheer(false)
        sound.say(rules.say, { rate: 0.96 })
      }, afterWalkons))
    } else {
      walkTimers.current.push(setTimeout(() => setPhase('match'), 0))
    }
  }, [sig, isFresh, game, players.length, cinPlayers])

  useEffect(() => () => walkTimers.current.forEach(clearTimeout), [])

  // ── Crowd ambience bed ────────────────────────────────────────────────────
  // Start the looping crowd murmur once the match is live; tear it down when we
  // leave 'match' (rules/spin/walk-on) and on unmount. roar()/hush() are fired
  // from the big-call and checkout effects below.
  useEffect(() => {
    if (phase === 'match') {
      crowd.start()
      crowd.setIntensity(0.45)
    } else {
      crowd.stop()
    }
    return () => crowd.stop()
  }, [phase])

  // ── Checkout hush ─────────────────────────────────────────────────────────
  // When a player is on a finish (game.checkout present), drop the crowd to a
  // tense near-silence; restore the resting intensity once the checkout clears.
  useEffect(() => {
    if (phase !== 'match') { prevCheckoutRef.current = false; return }
    const onCheckout = !!game?.checkout && !game?.over
    if (onCheckout && !prevCheckoutRef.current) {
      crowd.hush()
    } else if (!onCheckout && prevCheckoutRef.current) {
      crowd.setIntensity(0.45)   // restore murmur after the attempt
    }
    prevCheckoutRef.current = onCheckout
  }, [game, phase])

  const skipIntro = () => {
    walkTimers.current.forEach(clearTimeout)
    walkTimers.current = []
    sound.stop()
    sound.say(rulesFor(game).say, { rate: 0.96 })
    setPhase('rules')
  }

  // User confirms the rules card → Killer goes to the spin-the-wheel number
  // pick first; every other mode starts play immediately.
  const startMatch = () => {
    walkTimers.current.forEach(clearTimeout)
    walkTimers.current = []
    if ((game?.mode) === 'Killer') {
      sound.say('Spin for your numbers!', { rate: 0.98 })
      setPhase('spin')
      return
    }
    sound.cheer(false)
    sound.say('Game on!', { rate: 0.9 })
    setPhase('match')
  }

  // Spin-the-wheel finished → push the chosen numbers to the backend, then play.
  const confirmNumbers = async (numbers) => {
    try { await onAssignNumbers?.(numbers) } catch { /* non-fatal */ }
    sound.cheer(false)
    sound.say('Game on!', { rate: 0.9 })
    setPhase('match')
  }

  // ── Big-call overlay on visit completion (180 / game shot) ────────────────
  useEffect(() => {
    if (!game) return
    // Snapshot whether a checkout was on the board *before* this update, then
    // record the current state for next time. Done before the early returns so
    // it's tracked on every game change (independent of the hush effect's ref).
    const wasOnCheckout = wasOnCheckoutRef.current
    wasOnCheckoutRef.current = !!game.checkout && !game.over

    const seq = game.dart_seq ?? 0
    const prev = prevSeqRef.current
    prevSeqRef.current = seq
    if (seq <= prev) return // undo / reset / no change

    const disp = game.display_turn || []
    const visitOver = (game.turn?.length ?? 0) === 0 && disp.length > 0
    if (!visitOver) return

    // Checkout miss: the player was on a finish before this visit completed but
    // the visit ended without winning. Fire the disappointed caller.
    if (wasOnCheckout && !game.over) {
      sound.say(pickLine('checkoutMiss'), { rate: 0.97, pitch: 0.82 })
    }

    const total = disp.reduce((s, d) => s + (d.points || 0), 0)
    const msg = game.message || ''
    const mode = game.mode ?? 'X01'
    const x01 = mode === 'X01'
    const th = themeFor(mode)
    let call = null
    let line = null   // optional spoken commentary for this big moment
    if (game.over) {
      call = { ...th.win }
      line = pickLine('win', { name: game.winner || 'The winner' })
    }
    else if (/wins the set/i.test(msg)) call = { text: 'GAME SHOT', sub: 'AND THE SET' }
    else if (/wins the leg/i.test(msg)) call = { text: 'GAME SHOT', sub: 'THE LEG' }
    else if (/SHANGHAI/i.test(msg)) call = { text: 'SHANGHAI', sub: 'INSTANT WIN' }
    // Killer: announce an elimination (not a win) with the knocked-out player.
    else if (mode === 'Killer' && /KNOCKS OUT|is OUT/i.test(msg)) {
      const victim = (msg.match(/KNOCKS OUT (.+?) \(/) || msg.match(/(\w[\w ]*) hit their OWN/) || [])[1]
      const v = victim ? victim.trim() : 'ONE DOWN'
      call = { text: 'ELIMINATED', sub: v, elim: true }
      line = pickLine('eliminated', { victim: victim ? victim.trim() : 'A player' })
    }
    // The 180 / big-score calls only make sense in X01, where the visit total
    // is the score. In Cricket/ATC the dart face value isn't the score, so a
    // "60 BIG SCORE" on three closing trebles would be nonsense.
    else if (x01 && total === 180) { call = { text: '180', sub: 'MAXIMUM' }; line = pickLine('visitTotal', { total }) }
    else if (x01 && total >= 100) { call = { text: String(total), sub: 'BIG SCORE' }; line = pickLine('visitTotal', { total }) }

    if (call) {
      crowd.roar()   // crowd swells on every big moment (audio)
      // Visual partner: bounce the crowd silhouettes. Re-arm so back-to-back
      // big calls each retrigger the bounce. Deferred (setTimeout 0) to avoid a
      // synchronous setState inside the effect body.
      clearTimeout(crowdReactTimer.current)
      setTimeout(() => {
        setCrowdReact(false)
        requestAnimationFrame(() => setCrowdReact(true))
      }, 0)
      crowdReactTimer.current = setTimeout(() => setCrowdReact(false), 1200)
      if (line) sound.say(line, { rate: 0.96 })
      clearTimeout(bigCallTimer.current)
      // Deferred to avoid synchronous setState inside the effect body.
      setTimeout(() => setBigCall(call), 0)
      bigCallTimer.current = setTimeout(() => setBigCall(null), 2200)
    }
  }, [game])

  useEffect(() => () => { clearTimeout(bigCallTimer.current); clearTimeout(crowdReactTimer.current) }, [])

  // ── Win-moment finale (visual only) ───────────────────────────────────────
  // On game-over, after the themed big-call has had its moment, raise the shared
  // WinScene: a slow-mo replay of the winning dart (board position from
  // game.last_dart_pos, falling back to the last display_turn dart with a pos),
  // then the winner card with real stats. Guarded so it fires exactly once per
  // game-over — keyed on the winner name so a fresh game (winner cleared) re-arms
  // it. Audio is owned by the commentary agent's `win` line, so this is visuals
  // only (muteReplaySound).
  const winTimerRef = useRef(null)
  useEffect(() => {
    if (!game || !game.over || game.winner == null) {
      // New / ongoing game → clear the guard and any lingering scene.
      if (winFiredRef.current && (!game?.over || game?.winner == null)) {
        winFiredRef.current = null
        setWinScene(null)
      }
      return
    }
    const sigOver = `${game.winner}#${game.dart_seq ?? 0}`
    if (winFiredRef.current === sigOver) return
    winFiredRef.current = sigOver

    const wIdx = players.findIndex((p) => p.name === game.winner)
    if (wIdx < 0) return
    // Winning-dart board position: prefer the explicit last_dart_pos; else the
    // last dart in the just-finished visit that carries a board coord.
    let pos = game.last_dart_pos || null
    if (!pos) {
      const disp = game.display_turn || []
      for (let i = disp.length - 1; i >= 0; i--) {
        if (disp[i]?.pos) { pos = disp[i].pos; break }
      }
    }
    // Defer until the big-call/confetti beat has played (it lives ~2.2s).
    clearTimeout(winTimerRef.current)
    winTimerRef.current = setTimeout(() => {
      setWinScene({ winnerIdx: wIdx, pos: pos || null })
    }, 2400)
  }, [game, players])

  useEffect(() => () => clearTimeout(winTimerRef.current), [])

  // ── Killer sound design: kerching (arming hit), lock-and-load (armed), and
  // ouch (a life knocked off). Diff the per-player Killer state each update. ──
  useEffect(() => {
    if (!game || game.mode !== 'Killer') { prevKillerRef.current = null; return }
    const cur = (game.players || []).map((p) => ({
      arm: p.state?.arm ?? 0,
      killer: !!p.state?.killer,
      lives: p.state?.lives ?? 0,
    }))
    const prev = prevKillerRef.current
    if (prev && prev.length === cur.length) {
      cur.forEach((c, i) => {
        const pr = prev[i]
        if (!pr.killer && c.killer) {
          sound.lockLoad()        // rack SFX
          const name = game.players?.[i]?.name || 'Player'
          sound.say(pickLine('killerArm', { name }), { rate: 1.0, pitch: 0.85 })
        }
        else if (!c.killer && c.arm > pr.arm) sound.kerching() // arming hit
        if (c.lives < pr.lives) sound.ouch()                // life taken
      })
    }
    prevKillerRef.current = cur
  }, [game])

  // ── Cricket call-outs: announce when a number is closed, and whether it can
  // now be scored against (an opponent still has it open) or is dead. Diff each
  // player's marks; a target crossing 3 marks is a close. ──────────────────────
  useEffect(() => {
    if (!game || game.mode !== 'Cricket') { prevCricketRef.current = null; return }
    const players = game.players || []
    const cur = players.map((p) => ({ ...(p.state?.marks || {}) }))
    const prev = prevCricketRef.current
    if (prev && prev.length === cur.length) {
      cur.forEach((marks, i) => {
        const pr = prev[i] || {}
        Object.keys(marks).forEach((k) => {
          const wasClosed = (pr[k] ?? 0) >= 3
          const nowClosed = (marks[k] ?? 0) >= 3
          if (!wasClosed && nowClosed) {
            const label = k === '25' ? 'Bull' : k
            // Scoreable while any OTHER player still has this number open (<3).
            const scoreable = cur.some((m, j) => j !== i && (m[k] ?? 0) < 3)
            const name = players[i]?.name || 'Player'
            sound.kerching()   // success cue: a number just closed
            const head = pickLine('cricketClose', { name, label })
            sound.say(`${head} ${scoreable ? 'Open for points.' : 'Dead number.'}`, { rate: 0.95 })
          }
        })
      })
    }
    prevCricketRef.current = cur
  }, [game])

  // ── Per-turn intro + target-hit success. On turn handover, announce what the
  // active player needs ("{player} needs 1"); within a turn, play a success cue
  // the instant their progress advances (e.g. ATC idx ↑, Shanghai score ↑). ───
  useEffect(() => {
    if (phase !== 'match' || !game || game.over) {
      prevTurnRef.current = null
      prevProgressRef.current = null
      return
    }
    const cur = game.current
    if (prevTurnRef.current !== cur) {
      // New visit → announce the intro and reset the success baseline.
      prevTurnRef.current = cur
      prevProgressRef.current = activeProgress(game, cur)
      // X01: vary the intro via the commentary bank (one variant is still the
      // classic "{name} needs N"). Other modes keep their mode-specific phrase.
      const mode = game.mode ?? 'X01'
      if (mode === 'X01') {
        const p = game.players?.[cur]
        if (p) sound.say(pickLine('turnIntro', { name: p.name || 'Player', need: p.score }), { rate: 0.96 })
      } else {
        const phrase = turnIntro(game, cur)
        if (phrase) sound.say(phrase, { rate: 0.96 })
      }
      return
    }
    const prog = activeProgress(game, cur)
    if (prevProgressRef.current != null && prog != null && prog > prevProgressRef.current) {
      sound.kerching()   // they hit what they needed
    }
    prevProgressRef.current = prog
  }, [game, phase])

  // ── Lead-change call (X01) ────────────────────────────────────────────────
  // Track who's nearest a finish (lowest score). When the leader changes mid-
  // match, the co-commentator (lower pitch) calls it. Only fires once a few
  // darts are in so the start-of-leg tie doesn't trigger it.
  useEffect(() => {
    if (phase !== 'match' || !game || game.over || (game.mode ?? 'X01') !== 'X01') {
      prevLeaderRef.current = null
      return
    }
    const ps = game.players || []
    if (ps.length < 2 || (game.dart_seq ?? 0) < 3) return
    let leader = null, best = Infinity
    ps.forEach((p) => { if (p.score < best) { best = p.score; leader = p.name } })
    const prev = prevLeaderRef.current
    if (prev != null && leader != null && leader !== prev) {
      sound.say(pickLine('leadChange', { leader }), { rate: 0.95, pitch: 0.78 })
    }
    prevLeaderRef.current = leader
  }, [game, phase])

  const paused = !!game?.paused
  const togglePause = () => onPause?.(!paused)

  const toggleMute = () => {
    const next = !muted
    setMuted(next)
    sound.setEnabled(!next)
  }

  if (!game || players.length < 1) return null
  const isX01 = (game.mode ?? 'X01') === 'X01'
  const theme = themeFor(game.mode ?? 'X01')
  // Venue re-skins the arena backdrop (default per mode; a picker could pass a
  // key later). Its CSS vars are spread onto the cinematic root below.
  const venue = venueFor(game.mode ?? 'X01')

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

  const visitDarts = (boardDarts || []).map((d) => ({ label: d.label, confidence: d.confidence }))
  const poses = cinPlayers.map((_, i) => {
    if (winnerIdx != null) return i === winnerIdx ? 'celebrate' : 'defeated'
    return i === activeIdx ? poseForState(animState) : 'idle'
  })

  const stat = (p) => ({ darts: p.darts, pts: (p.avg * p.darts) / 3 })

  // Board segments the active player should aim for (Cricket / ATC / Shanghai).
  const boardTargets = (() => {
    if (game.over || activeIdx < 0) return []
    const ap = players[activeIdx]
    if (game.mode === 'Cricket' && ap?.state?.marks) {
      return Object.entries(ap.state.marks)
        .filter(([, m]) => m < 3)
        .map(([k]) => Number(k))
    }
    if (game.mode === 'Around the Clock' && ap?.state?.target) {
      const t = ap.state.target
      return [t === 'Bull' ? 25 : Number(t)].filter((n) => !Number.isNaN(n))
    }
    if (game.mode === 'Shanghai' && game.target) {
      return [game.target]
    }
    if (game.mode === 'Killer' && ap?.state) {
      if (!ap.state.killer) return [ap.state.number]   // arm on your own number
      // Armed: aim at every alive opponent's number.
      return players
        .filter((p, i) => i !== activeIdx && !p.state?.out)
        .map((p) => p.state?.number)
        .filter(Boolean)
    }
    return []
  })()

  // Which players get a flanking caricature. 1-2 players → fixed P1/P2; 3+ →
  // the active thrower on the left (everyone is listed in the panels below).
  const sideChars = players.length <= 2
    ? { left: 0, right: players.length > 1 ? 1 : null }
    : { left: Math.max(0, activeIdx), right: null }

  return (
    <div ref={stageRef}
      className={`relative w-full h-full overflow-hidden rounded-2xl text-white ${crowdReact ? 'cin-crowd-react' : ''}`}
      style={venue.vars}>
      <style>{CSS}</style>
      <div className="cin-bg" />
      <div className="cin-spot cin-spot-a" />
      <div className="cin-spot cin-spot-b" />
      {/* Crowd silhouettes: a darkened band low on the stage, behind the board
          and the SideChar panels (z below them). Idle sway always; bounces when
          the root carries .cin-crowd-react on a big moment. */}
      <div className="cin-crowd">
        <div className="cin-crowd-sway w-full h-full">
          <CrowdRow accent={theme.accent} />
        </div>
      </div>

      {/* Top bar */}
      <div className="absolute top-0 inset-x-0 flex items-center justify-between px-6 py-4 z-50">
        <div className="flex items-center gap-3">
          <span className="cin-live">● LIVE</span>
          <span className="text-white/60 text-[11px] font-bold tracking-[0.3em] uppercase hidden sm:flex items-center gap-1.5">
            <Star className="w-3.5 h-3.5 text-amber-400" /> Cinematic mode
          </span>
          <AutodartsStatus status={game.autodarts} />
        </div>
        <div className="flex items-center gap-2">
          {phase === 'walkon' && (
            <button onClick={skipIntro} className="cin-chipbtn">Skip to rules</button>
          )}
          {phase === 'match' && !game.over && onPause && (
            <button onClick={togglePause} className="cin-chipbtn"
              title={paused ? 'Resume game' : 'Pause game'}>
              {paused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
            </button>
          )}
          <button onClick={toggleMute} className="cin-chipbtn" title="Toggle sound">
            {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
          </button>
          <button onClick={onExit} className="cin-chipbtn" title="Exit cinematic mode">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Paused overlay */}
      {phase === 'match' && paused && !game.over && (
        <div className="absolute inset-0 z-[60] flex flex-col items-center justify-center gap-6 bg-black/70 backdrop-blur-sm">
          <div className="flex items-center gap-4 text-white">
            <Pause className="w-12 h-12" />
            <span className="text-5xl font-black tracking-[0.2em] uppercase">Paused</span>
          </div>
          <button onClick={togglePause}
            className="flex items-center gap-2 px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 border border-white/20 text-white font-bold uppercase tracking-wider transition-colors">
            <Play className="w-5 h-5" /> Resume
          </button>
        </div>
      )}

      {/* Walk-on intro */}
      {phase === 'walkon' && <WalkOnCard key={walkonIdx} pl={cinPlayers[walkonIdx]} />}

      {/* Rules / how-to-play card */}
      {phase === 'rules' && <RulesCard rules={rulesFor(game)} players={cinPlayers} onStart={startMatch} theme={theme} />}

      {/* Killer spin-the-wheel number pick */}
      {phase === 'spin' && (
        <KillerSpin
          players={cinPlayers.map((cp, i) => ({ ...cp, is_ai: players[i]?.is_ai }))}
          accent={theme.accent}
          onConfirm={confirmNumbers}
        />
      )}

      {/* Match stage */}
      {phase === 'match' && (
        <div className="absolute inset-0 z-10 flex flex-col pt-14">
          <div className="flex-1 relative flex items-center justify-center min-h-0 py-2">
            <div className="cin-board-glow" />
            <div className="cin-zoom h-full max-h-[58vh] aspect-square">
              <BroadcastBoard darts={darts} targets={boardTargets} targetColor={activeColor} />
            </div>
            {/* Flanking caricatures. For 1-2 players, left=P1 / right=P2. For 3+
                players the side art follows the active thrower (left) so the
                person at the oche is always on screen; everyone shows below. */}
            {sideChars.left != null && cinPlayers[sideChars.left] && (
              <SideChar pl={cinPlayers[sideChars.left]} pose={poses[sideChars.left]} side="left"
                active={activeIdx === sideChars.left}
                defeated={winnerIdx != null && winnerIdx !== sideChars.left} />
            )}
            {sideChars.right != null && cinPlayers[sideChars.right] && (
              <SideChar pl={cinPlayers[sideChars.right]} pose={poses[sideChars.right]} side="right"
                active={activeIdx === sideChars.right}
                defeated={winnerIdx != null && winnerIdx !== sideChars.right} />
            )}
          </div>

          {game.checkout && activeIdx >= 0 && (
            <div className="cin-hint self-center" style={{ borderColor: `${activeColor}99`, color: activeColor }}>
              CHECKOUT · {game.checkout}
            </div>
          )}
          {!isX01 && (
            <div className="cin-hint self-center" style={{ borderColor: `${activeColor}99`, color: activeColor }}>
              {game.mode_label || game.mode}
            </div>
          )}

          {game.mode === 'Cricket' ? (
            <div className="px-5 pb-2 pt-1">
              <CricketScoreboard game={game} players={cinPlayers}
                activeIdx={activeIdx} winnerIdx={winnerIdx} />
            </div>
          ) : game.mode === 'Killer' ? (
            <div className="px-5 pb-2 pt-1">
              <KillerScoreboard game={game} players={cinPlayers}
                activeIdx={activeIdx} winnerIdx={winnerIdx} />
            </div>
          ) : (
          <div className="flex gap-3 items-stretch px-5 pb-5 pt-3 z-30">
            {players.length === 2 ? (
              <>
                <Panel pl={cinPlayers[0]} idx={0} score={players[0].score} stat={stat(players[0])}
                  active={activeIdx === 0} visitDarts={activeIdx === 0 ? visitDarts : []} winnerIdx={winnerIdx} />
                <div className="hidden lg:flex flex-col items-center justify-center px-4 text-center shrink-0">
                  <div className="text-2xl font-black text-white/85 tabular-nums">
                    {isX01 ? game.start_score : (game.target ?? game.round ?? '·')}
                  </div>
                  <div className="text-[9px] tracking-[0.3em] text-white/40 font-bold uppercase max-w-[7rem]">
                    {isX01 ? (game.double_out ? 'Double out' : 'Straight out')
                           : (game.mode ?? '')}
                  </div>
                </div>
                <Panel pl={cinPlayers[1]} idx={1} score={players[1].score} stat={stat(players[1])}
                  active={activeIdx === 1} visitDarts={activeIdx === 1 ? visitDarts : []} winnerIdx={winnerIdx} />
              </>
            ) : (
              cinPlayers.map((cp, i) => (
                <Panel key={i} pl={cp} idx={i} mirror={false} score={players[i].score} stat={stat(players[i])}
                  active={activeIdx === i} visitDarts={activeIdx === i ? visitDarts : []} winnerIdx={winnerIdx} />
              ))
            )}
          </div>
          )}
        </div>
      )}

      {/* Win confetti — themed to the mode's palette */}
      {phase === 'match' && game.over && <Confetti colors={theme.confetti} />}

      {/* Big calls (themed win / elimination / big score) */}
      {bigCall && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center pointer-events-none px-4">
          <div className="cin-flash" />
          {bigCall.elim ? (
            <>
              <div className="cin-elim">{bigCall.text}</div>
              <div className="cin-elim-sub">{bigCall.sub}</div>
            </>
          ) : (
            <>
              <div className="cin-bigcall">{bigCall.text}</div>
              <div className="cin-bigcall-sub">{bigCall.sub}</div>
            </>
          )}
        </div>
      )}

      {/* Win-moment finale: slow-mo winning-dart replay → winner card with real
          live stats. Confetti keeps falling behind it. Mounted once per
          game-over (guarded by winFiredRef). */}
      {winScene && cinPlayers[winScene.winnerIdx] && (
        <WinScene
          winner={cinPlayers[winScene.winnerIdx]}
          pos={winScene.pos}
          rot={ROTS[((game.display_turn?.length ?? 1) - 1) % ROTS.length] ?? 6}
          mode={game.mode ?? 'X01'}
          theme={theme}
          muteReplaySound
          stats={winStats(game, players[winScene.winnerIdx])}
          onExit={onExit}
        />
      )}

      {/* Live camera feed — mounted in both phases so it begins warming up
          during the walk-on; in match it becomes a draggable inset. Rendered in
          a single, stable spot so the MJPEG connection never remounts. */}
      {cameraSrc && (
        <div
          ref={camRef}
          onPointerDown={phase === 'match' ? onCamPointerDown : undefined}
          onPointerMove={phase === 'match' ? onCamPointerMove : undefined}
          onPointerUp={phase === 'match' ? onCamPointerUp : undefined}
          onPointerCancel={phase === 'match' ? onCamPointerUp : undefined}
          style={phase === 'match'
            ? (camPos ? { left: camPos.x, top: camPos.y } : { right: 8, bottom: 8 })
            : { left: 16, bottom: 16 }}
          className={`group absolute aspect-video rounded-lg overflow-hidden border bg-black/60 shadow-2xl select-none transition-[width,opacity] duration-500 ${
            phase === 'match'
              ? `z-30 w-36 sm:w-44 touch-none ${dragging ? 'cursor-grabbing border-cyan-400/70 ring-2 ring-cyan-400/40' : 'cursor-grab border-white/15'}`
              : 'z-10 w-28 opacity-70 border-white/10 pointer-events-none'
          }`}>
          <img src={cameraSrc} alt="camera" draggable={false}
            className="w-full h-full object-cover pointer-events-none" />
          <span className="absolute top-1 left-1 text-[8px] font-bold tracking-[0.2em] text-white/70 bg-black/50 px-1.5 py-0.5 rounded pointer-events-none">
            {phase === 'match' ? 'CAM' : 'WARMING UP'}
          </span>
          {phase === 'match' && (
            <span className="absolute top-1 right-1 p-0.5 rounded bg-black/50 text-white/60 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <Move className="w-3 h-3" />
            </span>
          )}
        </div>
      )}
    </div>
  )
}
