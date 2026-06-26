// Per-mode visual identity for the cinematic broadcast: accent colour, an
// emblem, a themed entrance class for the rules card, and the win-shot call.
// Keeps every game mode feeling distinct in the intro, the lower-third, and the
// win/lose moments. Consumed by CinematicGame + broadcastParts.

export const MODE_THEMES = {
  'X01': {
    accent: '#22d3ee',
    emblem: '🎯',
    label: 'X01',
    cls: 'th-x01',
    win: { text: 'GAME SHOT', sub: 'AND THE MATCH' },
    confetti: ['#22d3ee', '#7ff0ff', '#f8fafc', '#fbbf24'],
    // winScene: the win-moment finale descriptor. `replay` enables the slow-mo
    // zoom on the winning dart; `headline`/`sub` set the winner-card crown text.
    winScene: { replay: true, headline: 'GAME SHOT', sub: 'AND THE MATCH', crown: 'CHAMPION' },
  },
  'Cricket': {
    accent: '#34d399',
    emblem: '🦗',
    label: 'Cricket',
    cls: 'th-cricket',
    win: { text: 'GAME SHOT', sub: 'CLOSED OUT' },
    confetti: ['#34d399', '#a7f3d0', '#f8fafc', '#fbbf24'],
    winScene: { replay: true, headline: 'CLOSED OUT', sub: 'EVERY NUMBER SHUT', crown: 'CHAMPION' },
  },
  'Around the Clock': {
    accent: '#fbbf24',
    emblem: '🕛',
    label: 'Around the Clock',
    cls: 'th-clock',
    win: { text: 'FULL CLOCK', sub: 'ROUND THE WORLD' },
    confetti: ['#fbbf24', '#fde68a', '#f8fafc', '#22d3ee'],
    winScene: { replay: true, headline: 'FULL CLOCK', sub: 'ROUND THE WORLD', crown: 'CHAMPION' },
  },
  'Shanghai': {
    accent: '#fb7185',
    emblem: '🏮',
    label: 'Shanghai',
    cls: 'th-shanghai',
    win: { text: 'GAME SHOT', sub: 'TOP OF THE TABLE' },
    confetti: ['#fb7185', '#fecdd3', '#f8fafc', '#fbbf24'],
    winScene: { replay: true, headline: 'TOP OF THE TABLE', sub: 'HIGHEST TALLY', crown: 'CHAMPION' },
  },
  'Count Up': {
    accent: '#a78bfa',
    emblem: '📈',
    label: 'Count Up',
    cls: 'th-countup',
    win: { text: 'TOP SCORE', sub: 'HIGHEST WINS' },
    confetti: ['#a78bfa', '#ddd6fe', '#f8fafc', '#34d399'],
    winScene: { replay: true, headline: 'TOP SCORE', sub: 'HIGHEST TALLY WINS', crown: 'CHAMPION' },
  },
  'Killer': {
    accent: '#f97316',
    emblem: '💀',
    label: 'Killer',
    cls: 'th-killer',
    win: { text: 'LAST ONE STANDING', sub: 'WINNER' },
    confetti: ['#f97316', '#fdba74', '#f8fafc', '#ef4444'],
    winScene: { replay: true, headline: 'LAST ONE STANDING', sub: 'THE SOLE SURVIVOR', crown: 'SURVIVOR' },
  },
}

// Resolve a mode's win-scene descriptor, with an X01 fallback.
export const winSceneFor = (mode) =>
  (MODE_THEMES[mode] || MODE_THEMES['X01']).winScene || MODE_THEMES['X01'].winScene

export const themeFor = (mode) => MODE_THEMES[mode] || MODE_THEMES['X01']

