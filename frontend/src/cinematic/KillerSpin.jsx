// Killer pre-game: each player spins a dartboard-style wheel with a needle to
// pick their number. Humans click Spin; AI players auto-spin. Once everyone has
// a number the user clicks Start (or Respin). Reports the chosen numbers (one
// per player, in player order) via onConfirm.
import { useState, useEffect, useRef, useCallback } from 'react'
import { sound } from './audio'

// Standard dartboard order around the wheel (clockwise from the top).
const WHEEL = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
const SEG = 360 / WHEEL.length            // 18°
const COLORS = ['#e23b3b', '#1f8a4c', '#2e6fd6', '#8e44ad', '#e07b1a', '#159a8c',
  '#d63384', '#3a8f3a', '#c0392b', '#2980b9']

const C = 110
const R = 100
const rad = (d) => (d * Math.PI) / 180
const pt = (r, deg) => [C + r * Math.sin(rad(deg)), C - r * Math.cos(rad(deg))]

function sector(ro, t0, t1) {
  const [x0, y0] = pt(ro, t0)
  const [x1, y1] = pt(ro, t1)
  return `M${C},${C} L${x0},${y0} A${ro},${ro} 0 0 1 ${x1},${y1} Z`
}

export default function KillerSpin({ players = [], accent = '#f97316', onConfirm }) {
  const n = players.length
  const [assignments, setAssignments] = useState(() => Array(n).fill(null))
  const [rot, setRot] = useState(0)
  const [spinning, setSpinning] = useState(false)
  const timer = useRef(null)

  const current = assignments.findIndex((a) => a === null)
  const allDone = current === -1
  const taken = new Set(assignments.filter((a) => a !== null))

  const spin = useCallback(() => {
    if (spinning || current === -1) return
    const takenSet = new Set(assignments.filter((a) => a !== null))
    const pool = WHEEL.filter((num) => !takenSet.has(num))
    if (!pool.length) return
    const num = pool[Math.floor(Math.random() * pool.length)]
    const idx = WHEEL.indexOf(num)
    // Bring segment `idx` under the left-pointing needle (270° clockwise).
    const desired = ((270 - idx * SEG) % 360 + 360) % 360
    setRot((cur) => {
      const curMod = ((cur % 360) + 360) % 360
      const delta = (desired - curMod + 360) % 360
      const jitter = Math.random() * 10 - 5            // ±5° (inside the wedge)
      return cur + 360 * 4 + delta + jitter
    })
    setSpinning(true)
    sound.wheelSpin(3400)
    timer.current = setTimeout(() => {
      setSpinning(false)
      sound.ding()
      setAssignments((a) => a.map((v, i) => (i === current ? num : v)))
    }, 3500)
  }, [spinning, current, assignments])

  // AI players spin automatically when it's their turn.
  useEffect(() => {
    if (spinning || current === -1) return
    if (players[current]?.is_ai) {
      const t = setTimeout(spin, 900)
      return () => clearTimeout(t)
    }
  }, [current, spinning, players, spin])

  useEffect(() => () => clearTimeout(timer.current), [])

  const respin = () => {
    clearTimeout(timer.current)
    setSpinning(false)
    setAssignments(Array(n).fill(null))
  }

  const cur = current === -1 ? null : players[current]

  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center px-6 gap-5">
      <div className="text-xs font-bold tracking-[0.45em] uppercase cin-rise" style={{ color: accent }}>
        ★ Spin for your number
      </div>

      <div className="relative" style={{ width: 'min(46vh, 360px)', height: 'min(46vh, 360px)' }}>
        {/* Needle — left, pointing right into the wheel */}
        <svg viewBox="0 0 30 220" className="absolute -left-5 top-0 h-full" style={{ width: 34, overflow: 'visible' }}>
          <path d="M2,98 L26,110 L2,122 Z" fill={accent} stroke="#0a0d18" strokeWidth="2"
            style={{ filter: `drop-shadow(0 2px 6px ${accent}88)` }} />
        </svg>

        <svg viewBox="0 0 220 220" className="w-full h-full"
          style={{ filter: 'drop-shadow(0 20px 50px rgba(0,0,0,0.6))' }}>
          <circle cx={C} cy={C} r={R + 6} fill="#0a0d18" stroke="#2a2f3a" strokeWidth="3" />
          <g style={{
            transform: `rotate(${rot}deg)`, transformOrigin: '110px 110px',
            transition: spinning ? 'transform 3.5s cubic-bezier(0.18,0.66,0.16,1)' : 'none',
          }}>
            {WHEEL.map((num, i) => {
              const t0 = i * SEG - SEG / 2
              const t1 = i * SEG + SEG / 2
              const [tx, ty] = pt(R * 0.72, i * SEG)
              const dim = taken.has(num)
              return (
                <g key={num}>
                  <path d={sector(R, t0, t1)} fill={COLORS[i % COLORS.length]}
                    opacity={dim ? 0.25 : 1} stroke="#0a0d18" strokeWidth="0.8" />
                  <text x={tx} y={ty} fontSize="15" fontWeight="800" fill="#fff"
                    textAnchor="middle" dominantBaseline="central"
                    opacity={dim ? 0.4 : 1}
                    transform={`rotate(${i * SEG} ${tx} ${ty})`}>{num}</text>
                </g>
              )
            })}
          </g>
          {/* hub */}
          <circle cx={C} cy={C} r={20} fill="#f8fafc" stroke="#0a0d18" strokeWidth="3" />
          <circle cx={C} cy={C} r={6} fill={accent} />
        </svg>
      </div>

      {/* Player chips with their drawn number */}
      <div className="flex items-center justify-center gap-2 flex-wrap max-w-xl">
        {players.map((p, i) => (
          <span key={i} className={`px-3 py-1.5 rounded-full text-xs font-bold tracking-wide uppercase flex items-center gap-2 transition-all ${i === current && !allDone ? 'ring-2 ring-offset-0' : ''}`}
            style={{
              background: `${p.color}22`, color: p.color, border: `1px solid ${p.color}55`,
              boxShadow: i === current && !allDone ? `0 0 16px ${p.color}66` : 'none',
            }}>
            {p.name}
            <span className="tabular-nums font-black text-sm" style={{ color: assignments[i] != null ? '#fff' : `${p.color}88` }}>
              {assignments[i] != null ? assignments[i] : '—'}
            </span>
            {p.is_ai && <span className="text-[9px] opacity-60">AI</span>}
          </span>
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3 mt-1">
        {!allDone && cur && !cur.is_ai && (
          <button onClick={spin} disabled={spinning}
            className="cin-rules-go"
            style={{ background: `linear-gradient(180deg, ${accent}, ${accent}cc)`, boxShadow: `0 10px 30px ${accent}66`, opacity: spinning ? 0.6 : 1 }}>
            {spinning ? 'Spinning…' : `Spin · ${cur.name}`}
          </button>
        )}
        {!allDone && cur && cur.is_ai && (
          <div className="cin-chipbtn" style={{ pointerEvents: 'none' }}>
            {spinning ? `${cur.name} spinning…` : `${cur.name} (AI) up…`}
          </div>
        )}
        {allDone && (
          <>
            <button onClick={() => onConfirm?.(assignments)} className="cin-rules-go"
              style={{ background: `linear-gradient(180deg, ${accent}, ${accent}cc)`, boxShadow: `0 10px 30px ${accent}66` }}>
              Start game ▶
            </button>
            <button onClick={respin} className="cin-chipbtn">Respin</button>
          </>
        )}
      </div>
    </div>
  )
}
