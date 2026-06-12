// Flat-vector caricature players — big head, tiny body, bold flat colours.
// Replaces the old AI sprite sheets. Pure SVG so it scales, recolours and poses.
//
//   <Caricature variant="pubguy" pose="aim" shirt="#fb7185" framing="full" />
//
// poses: idle | aim | throw | celebrate | defeated
// framing: 'full' (whole body) | 'bust' (head & shoulders, for chips/pickers)

const SKIN_SHADE = 'rgba(0,0,0,0.12)'

const VARIANTS = {
  pubguy: {
    skin: '#eec39a',
    shirt: '#3e7a4f',
    hairColor: '#7d6648',
    beard: '#8a6442',
  },
  ninja: {
    skin: '#e8b88d',
    shirt: '#334155',
    cloth: '#1f2a44',
  },
  cyberpunk: {
    skin: '#f2c9a0',
    shirt: '#0e7490',
    hawk: '#a855f7',
  },
  wizard: {
    skin: '#f0c9a4',
    shirt: '#6d28d9',
    beard: '#ece8e1',
    hat: '#5b21b6',
  },
  viking: {
    skin: '#d4956a',
    shirt: '#5c4a2a',
    hairColor: '#c49a3c',
    beard: '#b8842a',
  },
  cowboy: {
    skin: '#d4956a',
    shirt: '#8b4513',
    hatColor: '#b8870b',
  },
  rockstar: {
    skin: '#f0d4b0',
    shirt: '#1a1a2e',
    hairColor: '#1a1a1a',
  },
  posh: {
    skin: '#f5e6d3',
    shirt: '#0a0a2a',
    hatColor: '#0f0f1f',
  },
}

function Hair({ variant, v }) {
  switch (variant) {
    case 'pubguy': // flat cap
      return (
        <g>
          <path d="M40,80 Q100,18 160,80 Q100,54 40,80 Z" fill={v.hairColor} />
          <ellipse cx="100" cy="79" rx="52" ry="9" fill={v.hairColor} />
          <ellipse cx="100" cy="77" rx="52" ry="8" fill="rgba(0,0,0,0.2)" />
        </g>
      )
    case 'ninja': // hood + headband, knot tails
      return (
        <g>
          <path d="M36,84 Q100,10 164,84 Q100,48 36,84 Z" fill={v.cloth} />
          <path d="M40,74 Q100,52 160,74 L160,90 Q100,68 40,90 Z" fill="#e7e9ee" />
          <path d="M156,84 q22,0 28,16 q-16,-3 -23,-9 Z" fill="#e7e9ee" />
          <path d="M158,90 q18,10 18,26 q-14,-8 -20,-18 Z" fill="#cfd4dd" />
        </g>
      )
    case 'cyberpunk': // mohawk + shaved sides
      return (
        <g>
          <path d="M40,84 Q100,40 160,84 Q100,66 40,84 Z" fill="#3b3b40" opacity="0.5" />
          <path d="M68,56 L80,14 L88,52 L100,6 L112,52 L120,14 L132,56 Q100,42 68,56 Z" fill={v.hawk} />
        </g>
      )
    case 'wizard': // pointy hat
      return (
        <g>
          <path d="M100,-2 L144,74 Q100,58 56,74 Z" fill={v.hat} />
          <path d="M56,72 Q100,56 144,72 L148,82 Q100,64 52,82 Z" fill="#7c3aed" />
          <path d="M104,28 l3,7 7,1 -5,5 1,7 -6,-4 -6,4 1,-7 -5,-5 7,-1 Z" fill="#fbbf24" />
        </g>
      )
    case 'viking': // iron helmet + blonde braids
      return (
        <g>
          <ellipse cx="100" cy="66" rx="64" ry="45" fill="#8892a0" />
          <path d="M34,84 Q100,74 166,84 L164,96 Q100,86 36,96 Z" fill="#68758a" />
          <rect x="97" y="84" width="6" height="28" rx="3" fill="#68758a" />
          <path d="M36,92 Q16,126 18,166 Q18,180 14,192" stroke={v.hairColor} strokeWidth="13" fill="none" strokeLinecap="round" />
          <path d="M164,92 Q184,126 182,166 Q182,180 186,192" stroke={v.hairColor} strokeWidth="13" fill="none" strokeLinecap="round" />
        </g>
      )
    case 'cowboy': // Stetson + red bandana
      return (
        <g>
          <path d="M66,76 L68,32 Q100,14 132,32 L134,76 Q100,64 66,76 Z" fill={v.hatColor} />
          <path d="M66,76 L68,40 Q100,28 132,40 L130,76 Q100,65 70,76 Z" fill="rgba(0,0,0,0.16)" />
          <path d="M18,78 Q52,92 66,78 Q100,66 134,78 Q148,92 182,78 Q158,100 100,96 Q42,100 18,78 Z" fill={v.hatColor} />
          <path d="M66,76 Q100,66 134,76 L133,82 Q100,72 67,82 Z" fill="rgba(0,0,0,0.32)" />
          <path d="M72,154 L100,172 L128,154 Q124,146 100,150 Q76,146 72,154 Z" fill="#c41e3a" />
        </g>
      )
    case 'rockstar': // long black hair + red headband
      return (
        <g>
          <path d="M38,90 Q10,132 8,178 Q10,208 8,228" stroke={v.hairColor} strokeWidth="30" fill="none" strokeLinecap="round" />
          <path d="M162,90 Q190,132 192,178 Q190,208 192,228" stroke={v.hairColor} strokeWidth="30" fill="none" strokeLinecap="round" />
          <path d="M38,88 Q100,22 162,88 Q100,48 38,88 Z" fill={v.hairColor} />
          <path d="M38,92 Q100,74 162,92 L160,100 Q100,82 40,100 Z" fill="#dc2626" />
        </g>
      )
    case 'posh': // top hat + silver temples
      return (
        <g>
          <path d="M38,84 Q28,96 30,112" stroke="#b8bcc4" strokeWidth="16" fill="none" strokeLinecap="round" />
          <path d="M162,84 Q172,96 170,112" stroke="#b8bcc4" strokeWidth="16" fill="none" strokeLinecap="round" />
          <path d="M28,76 Q100,66 172,76 L170,88 Q100,78 30,88 Z" fill={v.hatColor} />
          <rect x="57" y="12" width="86" height="64" rx="3" fill={v.hatColor} />
          <ellipse cx="100" cy="14" rx="43" ry="8" fill={v.hatColor} />
          <rect x="57" y="66" width="86" height="10" rx="2" fill="#3b3b8f" />
          <rect x="61" y="16" width="5" height="46" rx="2.5" fill="rgba(255,255,255,0.12)" />
        </g>
      )
    default:
      return null
  }
}

