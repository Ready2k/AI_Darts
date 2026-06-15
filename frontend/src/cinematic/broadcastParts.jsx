// Shared broadcast-style presentational pieces used by both the scripted
// CinematicDemo and the live CinematicGame view: the blister-pack walk-on
// card, the flanking match-side caricatures, the lower-third score panel,
// the confetti burst, and the full cin-* stylesheet.
import { useMemo } from 'react'
import { Trophy } from 'lucide-react'
import Caricature, { Accessory } from '../art/Caricature'

export const HEART = 'M12,21 C5,16 2,11 2,7.5 C2,4.5 4.5,2.5 7,2.5 C9,2.5 10.8,3.6 12,5.4 ' +
  'C13.2,3.6 15,2.5 17,2.5 C19.5,2.5 22,4.5 22,7.5 C22,11 19,16 12,21 Z'

// ── Walk-on: blister-pack player card ───────────────────────────────────────
export function WalkOnCard({ pl }) {
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
export function SideChar({ pl, pose, side, active, defeated }) {
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
export function Panel({ pl, idx, score, stat, active, visitDarts, winnerIdx }) {
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

// ── Confetti burst ──────────────────────────────────────────────────────────
export function Confetti() {
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

// ── Full broadcast stylesheet (shared by demo + live cinematic game) ─────────
export const CSS = `
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
