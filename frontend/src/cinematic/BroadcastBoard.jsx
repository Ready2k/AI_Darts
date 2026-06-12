// Broadcast-quality dartboard for the cinematic demo: full wire spider, number
// ring, studio lighting, and darts that fly in, thunk, wobble and cast shadow.

import { SIZE, C, SCALE } from './geometry'

const SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

const R = {
  bull: 6.35 * SCALE,
  bulls: 15.9 * SCALE,
  t0: 99 * SCALE,
  t1: 107 * SCALE,
  d0: 162 * SCALE,
  d1: 170 * SCALE,
  numbers: 226,
  surround: 248,
}

const COL = {
  dark: '#15181d',
  cream: '#efe4c8',
  red: '#d33b41',
  green: '#1f8a4c',
  wire: '#c9ced6',
}

const deg = (d) => (d * Math.PI) / 180
const pt = (r, th) => [C + r * Math.sin(th), C - r * Math.cos(th)]

function sector(ri, ro, t0, t1) {
  const [x0o, y0o] = pt(ro, t0)
  const [x1o, y1o] = pt(ro, t1)
  const [x1i, y1i] = pt(ri, t1)
  const [x0i, y0i] = pt(ri, t0)
  return `M${x0o},${y0o} A${ro},${ro} 0 0 1 ${x1o},${y1o} L${x1i},${y1i} A${ri},${ri} 0 0 0 ${x0i},${y0i} Z`
}

function Dart({ d }) {
  const x = C + d.x * SCALE
  const y = C - d.y * SCALE
  const dur = (d.slow ? 1500 : 560) + 'ms'
  return (
    <g transform={`translate(${x} ${y})`} style={{ '--dur': dur }}>
      <ellipse cx="3" cy="2.5" rx="8" ry="3" fill="rgba(0,0,0,0.45)" className="bb-shadow-in" />
      {d.win && <circle r="15" fill="none" stroke={d.color} strokeWidth="2.5" className="bb-winglow" />}
      <circle r="11" fill="none" stroke={d.color} strokeWidth="2" className="bb-impact" />
      <g transform={`rotate(${d.rot})`}>
        <g className="bb-dart-enter" style={{ transformBox: 'fill-box', transformOrigin: '50% 100%' }}>
          <line x1="0" y1="0" x2="0" y2="-15" stroke="#d6dae0" strokeWidth="1.8" />
          <rect x="-2.6" y="-32" width="5.2" height="17" rx="2.4" fill="url(#bbBarrel)" />
          <line x1="-2.6" y1="-21" x2="2.6" y2="-21" stroke="rgba(0,0,0,0.35)" strokeWidth="1" />
          <line x1="-2.6" y1="-25" x2="2.6" y2="-25" stroke="rgba(0,0,0,0.35)" strokeWidth="1" />
          <rect x="-1.5" y="-47" width="3" height="15" rx="1.5" fill="#262d38" />
          <path d="M0,-45 L9,-63 L5,-69 L0,-58 L-5,-69 L-9,-63 Z" fill={d.color} stroke="rgba(255,255,255,0.75)" strokeWidth="1" />
        </g>
      </g>
    </g>
  )
}