// ── Venues ──────────────────────────────────────────────────────────────────
// A venue re-skins the arena backdrop (the cin-bg gradient + the two roving
// cin-spot tints) by setting CSS custom properties on the cinematic root. Each
// venue is just a bag of CSS vars + a label, so a venue picker can be wired up
// later without touching the stylesheet. `vars` is spread straight onto the
// root container's inline style in CinematicGame.
export const VENUES = {
  allyPally: {
    label: 'Ally Pally',
    vars: {
      '--cin-bg-1': '#16412e',   // deep championship green
      '--cin-bg-2': '#08160f',
      '--cin-bg-3': '#030705',
      '--cin-spot-a': 'rgba(120,255,180,0.10)',
      '--cin-spot-b': 'rgba(255,235,140,0.07)',
      '--cin-spot-c': 'rgba(120,255,200,0.06)',
    },
  },
  vegasNeon: {
    label: 'Vegas Neon',
    vars: {
      '--cin-bg-1': '#3a1052',   // electric purple
      '--cin-bg-2': '#140822',
      '--cin-bg-3': '#06030c',
      '--cin-spot-a': 'rgba(255,120,235,0.12)',
      '--cin-spot-b': 'rgba(120,200,255,0.10)',
      '--cin-spot-c': 'rgba(255,210,120,0.07)',
    },
  },
  smokyPub: {
    label: 'Smoky Pub',
    vars: {
      '--cin-bg-1': '#4a3a22',   // warm amber haze
      '--cin-bg-2': '#1b150c',
      '--cin-bg-3': '#0a0805',
      '--cin-spot-a': 'rgba(255,200,120,0.10)',
      '--cin-spot-b': 'rgba(255,150,90,0.07)',
      '--cin-spot-c': 'rgba(200,160,110,0.06)',
    },
  },
  bluesArena: {
    label: 'Blues Arena',
    vars: {
      '--cin-bg-1': '#222b4d',   // the original deep-blue stage
      '--cin-bg-2': '#0a0d18',
      '--cin-bg-3': '#04050a',
      '--cin-spot-a': 'rgba(125,170,255,0.10)',
      '--cin-spot-b': 'rgba(255,130,180,0.08)',
      '--cin-spot-c': 'rgba(160,255,220,0.06)',
    },
  },
}

// Default venue per game mode. Sensible thematic pairings; no settings UI yet —
// a picker can override this later by passing a venue key into venueFor's caller.
const MODE_VENUE = {
  'X01': 'allyPally',
  'Cricket': 'bluesArena',
  'Around the Clock': 'vegasNeon',
  'Shanghai': 'vegasNeon',
  'Count Up': 'smokyPub',
  'Killer': 'smokyPub',
}

// Resolve a venue: explicit key wins, else the mode default, else Ally Pally.
export const venueFor = (mode, key) =>
  VENUES[key] || VENUES[MODE_VENUE[mode]] || VENUES.allyPally

// CSS for the themed rules-card emblem entrances + win flourishes. Appended to
// the shared cin-* stylesheet (see broadcastParts CSS).
export const THEME_CSS = `
.th-emblem { font-size:clamp(46px, 9vw, 84px); line-height:1; margin-bottom:6px;
  filter: drop-shadow(0 6px 18px rgba(0,0,0,.5)); display:inline-block; }
.th-x01     .th-emblem { animation: th-pulse 1.8s ease-in-out infinite; }
.th-cricket .th-emblem { animation: th-hop 1.4s ease-in-out infinite; }
.th-clock   .th-emblem { animation: th-spin 6s linear infinite; }
.th-shanghai .th-emblem { animation: th-sway 2.4s ease-in-out infinite; transform-origin:50% 0; }
.th-countup .th-emblem { animation: th-rise 1.8s ease-in-out infinite; }
.th-killer  .th-emblem { animation: th-shake 2.2s ease-in-out infinite; }
@keyframes th-pulse { 0%,100%{ transform:scale(1);} 50%{ transform:scale(1.14);} }
@keyframes th-hop   { 0%,100%{ transform:translateY(0) rotate(-4deg);} 50%{ transform:translateY(-12px) rotate(4deg);} }
@keyframes th-spin  { to { transform:rotate(360deg);} }
@keyframes th-sway  { 0%,100%{ transform:rotate(-9deg);} 50%{ transform:rotate(9deg);} }
@keyframes th-rise  { 0%,100%{ transform:translateY(4px) scale(.98);} 50%{ transform:translateY(-8px) scale(1.06);} }
@keyframes th-shake { 0%,92%,100%{ transform:translateX(0) rotate(0);} 94%{ transform:translateX(-4px) rotate(-6deg);} 96%{ transform:translateX(4px) rotate(6deg);} 98%{ transform:translateX(-3px) rotate(-4deg);} }

.cin-elim { font-size:clamp(54px, 12vw, 150px); font-weight:900; line-height:.9; text-align:center;
  color:#fff; -webkit-text-stroke:2px #ef4444;
  text-shadow:0 0 36px rgba(239,68,68,.7);
  animation: cin-elim-in .5s cubic-bezier(.2,1.5,.3,1) both; }
.cin-elim-sub { margin-top:8px; font-weight:800; letter-spacing:.4em; text-align:center;
  color:#fecaca; font-size:clamp(12px,1.6vw,20px); animation: cin-up .5s .15s both; }
@keyframes cin-elim-in { 0%{ opacity:0; transform:scale(2.6) rotate(-8deg);} 60%{ opacity:1; transform:scale(.94) rotate(2deg);} 100%{ transform:scale(1) rotate(0);} }
`
