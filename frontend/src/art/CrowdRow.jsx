// Flat-vector crowd silhouette — a row of darkened head/shoulder shapes with
// slight height variation, drawn as one band that sits behind the board stage.
// Pure SVG, no image assets. Rendered by CinematicGame as the visual partner to
// the audio crowd bed; a gentle idle sway lives on the inner group's CSS class
// (.cin-crowd-sway, defined in broadcastParts CSS), and the parent toggles
// .cin-crowd-react on big moments for a roar bounce.
//
//   <CrowdRow accent="#22d3ee" />
//
// `accent` tints a faint scattering of "lit" heads (phone lights / fans in
// team colours) so the band reads as a real arena crowd rather than a flat bar.

// Deterministic pseudo-random so the silhouette is identical every render
// (no hydration flicker, no layout shift).
const rnd = (i, salt) => {
  const x = Math.sin(i * 91.3 + salt * 47.7) * 9173.13
  return x - Math.floor(x)
}

// One head+shoulders silhouette centred at x, baseline at y, sized by `s`.
function Head({ x, y, s, fill }) {
  const r = 9 * s            // head radius
  const hy = y - 22 * s      // head centre height above the baseline
  return (
    <g fill={fill}>
      {/* shoulders */}
      <path d={`M${x - 18 * s},${y}
                Q${x - 16 * s},${hy + 8 * s} ${x},${hy + 9 * s}
                Q${x + 16 * s},${hy + 8 * s} ${x + 18 * s},${y} Z`} />
      {/* head */}
      <circle cx={x} cy={hy} r={r} />
    </g>
  )
}

export default function CrowdRow({ accent = '#22d3ee', count = 26, className = '' }) {
  const W = 1000
  const H = 120
  const baseline = H + 6          // shoulders run off the bottom edge
  const step = W / (count - 1)

  const heads = Array.from({ length: count }, (_, i) => {
    const jitterX = (rnd(i, 1) - 0.5) * step * 0.5
    const s = 0.9 + rnd(i, 2) * 0.5            // height variation
    const lift = rnd(i, 3) * 10                 // some sit slightly taller
    // A faint scatter of accent-lit fans (phone torches / team colours).
    const lit = rnd(i, 4) > 0.82
    return {
      x: i * step + jitterX,
      y: baseline - lift,
      s,
      // Front rows darker, a touch of depth via two tone bands.
      fill: lit ? accent : (i % 3 === 0 ? '#05060c' : '#0b0e18'),
      lit,
    }
  })

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMax slice"
      className={className} aria-hidden="true">
      {/* soft floor shadow under the band */}
      <rect x="0" y={H * 0.55} width={W} height={H} fill="#04050a" opacity="0.55" />
      {heads.map((h, i) => (
        <Head key={i} x={h.x} y={h.y} s={h.s} fill={h.fill} />
      ))}
      {/* faint glow dots on the lit heads for a phone-light shimmer */}
      {heads.filter((h) => h.lit).map((h, i) => (
        <circle key={`g${i}`} cx={h.x} cy={h.y - 22 * h.s} r={3 * h.s}
          fill={accent} opacity="0.8" />
      ))}
    </svg>
  )
}