export default function BroadcastBoard({ darts = [], pops = [] }) {
  const sectors = []
  for (let i = 0; i < 20; i++) {
    const t0 = deg(i * 18 - 9)
    const t1 = deg(i * 18 + 9)
    const single = i % 2 === 0 ? COL.dark : COL.cream
    const ring = i % 2 === 0 ? COL.red : COL.green
    sectors.push(
      <g key={i}>
        <path d={sector(R.bulls, R.t0, t0, t1)} fill={single} />
        <path d={sector(R.t0, R.t1, t0, t1)} fill={ring} />
        <path d={sector(R.t1, R.d0, t0, t1)} fill={single} />
        <path d={sector(R.d0, R.d1, t0, t1)} fill={ring} />
      </g>
    )
  }

  const wires = []
  for (let i = 0; i < 20; i++) {
    const t = deg(i * 18 + 9)
    const [x0, y0] = pt(R.bulls, t)
    const [x1, y1] = pt(R.d1, t)
    wires.push(<line key={i} x1={x0} y1={y0} x2={x1} y2={y1} stroke={COL.wire} strokeWidth="1.1" opacity="0.85" />)
  }

  const numbers = SEGMENTS.map((seg, i) => {
    const [x, y] = pt(R.numbers, deg(i * 18))
    return (
      <text key={seg} x={x} y={y + 8} fontSize="23" fontWeight="700" textAnchor="middle"
        fill="#edeff2" transform={`rotate(${i * 18} ${x} ${y})`}>
        {seg}
      </text>
    )
  })

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full h-full block">
      <defs>
        <linearGradient id="bbBarrel" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#7d8694" />
          <stop offset="0.5" stopColor="#e3e7ec" />
          <stop offset="1" stopColor="#646d7a" />
        </linearGradient>
        <radialGradient id="bbSheen" cx="0.38" cy="0.3" r="0.75">
          <stop offset="0" stopColor="rgba(255,255,255,0.16)" />
          <stop offset="0.55" stopColor="rgba(255,255,255,0)" />
        </radialGradient>
        <radialGradient id="bbVignette" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0.62" stopColor="rgba(0,0,0,0)" />
          <stop offset="1" stopColor="rgba(0,0,0,0.5)" />
        </radialGradient>
        <radialGradient id="bbSurround" cx="0.5" cy="0.42" r="0.7">
          <stop offset="0" stopColor="#23262c" />
          <stop offset="1" stopColor="#0c0d10" />
        </radialGradient>
      </defs>

      <circle cx={C} cy={C} r={R.surround} fill="url(#bbSurround)" />
      <circle cx={C} cy={C} r={R.surround} fill="none" stroke="#3a3f47" strokeWidth="3" />

      {sectors}

      {/* wire spider */}
      {wires}
      {[R.bulls, R.t0, R.t1, R.d0].map((r) => (
        <circle key={r} cx={C} cy={C} r={r} fill="none" stroke={COL.wire} strokeWidth="1.1" opacity="0.85" />
      ))}
      <circle cx={C} cy={C} r={R.d1} fill="none" stroke={COL.wire} strokeWidth="2" opacity="0.95" />

      {/* bull */}
      <circle cx={C} cy={C} r={R.bulls} fill={COL.green} stroke={COL.wire} strokeWidth="1.2" />
      <circle cx={C} cy={C} r={R.bull} fill={COL.red} stroke={COL.wire} strokeWidth="1.2" />

      {numbers}

      <circle cx={C} cy={C} r={R.surround} fill="url(#bbSheen)" pointerEvents="none" />
      <circle cx={C} cy={C} r={R.surround} fill="url(#bbVignette)" pointerEvents="none" />

      {darts.map((d) => <Dart key={d.id} d={d} />)}

      {pops.map((p) => {
        const x = C + p.x * SCALE
        const y = C - p.y * SCALE - 22
        return (
          <text key={p.id} x={x} y={y} className="bb-pop" fontSize="32" fontWeight="800"
            textAnchor="middle" fill={p.color} stroke="#000" strokeWidth="1"
            style={{ paintOrder: 'stroke' }}>
            {p.text}
          </text>
        )
      })}

      <style>{`
        .bb-dart-enter {
          animation: bb-dart-in var(--dur, 560ms) cubic-bezier(0.2, 0.9, 0.3, 1) both;
        }
        @keyframes bb-dart-in {
          0%   { opacity: 0; transform: translateY(-150px) scale(3.6); filter: blur(5px); }
          55%  { opacity: 1; transform: translateY(0) scale(1.04); filter: blur(0); }
          70%  { transform: rotate(-4deg) scale(1); }
          85%  { transform: rotate(2.5deg); }
          100% { transform: rotate(0deg); }
        }
        .bb-shadow-in { animation: bb-fade var(--dur, 560ms) ease-out both; }
        @keyframes bb-fade { 0%, 50% { opacity: 0; } 100% { opacity: 1; } }
        .bb-impact {
          transform-box: fill-box; transform-origin: center;
          animation: bb-ring calc(var(--dur, 560ms) + 350ms) ease-out both;
        }
        @keyframes bb-ring {
          0%, 55% { opacity: 0; transform: scale(0.25); }
          70% { opacity: 0.9; }
          100% { opacity: 0; transform: scale(2.4); }
        }
        .bb-winglow {
          transform-box: fill-box; transform-origin: center;
          animation: bb-glow 1.1s ease-in-out 0.6s infinite;
        }
        @keyframes bb-glow {
          0%, 100% { opacity: 0.85; transform: scale(1); }
          50% { opacity: 0.25; transform: scale(1.5); }
        }
        .bb-pop { animation: bb-pop-rise 1.3s ease-out both; }
        @keyframes bb-pop-rise {
          0% { opacity: 0; transform: translateY(14px) scale(0.6); }
          18% { opacity: 1; transform: translateY(0) scale(1.12); }
          30% { transform: scale(1); }
          75% { opacity: 1; }
          100% { opacity: 0; transform: translateY(-18px); }
        }
        .bb-pop { transform-box: fill-box; transform-origin: center; }
      `}</style>
    </svg>
  )
}