function Face({ variant, v, pose }) {
  const sad = pose === 'defeated'
  const shout = pose === 'celebrate'

  // Eyes / brows
  let eyes
  if (variant === 'cyberpunk') {
    eyes = (
      <g>
        <rect x="56" y="76" width="88" height="22" rx="11" fill="#101216" />
        <line x1="66" y1="83" x2="92" y2="83" stroke="#22d3ee" strokeWidth="3" strokeLinecap="round" opacity="0.9" />
        <circle cx="166" cy="118" r="4" fill="#fbbf24" />
      </g>
    )
  } else if (variant === 'rockstar') {
    eyes = (
      <g>
        <rect x="52" y="76" width="96" height="26" rx="13" fill="#0f172a" />
        <rect x="96" y="80" width="8" height="18" rx="3" fill="#1e293b" />
        <ellipse cx="74" cy="83" rx="11" ry="5" fill="rgba(255,255,255,0.1)" />
        <ellipse cx="126" cy="83" rx="11" ry="5" fill="rgba(255,255,255,0.1)" />
        <path d="M52,78 Q100,72 148,78" stroke="rgba(255,255,255,0.15)" strokeWidth="2" fill="none" />
      </g>
    )
  } else if (variant === 'posh') {
    eyes = (
      <g>
        <ellipse cx="78" cy="86" rx="5.5" ry="7" fill="#27241f" />
        <path d="M68,72 Q78,67 88,72" stroke="#27241f" strokeWidth="4.5" fill="none" strokeLinecap="round" />
        <circle cx="122" cy="86" r="14" fill="none" stroke="#d4af37" strokeWidth="2.5" />
        <ellipse cx="122" cy="86" rx="5.5" ry="7" fill="#27241f" />
        <path d="M112,72 Q122,67 132,72" stroke="#27241f" strokeWidth="4.5" fill="none" strokeLinecap="round" />
        <path d="M135,93 Q142,106 144,118" stroke="#d4af37" strokeWidth="2" fill="none" strokeDasharray="3,2" />
      </g>
    )
  } else if (sad) {
    eyes = (
      <g>
        <path d="M70,88 Q78,82 86,88" stroke="#27241f" strokeWidth="4" fill="none" strokeLinecap="round" />
        <path d="M114,88 Q122,82 130,88" stroke="#27241f" strokeWidth="4" fill="none" strokeLinecap="round" />
        <path d="M66,76 L88,82" stroke="#27241f" strokeWidth="4" strokeLinecap="round" />
        <path d="M134,76 L112,82" stroke="#27241f" strokeWidth="4" strokeLinecap="round" />
      </g>
    )
  } else {
    eyes = (
      <g>
        <ellipse cx="78" cy="86" rx="5.5" ry="7" fill="#27241f" />
        <ellipse cx="122" cy="86" rx="5.5" ry="7" fill="#27241f" />
        <path d="M68,72 Q78,67 88,72" stroke="#27241f" strokeWidth="4.5" fill="none" strokeLinecap="round" />
        <path d="M112,72 Q122,67 132,72" stroke="#27241f" strokeWidth="4.5" fill="none" strokeLinecap="round" />
      </g>
    )
  }

  // Lower face: beard / mask / mouth
  let lower
  if (variant === 'ninja') {
    lower = <path d="M44,110 Q100,132 156,110 L150,142 Q100,170 50,142 Z" fill={v.cloth} />
  } else {
    const beard =
      variant === 'pubguy'   ? <path d="M48,104 Q100,126 152,104 Q154,168 100,178 Q46,168 48,104 Z" fill={v.beard} /> :
      variant === 'wizard'   ? <path d="M46,104 Q100,128 154,104 Q160,196 100,210 Q40,196 46,104 Z" fill={v.beard} /> :
      variant === 'viking'   ? <path d="M40,108 Q100,130 160,108 Q166,192 100,206 Q34,192 40,108 Z" fill={v.beard} /> :
      variant === 'rockstar' ? <path d="M88,126 Q100,148 112,126 L114,150 Q100,160 86,150 Z" fill={v.hairColor} /> :
      variant === 'posh' ? (
        <g>
          <path d="M82,118 Q91,112 100,118" stroke="#5a4030" strokeWidth="4.5" fill="none" strokeLinecap="round" />
          <path d="M100,118 Q109,112 118,118" stroke="#5a4030" strokeWidth="4.5" fill="none" strokeLinecap="round" />
          <path d="M82,118 Q77,113 73,110" stroke="#5a4030" strokeWidth="3" fill="none" strokeLinecap="round" />
          <path d="M118,118 Q123,113 127,110" stroke="#5a4030" strokeWidth="3" fill="none" strokeLinecap="round" />
        </g>
      ) :
      null
    const mouth = shout
      ? <ellipse cx="100" cy="130" rx="13" ry="15" fill="#5e2222" />
      : sad
        ? <path d="M88,134 Q100,124 112,134" stroke="#3a2c20" strokeWidth="4.5" fill="none" strokeLinecap="round" />
        : <path d="M86,124 Q100,138 114,124" stroke="#3a2c20" strokeWidth="4.5" fill="none" strokeLinecap="round" />
    lower = (
      <g>
        {beard}
        <ellipse cx="100" cy="106" rx="7" ry="9" fill={SKIN_SHADE} />
        {mouth}
        {shout && <ellipse cx="100" cy="137" rx="7" ry="5" fill="#c2566b" />}
      </g>
    )
  }

  return (
    <g>
      {eyes}
      {lower}
      {!sad && variant !== 'ninja' && variant !== 'cyberpunk' && variant !== 'rockstar' && (
        <g opacity="0.35">
          <circle cx="62" cy="106" r="7" fill="#e58b8b" />
          <circle cx="138" cy="106" r="7" fill="#e58b8b" />
        </g>
      )}
    </g>
  )
}

