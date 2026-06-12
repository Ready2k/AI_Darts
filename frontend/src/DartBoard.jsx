// Interactive dartboard: renders the standard board, plots the current visit's
// darts (board-mm positions), and — when `armed` — turns a click into a board
// coordinate so the last dart can be re-scored.
import { useRef, useEffect, useState } from 'react'

const SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

const SIZE = 360
const C = SIZE / 2
const R_OUT = 150            // px at the 170mm double-out ring
const SCALE = R_OUT / 170    // px per mm

const r = (mm) => mm * SCALE
const BULL = r(6.35)
const BULLS = r(15.9)
const TRB_IN = r(99)
const TRB_OUT = r(107)
const DBL_IN = r(162)

const COL = {
  single: (i) => (i % 2 === 0 ? '#17120c' : '#e9dcb5'),
  ring:   (i) => (i % 2 === 0 ? '#b4202a' : '#1c7a3e'),
}

const deg = (d) => (d * Math.PI) / 180
const pt = (rad, theta) => [C + rad * Math.sin(theta), C - rad * Math.cos(theta)]

function sector(ri, ro, t0, t1) {
  const [x0o, y0o] = pt(ro, t0)
  const [x1o, y1o] = pt(ro, t1)
  const [x1i, y1i] = pt(ri, t1)
  const [x0i, y0i] = pt(ri, t0)
  return `M${x0o},${y0o} A${ro},${ro} 0 0 1 ${x1o},${y1o} `
       + `L${x1i},${y1i} A${ri},${ri} 0 0 0 ${x0i},${y0i} Z`
}

export default function DartBoard({ darts = [], armed = false, onPick, className = "" }) {
  const ref = useRef(null)
  const [animatedDarts, setAnimatedDarts] = useState(new Set())
  const prevDartsCount = useRef(darts.length)

  useEffect(() => {
    if (darts.length > prevDartsCount.current) {
      const newSet = new Set(animatedDarts)
      for (let i = prevDartsCount.current; i < darts.length; i++) {
        newSet.add(i)
      }
      setAnimatedDarts(newSet)
    } else if (darts.length < prevDartsCount.current) {
      // If darts are cleared or undone, reset the animated darts set
      setAnimatedDarts(new Set())
    }
    prevDartsCount.current = darts.length
  }, [darts.length])

  const sectors = []
  for (let i = 0; i < 20; i++) {
    const t0 = deg(i * 18 - 9)
    const t1 = deg(i * 18 + 9)
    sectors.push(
      <g key={i}>
        <path d={sector(BULLS, TRB_IN, t0, t1)} fill={COL.single(i)} />
        <path d={sector(TRB_IN, TRB_OUT, t0, t1)} fill={COL.ring(i)} />
        <path d={sector(TRB_OUT, DBL_IN, t0, t1)} fill={COL.single(i)} />
        <path d={sector(DBL_IN, R_OUT, t0, t1)} fill={COL.ring(i)} />
      </g>
    )
  }

  const numbers = SEGMENTS.map((seg, i) => {
    const [x, y] = pt(R_OUT + 9, deg(i * 18))
    return (
      <text key={seg} x={x} y={y + 3.5} fontSize="11" fontWeight="600"
        textAnchor="middle" fill="#cbd5e1">{seg}</text>
    )
  })

  const handleClick = (e) => {
    if (!armed || !onPick) return
    const rect = ref.current.getBoundingClientRect()
    const vx = ((e.clientX - rect.left) / rect.width) * SIZE
    const vy = ((e.clientY - rect.top) / rect.height) * SIZE
    onPick((vx - C) / SCALE, (C - vy) / SCALE)
  }

  return (
    <svg ref={ref} viewBox={`0 0 ${SIZE} ${SIZE}`} onClick={handleClick}
      className={`w-full ${className || 'max-w-[360px]'} mx-auto ${armed ? 'cursor-crosshair' : ''}`}>
      <circle cx={C} cy={C} r={R_OUT + 20} fill="#0a0a0a" />
      {sectors}
      <circle cx={C} cy={C} r={BULLS} fill="#1c7a3e" />
      <circle cx={C} cy={C} r={BULL} fill="#b4202a" />
      {numbers}

      {darts.filter((d) => d.pos).map((d, i, arr) => {
        const last = i === arr.length - 1
        const [x, y] = [C + d.pos[0] * SCALE, C - d.pos[1] * SCALE]
        return (
          <g key={i} className={animatedDarts.has(i) ? 'animate-dart-throw' : ''}>
            <circle cx={x} cy={y} r="4.5" fill={last && armed ? '#22d3ee' : '#fafafa'}
              stroke="#000" strokeWidth="1.2" />
            <circle cx={x} cy={y} r="1.3" fill="#000" />
          </g>
        )
      })}

      {armed && (
        <text x={C} y={SIZE - 6} fontSize="11" textAnchor="middle" fill="#22d3ee">
          click to move the last dart
        </text>
      )}
    </svg>
  )
}