// A tiny dart drawn along +y: flight at (0,0), tip at (0,30).
export function MiniDart({ x = 0, y = 0, rot = 0, scale = 1, flight = '#ef4444' }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${rot}) scale(${scale})`}>
      <path d="M0,0 L5,8 L0,12 L-5,8 Z" fill={flight} />
      <line x1="0" y1="10" x2="0" y2="20" stroke="#39404a" strokeWidth="3" strokeLinecap="round" />
      <line x1="0" y1="18" x2="0" y2="30" stroke="#aab2bd" strokeWidth="2" strokeLinecap="round" />
    </g>
  )
}

function Arms({ pose, shirt, skin, flight }) {
  const sleeve = { stroke: shirt, strokeWidth: 18, fill: 'none', strokeLinecap: 'round' }
  const fore = { stroke: skin, strokeWidth: 12, fill: 'none', strokeLinecap: 'round' }

  const idleLeft = (
    <g>
      <path d="M64,176 Q54,196 56,210" {...sleeve} />
      <path d="M56,210 Q57,224 58,230" {...fore} />
      <circle cx="58" cy="234" r="8" fill={skin} />
    </g>
  )
  const idleRight = (
    <g>
      <path d="M136,176 Q146,196 144,210" {...sleeve} />
      <path d="M144,210 Q143,224 142,230" {...fore} />
      <circle cx="142" cy="234" r="8" fill={skin} />
      <MiniDart x={148} y={232} rot={20} flight={flight} />
    </g>
  )

  switch (pose) {
    case 'aim':
      return (
        <g>
          {idleLeft}
          <path d="M136,176 Q158,174 160,158" {...sleeve} />
          <path d="M160,158 Q154,140 140,132" {...fore} />
          <circle cx="136" cy="128" r="8" fill={skin} />
          <MiniDart x={134} y={124} rot={102} flight={flight} />
        </g>
      )
    case 'throw':
      return (
        <g>
          {idleLeft}
          <path d="M136,174 L160,168" {...sleeve} />
          <path d="M160,168 L184,160" {...fore} />
          <circle cx="190" cy="158" r="8" fill={skin} />
        </g>
      )
    case 'celebrate':
      return (
        <g>
          <path d="M64,174 Q44,156 42,134" {...sleeve} />
          <path d="M42,134 Q44,118 50,108" {...fore} />
          <circle cx="52" cy="102" r="8" fill={skin} />
          <path d="M136,174 Q156,156 158,134" {...sleeve} />
          <path d="M158,134 Q156,118 150,108" {...fore} />
          <circle cx="148" cy="102" r="8" fill={skin} />
          <MiniDart x={148} y={98} rot={180} flight={flight} />
        </g>
      )
    case 'defeated':
      return (
        <g>
          <path d="M64,176 L60,208" {...sleeve} />
          <path d="M60,208 L60,232" {...fore} />
          <circle cx="60" cy="236" r="8" fill={skin} />
          <path d="M136,176 L140,208" {...sleeve} />
          <path d="M140,208 L140,232" {...fore} />
          <circle cx="140" cy="236" r="8" fill={skin} />
        </g>
      )
    default:
      return <g>{idleLeft}{idleRight}</g>
  }
}

export default function Caricature({
  variant = 'pubguy', pose = 'idle', shirt, flight = '#ef4444',
  bg = null, framing = 'full', className = '', style = {},
}) {
  const v = VARIANTS[variant] || VARIANTS.pubguy
  const shirtCol = shirt || v.shirt
  const viewBox = framing === 'bust' ? '26 8 148 158' : '0 0 200 284'
  const grayed = pose === 'defeated'

  return (
    <svg viewBox={viewBox} className={className}
      style={{ ...style, ...(grayed ? { filter: 'grayscale(0.9) brightness(0.75)' } : {}) }}>
      {bg && <rect x="-40" y="-40" width="280" height="364" rx="36" fill={bg} />}

      {framing === 'full' && <ellipse cx="100" cy="272" rx="56" ry="8" fill="rgba(0,0,0,0.25)" />}

      {/* legs + shoes */}
      <rect x="76" y="226" width="20" height="36" rx="9" fill="#23272e" />
      <rect x="104" y="226" width="20" height="36" rx="9" fill="#23272e" />
      <ellipse cx="83" cy="266" rx="15" ry="7" fill="#191b1f" />
      <ellipse cx="117" cy="266" rx="15" ry="7" fill="#191b1f" />

      {/* neck + torso */}
      <rect x="90" y="140" width="20" height="34" fill={v.skin} />
      <path d="M62,168 Q100,156 138,168 L144,234 Q100,246 56,234 Z" fill={shirtCol} />
      {/* polo collar + buttons */}
      <path d="M88,165 L100,184 L112,165 L104,162 L100,172 L96,162 Z" fill="rgba(255,255,255,0.85)" />
      <circle cx="100" cy="190" r="2.2" fill="rgba(0,0,0,0.35)" />
      <circle cx="100" cy="199" r="2.2" fill="rgba(0,0,0,0.35)" />
      <path d="M56,234 Q100,246 144,234 L143,228 Q100,240 57,228 Z" fill="rgba(0,0,0,0.18)" />

      <Arms pose={pose} shirt={shirtCol} skin={v.skin} flight={flight} />

      {/* head */}
      <circle cx="38" cy="96" r="9" fill={v.skin} />
      <circle cx="162" cy="96" r="9" fill={v.skin} />
      <ellipse cx="100" cy="92" rx="62" ry="58" fill={v.skin} />
      <Face variant={variant} v={v} pose={pose} />
      <Hair variant={variant} v={v} />
    </svg>
  )
}

// Small flat accessory icons for the blister-pack player cards (viewBox 0 0 60 60).
export function Accessory({ type, color = '#ef4444' }) {
  switch (type) {
    case 'darts':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <MiniDart x={20} y={12} rot={8} scale={1.2} flight={color} />
          <MiniDart x={31} y={10} rot={0} scale={1.2} flight={color} />
          <MiniDart x={42} y={12} rot={-8} scale={1.2} flight={color} />
        </svg>
      )
    case 'trophy':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <path d="M18,10 h24 v10 a12,12 0 0 1 -24,0 Z" fill="#fbbf24" />
          <path d="M18,12 h-8 a8,8 0 0 0 8,10 Z M42,12 h8 a8,8 0 0 1 -8,10 Z" fill="#fbbf24" />
          <rect x="26" y="30" width="8" height="10" fill="#d97706" />
          <rect x="18" y="40" width="24" height="7" rx="2" fill="#92400e" />
        </svg>
      )
    case 'pint':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <path d="M20,14 L24,50 h12 L40,14 Z" fill="#f59e0b" opacity="0.9" />
          <path d="M19,10 h22 l-1.5,9 h-19 Z" fill="#fef3c7" />
          <circle cx="24" cy="9" r="4" fill="#fef3c7" />
          <circle cx="32" cy="7" r="5" fill="#fef3c7" />
          <circle cx="39" cy="10" r="3.5" fill="#fef3c7" />
        </svg>
      )
    case 'shuriken':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <path d="M30,6 L36,24 L54,30 L36,36 L30,54 L24,36 L6,30 L24,24 Z" fill="#475569" />
          <circle cx="30" cy="30" r="5" fill="#1e293b" />
        </svg>
      )
    case 'axe':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <rect x="28" y="6" width="6" height="46" rx="3" fill="#7c5c3e" />
          <path d="M34,10 Q52,16 52,30 Q52,44 34,50 L34,10 Z" fill={color} />
          <path d="M50,18 Q54,30 50,42" stroke="rgba(255,255,255,0.3)" strokeWidth="2" fill="none" strokeLinecap="round" />
        </svg>
      )
    case 'guitar':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <ellipse cx="30" cy="43" rx="15" ry="12" fill={color} />
          <ellipse cx="30" cy="28" rx="10" ry="8" fill={color} />
          <rect x="22" y="26" width="16" height="19" fill={color} />
          <path d="M22,27 Q16,36 22,46" stroke="rgba(0,0,0,0.3)" strokeWidth="3" fill="none" />
          <path d="M38,27 Q44,36 38,46" stroke="rgba(0,0,0,0.3)" strokeWidth="3" fill="none" />
          <rect x="28" y="8" width="4" height="20" rx="2" fill="#d4a06a" />
          <circle cx="30" cy="40" r="5" fill="rgba(0,0,0,0.35)" />
          <line x1="28" y1="24" x2="28" y2="48" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
          <line x1="30" y1="24" x2="30" y2="48" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
          <line x1="32" y1="24" x2="32" y2="48" stroke="rgba(255,255,255,0.45)" strokeWidth="1" />
        </svg>
      )
    case 'crown':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <path d="M10,42 L10,20 L20,32 L30,12 L40,32 L50,20 L50,42 Z" fill={color} />
          <rect x="10" y="42" width="40" height="8" rx="2" fill={color} />
          <circle cx="20" cy="38" r="4" fill="rgba(255,255,255,0.9)" />
          <circle cx="30" cy="35" r="4" fill="rgba(255,255,255,0.9)" />
          <circle cx="40" cy="38" r="4" fill="rgba(255,255,255,0.9)" />
        </svg>
      )
    case 'horseshoe':
      return (
        <svg viewBox="0 0 60 60" className="w-full h-full">
          <path d="M18,52 L18,28 Q18,10 30,10 Q42,10 42,28 L42,52"
            stroke={color} strokeWidth="10" fill="none" strokeLinecap="round" />
          <circle cx="18" cy="48" r="5" fill={color} />
          <circle cx="42" cy="48" r="5" fill={color} />
        </svg>
      )
    default:
      return null
  }
}
