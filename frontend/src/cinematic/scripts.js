// All scripted match scenarios. Each object has the same shape as script.js.
// CinematicDemo picks one at random each time the demo is launched.

import { MATCH as M0, PLAYERS as P0, VISITS as V0, matchStats as ms0 } from './script'

const SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
const at = (seg, r, dDeg = 0, dR = 0) => {
  const a = ((SEGMENTS.indexOf(seg) * 18 + dDeg) * Math.PI) / 180
  return [Math.sin(a) * (r + dR), Math.cos(a) * (r + dR)]
}
const makeStats = (players, visits) => () => {
  const s = players.map(() => ({ pts: 0, darts: 0, maxima: 0 }))
  for (const v of visits) {
    s[v.p].pts += v.total
    s[v.p].darts += v.darts.length
    if (v.total === 180) s[v.p].maxima += 1
  }
  return s.map((x) => ({ ...x, avg: x.darts ? (3 * x.pts) / x.darts : 0 }))
}


const NUMBER_CALLS = {
  26: 'Twenty-six.',
  41: 'Forty-one.',
  60: 'Sixty.',
  83: 'Eighty-three.',
  84: 'Eighty-four.',
  97: 'Ninety-seven.',
  112: 'One hundred and twelve.',
  117: 'One hundred and seventeen.',
  118: 'One hundred and eighteen.',
  121: 'One hundred and twenty-one.',
  124: 'One hundred and twenty-four.',
  126: 'One hundred and twenty-six.',
  128: 'One hundred and twenty-eight.',
  135: 'One hundred and thirty-five.',
  140: 'One hundred and forty.',
  141: 'One hundred and forty-one.',
  149: 'One hundred and forty-nine.',
  150: 'One hundred and fifty.',
  157: 'One hundred and fifty-seven.',
  171: 'One hundred and seventy-one.',
  177: 'One hundred and seventy-seven.',
}

const ANNOUNCER = {
  // Display can be theatrical. TTS absolutely cannot. It will read the extra letters
  // because apparently machines respect spelling more than showmanship.
  max180Display: 'Onnnne HUNDRED and EIGHTYYY!',
  max180Speech: 'One hundred and eighty!',
  // Optional SSML if the frontend/TTS provider supports it. Google voices usually do.
  max180Ssml: '<speak><prosody rate="slow" pitch="+2st">One hundred</prosody><break time="120ms"/><prosody rate="slow" pitch="+4st">and eighty</prosody></speak>',
}

const callForTotal = (total, extra = '') => {
  if (total === 180) return extra ? `${ANNOUNCER.max180Speech} ${extra}` : ANNOUNCER.max180Speech
  return NUMBER_CALLS[total] || `${total}.`
}

const displayCallForTotal = (total, extra = '') => {
  if (total === 180) return extra ? `${ANNOUNCER.max180Display} ${extra}` : ANNOUNCER.max180Display
  return callForTotal(total, extra)
}

const speechCallForTotal = (total, extra = '') => {
  if (total === 180) return extra ? `${ANNOUNCER.max180Speech} ${extra}` : ANNOUNCER.max180Speech
  return callForTotal(total, extra)
}

const max180 = (extra = '') => ({
  big: '180',
  // Keep call speech-safe because many components/TTS hooks read visit.call directly.
  call: speechCallForTotal(180, extra),
  // Components can render this for the proper shouty TV darts look.
  displayCall: displayCallForTotal(180, extra),
  // TTS should prefer this, or ssmlCall if SSML is supported.
  speechCall: speechCallForTotal(180, extra),
  ssmlCall: ANNOUNCER.max180Ssml,
  audioCue: 'one-hundred-and-eighty',
})

const extract180Extra = (call = '') => call
  .replace(/^(On+n+e\s+HUNDRED\s+and\s+EIGHTY+!|ONE HUNDRED AND EIGHTY!|One hundred and eighty!)/i, '')
  .trim()

// Safety net: imported or future scripts cannot accidentally make Google voice read stretched text.
const normaliseScript = (script) => ({
  ...script,
  VISITS: script.VISITS.map((visit) => (
    visit.total === 180 ? { ...visit, ...max180(extract180Extra(visit.displayCall || visit.call)) } : visit
  )),
})

// ── 0: Original — Marcus Bell vs Kai Tanaka ─────────────────────────────────
const script0 = { MATCH: M0, PLAYERS: P0, VISITS: V0, matchStats: ms0 }

// ── 1: Erik "The Viking" Svensson vs Merlin "The Wizard" Blackwood ──────────
// Wizard lands two 180s and a clinical 141 checkout while Viking's power game implodes.
const P1 = [
  {
    name: 'Erik Svensson', nick: 'The Viking', tag: 'ES',
    variant: 'viking', color: '#f97316', cardBg: '#7c3f1e',
    accessories: ['darts', 'axe', 'trophy'],
    bio: 'Career average 94.2 · 8 tour titles · Hardest thrower on the circuit',
    announce: 'All the way from Uppsala... Erik, The Viking, Svensson!',
  },
  {
    name: 'Merlin Blackwood', nick: 'The Wizard', tag: 'MB',
    variant: 'wizard', color: '#a78bfa', cardBg: '#3b0764',
    accessories: ['darts', 'crown', 'trophy'],
    bio: 'Career average 101.3 · 22 ranking titles · The most precise arm in darts',
    announce: 'And his opponent, the man who makes the impossible look effortless... Merlin, The Wizard, Blackwood!',
  },
]
const V1 = [
  {
    p: 0, total: 140, call: 'One hundred and forty.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 1), rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, -2), rot: -42 },
      { label: 'S20', score: 20, pos: at(20, 130, 2, 3), rot: -38 },
    ],
  },
  {
    p: 1, total: 180, ...max180(),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2.5, 0), rot: -46 },
      { label: 'T20', score: 60, pos: at(20, 103, 1, 2), rot: -43 },
      { label: 'T20', score: 60, pos: at(20, 103, 3.5, -1), rot: -40 },
    ],
  },
  {
    p: 0, total: 140, call: 'One hundred and forty.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -3, 2), rot: -47 },
      { label: 'T20', score: 60, pos: at(20, 103, 0.5, -3), rot: -44 },
      { label: 'S20', score: 20, pos: at(20, 128, 5, 0), rot: -36 },
    ],
  },
  {
    p: 1, total: 180, ...max180(),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1.5, -1), rot: -48 },
      { label: 'T20', score: 60, pos: at(20, 103, -3, 1.5), rot: -41 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, 3), rot: -44 },
    ],
  },
  {
    p: 0, total: 124, call: 'One hundred and twenty-four. Ninety-seven left.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1, 2), rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 2.5, -2), rot: -42 },
      { label: 'S4',  score: 4,  pos: at(4, 128, 3, 1),   rot: -31, drama: 'STRAYS INTO THE FOUR!' },
    ],
  },
  {
    p: 1, total: 141, gameShot: true,
    hint: '141 · T20 → T17 → D15',
    requireCall: 'Merlin Blackwood, one hundred and forty-one.',
    call: 'Game shot! One hundred and forty-one! Merlin, The Wizard, Blackwood!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1, -1),  rot: -46 },
      { label: 'T17', score: 51, pos: at(17, 103, -2, 1),  rot: -50 },
      { label: 'D15', score: 30, pos: at(15, 166, 0.5, 0), rot: -44, win: true },
    ],
  },
]
const script1 = { MATCH: { startScore: 501, title: 'DARTS.AI GRAND PRIX', subtitle: 'SEMI-FINAL · 501 · DOUBLE OUT' }, PLAYERS: P1, VISITS: V1, matchStats: makeStats(P1, V1) }

// ── 2: Jed "The Howitzer" Holloway vs Rex "Neon Fury" Storm ────────────────
// 301, double-in/out bar league special. Rex lines up D12 for the win — Jed nicks D13 first.
const P2 = [
  {
    name: 'Jed Holloway', nick: 'The Howitzer', tag: 'JH',
    variant: 'cowboy', color: '#f59e0b', cardBg: '#78350f',
    accessories: ['darts', 'horseshoe', 'pint'],
    bio: 'Career average 81.4 · 3 county titles · Never buys his own drinks',
    announce: 'Straight from the lone star circuit... Jed, The Howitzer, Holloway!',
  },
  {
    name: 'Rex Storm', nick: 'Neon Fury', tag: 'RS',
    variant: 'rockstar', color: '#ec4899', cardBg: '#500724',
    accessories: ['darts', 'guitar', 'trophy'],
    bio: 'Career average 85.7 · 5 ranking titles · The crowd always goes wild',
    announce: 'And the people\'s champion... Rex, Neon Fury, Storm!',
  },
]
const V2 = [
  {
    p: 0, total: 157, call: 'One hundred and fifty-seven.',
    darts: [
      { label: 'D20', score: 40, pos: at(20, 166, 1, -1),  rot: -48 },
      { label: 'T20', score: 60, pos: at(20, 103, -2, 1),  rot: -44 },
      { label: 'T19', score: 57, pos: at(19, 103, 2, -1),  rot: -52 },
    ],
  },
  {
    p: 1, total: 149, call: 'One hundred and forty-nine.',
    darts: [
      { label: 'D16', score: 32, pos: at(16, 166, -1, 0),  rot: -47 },
      { label: 'T20', score: 60, pos: at(20, 103, 1, 2),   rot: -43 },
      { label: 'T19', score: 57, pos: at(19, 103, -3, 1),  rot: -51 },
    ],
  },
  {
    p: 0, total: 118, call: 'One hundred and eighteen. Twenty-six remaining.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 0),  rot: -45 },
      { label: 'T18', score: 54, pos: at(18, 103, 2, -1),  rot: -40 },
      { label: 'S4',  score: 4,  pos: at(4, 128, 4, 2),   rot: -30, drama: 'THE HOWITZER SHOOTS HIMSELF!' },
    ],
  },
  {
    p: 1, total: 128, call: 'One hundred and twenty-eight. Rex needs double twelve.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1.5, -2), rot: -44 },
      { label: 'T19', score: 57, pos: at(19, 103, -2, 1),   rot: -50 },
      { label: 'S11', score: 11, pos: at(11, 128, 3, 0),    rot: -42, drama: 'INTO THE ELEVEN! TWENTY-FOUR LEFT!' },
    ],
  },
  {
    p: 0, total: 26, gameShot: true,
    hint: '26 · D13',
    requireCall: 'Jed Holloway, double thirteen for the match!',
    call: 'Game shot! Jed, The Howitzer, Holloway wins it!',
    darts: [
      { label: 'D13', score: 26, pos: at(13, 166, 0.5, 0), rot: -43, win: true },
    ],
  },
]
const script2 = { MATCH: { startScore: 301, title: 'DARTS.AI BAR LEAGUE', subtitle: '301 · DOUBLE IN/OUT · SPECIAL EVENT' }, PLAYERS: P2, VISITS: V2, matchStats: makeStats(P2, V2) }

// ── 3: Zara "Volt" Kazari vs Sir Reginald "The Surgeon" Ashworth ────────────
// Zara lips out D18 when the match is hers; Reginald coldly takes the 150 checkout.
const P3 = [
  {
    name: 'Zara Kazari', nick: 'Volt', tag: 'ZK',
    variant: 'cyberpunk', color: '#22d3ee', cardBg: '#083344',
    accessories: ['darts', 'shuriken', 'trophy'],
    bio: 'Career average 96.4 · 11 ranking titles · Lightning release, zero hesitation',
    announce: 'The future of darts has arrived... Zara, Volt, Kazari!',
  },
  {
    name: 'Reginald Ashworth', nick: 'The Surgeon', tag: 'RA',
    variant: 'posh', color: '#d4af37', cardBg: '#1e1b4b',
    accessories: ['darts', 'crown', 'trophy'],
    bio: 'Career average 103.8 · 31 ranking titles · Precision that defies belief',
    announce: 'And his opponent, a living legend of this sport... Sir Reginald, The Surgeon, Ashworth!',
  },
]
const V3 = [
  {
    p: 0, total: 177, call: 'One hundred and seventy-seven.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 1),  rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, -1),  rot: -42 },
      { label: 'T19', score: 57, pos: at(19, 103, 1, 2),   rot: -52 },
    ],
  },
  {
    p: 1, total: 180, ...max180(),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1.5, 0), rot: -46 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, 2),   rot: -43 },
      { label: 'T20', score: 60, pos: at(20, 103, 0.5, -2), rot: -40 },
    ],
  },
  {
    p: 0, total: 171, call: 'One hundred and seventy-one.',
    darts: [
      { label: 'T19', score: 57, pos: at(19, 103, -2, 0),  rot: -53 },
      { label: 'T19', score: 57, pos: at(19, 103, 1.5, 2), rot: -50 },
      { label: 'T19', score: 57, pos: at(19, 103, 3, -2),  rot: -55 },
    ],
  },
  {
    p: 1, total: 171, call: 'One hundred and seventy-one.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 1),  rot: -45 },
      { label: 'T19', score: 57, pos: at(19, 103, 1, -1),  rot: -51 },
      { label: 'T18', score: 54, pos: at(18, 103, -1.5, 2), rot: -39 },
    ],
  },
  {
    p: 0, total: 117, call: 'One hundred and seventeen scored. Thirty-six remaining.',
    hint: '153 · T20 → T19 → D18',
    requireCall: 'Zara Kazari, you require one hundred and fifty-three.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1, 2),   rot: -44 },
      { label: 'T19', score: 57, pos: at(19, 103, 2, -1),   rot: -51 },
      { label: 'D18', score: 0,  pos: at(18, 176, 0, 1),    rot: -38, miss: true, drama: 'DOUBLE EIGHTEEN LIPS OUT!' },
    ],
  },
  {
    p: 1, total: 150, gameShot: true,
    hint: '150 · T20 → T18 → D18',
    requireCall: 'Sir Reginald, one hundred and fifty to win.',
    call: 'Game shot! One hundred and fifty! Sir Reginald, The Surgeon, Ashworth!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1, -1),  rot: -46 },
      { label: 'T18', score: 54, pos: at(18, 103, -1, 2),  rot: -40 },
      { label: 'D18', score: 36, pos: at(18, 166, 0.5, 0), rot: -38, win: true },
    ],
  },
]
const script3 = { MATCH: { startScore: 501, title: 'DARTS.AI MASTERS', subtitle: 'THE FINAL · 501 · DOUBLE OUT' }, PLAYERS: P3, VISITS: V3, matchStats: makeStats(P3, V3) }

// ── 4: Dave "The Regular" Thompson vs Yuki "Ice Cold" Nomura ────────────────
// Extreme skill mismatch. Yuki lands three perfect visits; Dave does his best.
const P4 = [
  {
    name: 'Dave Thompson', nick: 'The Regular', tag: 'DT',
    variant: 'pubguy', color: '#fb923c', cardBg: '#431407',
    accessories: ['darts', 'pint', 'trophy'],
    bio: 'Career average 32.1 · 0 ranking titles · But he\'s having a great time',
    announce: 'Our wild-card entry tonight... Dave, The Regular, Thompson!',
  },
  {
    name: 'Yuki Nomura', nick: 'Ice Cold', tag: 'YN',
    variant: 'ninja', color: '#34d399', cardBg: '#064e3b',
    accessories: ['darts', 'shuriken', 'trophy'],
    bio: 'Career average 107.2 · 44 ranking titles · Has never missed a checkout under pressure',
    announce: 'And the number one ranked player on earth... Yuki, Ice Cold, Nomura!',
  },
]
const V4 = [
  {
    p: 0, total: 26, call: 'Twenty-six.',
    darts: [
      { label: 'S20', score: 20, pos: at(20, 128, 1, 2),  rot: -38 },
      { label: 'S5',  score: 5,  pos: at(5,  128, 3, 1),  rot: -29, drama: 'FIVE?! FROM DAVE THOMPSON?!' },
      { label: 'S1',  score: 1,  pos: at(1,  128, -2, 0), rot: -34 },
    ],
  },
  {
    p: 1, total: 180, ...max180(),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 0),  rot: -46 },
      { label: 'T20', score: 60, pos: at(20, 103, 1.5, 2), rot: -43 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, -1),  rot: -40 },
    ],
  },
  {
    p: 0, total: 83, call: 'Eighty-three.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -3, 1),  rot: -44 },
      { label: 'S20', score: 20, pos: at(20, 128, 4, 2),   rot: -37 },
      { label: 'S3',  score: 3,  pos: at(3,  128, 2, 0),   rot: -31, drama: 'THREE! ALL THE WAY OVER THERE!' },
    ],
  },
  {
    p: 1, total: 180, ...max180(),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1.5, 2), rot: -47 },
      { label: 'T20', score: 60, pos: at(20, 103, 2.5, -1), rot: -44 },
      { label: 'T20', score: 60, pos: at(20, 103, 0.5, 3),  rot: -41 },
    ],
  },
  {
    p: 0, total: 135, call: 'One hundred and thirty-five. Good effort from Dave!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 2),  rot: -45 },
      { label: 'T19', score: 57, pos: at(19, 103, 1, -1),  rot: -51 },
      { label: 'S18', score: 18, pos: at(18, 128, 3, 0),   rot: -37 },
    ],
  },
  {
    p: 1, total: 141, gameShot: true,
    hint: '141 · T20 → T17 → D15',
    requireCall: 'Yuki Nomura, one hundred and forty-one for the match.',
    call: 'Game shot! Nine darts! Yuki, Ice Cold, Nomura!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1, -1),  rot: -46 },
      { label: 'T17', score: 51, pos: at(17, 103, -1.5, 1), rot: -49 },
      { label: 'D15', score: 30, pos: at(15, 166, 0.5, 0), rot: -44, win: true },
    ],
  },
]
const script4 = { MATCH: { startScore: 501, title: 'DARTS.AI OPEN', subtitle: 'ROUND ONE · 501 · DOUBLE OUT' }, PLAYERS: P4, VISITS: V4, matchStats: makeStats(P4, V4) }

// ── 5: Cara "Thunderclap" Voss vs Bruno "The Bulldozer" Hartmann ─────────────
// Bruno lands two 180s and reaches 141; then bottles it on D15. Cara punishes.
const P5 = [
  {
    name: 'Cara Voss', nick: 'Thunderclap', tag: 'CV',
    variant: 'rockstar', color: '#f472b6', cardBg: '#4a044e',
    accessories: ['darts', 'guitar', 'trophy'],
    bio: 'Career average 91.8 · 16 ranking titles · Comeback queen of the tour',
    announce: 'She was down, but never out... Cara, Thunderclap, Voss!',
  },
  {
    name: 'Bruno Hartmann', nick: 'The Bulldozer', tag: 'BH',
    variant: 'viking', color: '#fb7185', cardBg: '#4c0519',
    accessories: ['darts', 'axe', 'trophy'],
    bio: 'Career average 97.5 · 19 ranking titles · Favourite to win every tournament he enters',
    announce: 'The overwhelming favourite tonight... Bruno, The Bulldozer, Hartmann!',
  },
]
const V5 = [
  {
    p: 0, total: 60, call: 'Sixty. Cara Voss finding her feet.',
    darts: [
      { label: 'S20', score: 20, pos: at(20, 128, -2, 1), rot: -38 },
      { label: 'S20', score: 20, pos: at(20, 128, 3, 0),  rot: -35 },
      { label: 'S20', score: 20, pos: at(20, 128, 0, 3),  rot: -40 },
    ],
  },
  {
    p: 1, total: 180, ...max180(),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2.5, 1), rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 1, -2),   rot: -42 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, 1.5),  rot: -47 },
    ],
  },
  {
    p: 0, total: 177, call: 'One hundred and seventy-seven! Cara Voss steps up!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -3, 2),  rot: -46 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, -1),  rot: -43 },
      { label: 'T19', score: 57, pos: at(19, 103, 1.5, 1), rot: -52 },
    ],
  },
  {
    p: 1, total: 180, ...max180('Hartmann is relentless!'),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1, 0),  rot: -44 },
      { label: 'T20', score: 60, pos: at(20, 103, 2.5, 2), rot: -41 },
      { label: 'T20', score: 60, pos: at(20, 103, 0, -3),  rot: -48 },
    ],
  },
  {
    p: 0, total: 180, ...max180('CARA VOSS IS ALIVE!'),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 1.5), rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, -2),   rot: -42 },
      { label: 'T20', score: 60, pos: at(20, 103, 0.5, 2),  rot: -46 },
    ],
  },
  {
    p: 1, total: 126, call: 'One hundred and twenty-six. Fifteen remaining.',
    hint: '141 · T20 → T17 → D15',
    requireCall: 'Bruno Hartmann, you require one hundred and forty-one.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1.5, 0), rot: -44 },
      { label: 'T17', score: 51, pos: at(17, 103, 2, -1),   rot: -49 },
      { label: 'S15', score: 15, pos: at(15, 128, 1, 2),    rot: -44, drama: 'SINGLE FIFTEEN! THE BULLDOZER STALLS!' },
    ],
  },
  {
    p: 0, total: 84, gameShot: true,
    hint: '84 · T18 → D15',
    requireCall: 'Cara Voss, eighty-four, double fifteen for the match.',
    call: 'Game shot! Cara, Thunderclap, Voss wins the leg!',
    darts: [
      { label: 'T18', score: 54, pos: at(18, 103, -1, 1),  rot: -40 },
      { label: 'D15', score: 30, pos: at(15, 166, 0.5, 0), rot: -44, win: true },
    ],
  },
]
const script5 = { MATCH: { startScore: 501, title: 'DARTS.AI CHAMPIONSHIP', subtitle: 'LEG DECIDER · 501 · DOUBLE OUT' }, PLAYERS: P5, VISITS: V5, matchStats: makeStats(P5, V5) }


// ── 6: Max "The Machine" Calder vs Luca "Lucky Seven" Moretti ──────────────
// Max throws the full TV fantasy: 180, 180, then 141 for a nine-dart finish.
const P6 = [
  {
    name: 'Max Calder', nick: 'The Machine', tag: 'MC',
    variant: 'robot', color: '#38bdf8', cardBg: '#0f172a',
    accessories: ['darts', 'cog', 'trophy'],
    bio: 'Career average 112.6 · 63 ranking titles · Appears to have been assembled in a tungsten laboratory',
    announce: 'Walking in like the final boss of darts... Max, The Machine, Calder!',
  },
  {
    name: 'Luca Moretti', nick: 'Lucky Seven', tag: 'LM',
    variant: 'showman', color: '#facc15', cardBg: '#422006',
    accessories: ['darts', 'dice', 'trophy'],
    bio: 'Career average 92.9 · 10 ranking titles · The king of impossible escapes',
    announce: 'And trying to stop the machine... Luca, Lucky Seven, Moretti!',
  },
]
const V6 = [
  {
    p: 0, total: 180, ...max180(),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 0),   rot: -46 },
      { label: 'T20', score: 60, pos: at(20, 103, 1.5, 2),  rot: -43 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, -1.5), rot: -40 },
    ],
  },
  {
    p: 1, total: 97, call: callForTotal(97),
    darts: [
      { label: 'T19', score: 57, pos: at(19, 103, -2, 1), rot: -51 },
      { label: 'S20', score: 20, pos: at(20, 128, 3, 0),  rot: -36 },
      { label: 'S20', score: 20, pos: at(20, 128, 0, 2),  rot: -38 },
    ],
  },
  {
    p: 0, total: 180, ...max180('He is on for the perfect leg!'),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1.5, 2), rot: -47 },
      { label: 'T20', score: 60, pos: at(20, 103, 2.5, -1), rot: -44 },
      { label: 'T20', score: 60, pos: at(20, 103, 0.5, 3),  rot: -41 },
    ],
  },
  {
    p: 1, total: 140, call: callForTotal(140),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 1), rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, -2), rot: -42 },
      { label: 'S20', score: 20, pos: at(20, 128, 5, 0),  rot: -37 },
    ],
  },
  {
    p: 0, total: 141, gameShot: true,
    hint: '141 · T20 → T19 → D12',
    requireCall: 'Max Calder, one hundred and forty-one for the nine-darter.',
    call: 'Game shot! Nine-dart finish! Max, The Machine, Calder!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1, -1),   rot: -46 },
      { label: 'T19', score: 57, pos: at(19, 103, -1.5, 1), rot: -51 },
      { label: 'D12', score: 24, pos: at(12, 166, 0.5, 0),  rot: -39, win: true },
    ],
  },
]
const script6 = { MATCH: { startScore: 501, title: 'DARTS.AI PERFECT LEG', subtitle: 'NINE-DART SPECIAL · 501 · DOUBLE OUT' }, PLAYERS: P6, VISITS: V6, matchStats: makeStats(P6, V6) }

// ── 7: Gary "Two Pints" Wilkins vs Mo "The Spreadsheet" Patel ──────────────
// Pub chaos. Bad darts, worse decisions, then one stupidly good checkout.
const P7 = [
  {
    name: 'Gary Wilkins', nick: 'Two Pints', tag: 'GW',
    variant: 'pubguy', color: '#fb923c', cardBg: '#431407',
    accessories: ['darts', 'pint', 'horseshoe'],
    bio: 'Career average 39.8 · Local league regular · Calls every miss a marker',
    announce: 'From table eight, carrying questionable confidence... Gary, Two Pints, Wilkins!',
  },
  {
    name: 'Mo Patel', nick: 'The Spreadsheet', tag: 'MP',
    variant: 'posh', color: '#60a5fa', cardBg: '#1e3a8a',
    accessories: ['darts', 'cog', 'trophy'],
    bio: 'Career average 71.2 · Calculates checkouts nobody asked for',
    announce: 'And the man with conditional formatting in his soul... Mo, The Spreadsheet, Patel!',
  },
]
const V7 = [
  {
    p: 0, total: 26, call: 'Twenty-six. The traditional breakfast.',
    darts: [
      { label: 'S20', score: 20, pos: at(20, 128, -1, 2), rot: -38 },
      { label: 'S5',  score: 5,  pos: at(5, 128, 3, 1),   rot: -29, drama: 'FIVE! HE WENT SEARCHING FOR TWENTY AND FOUND PUB HISTORY!' },
      { label: 'S1',  score: 1,  pos: at(1, 128, -2, 0),  rot: -34 },
    ],
  },
  {
    p: 1, total: 41, call: callForTotal(41),
    darts: [
      { label: 'S20', score: 20, pos: at(20, 128, 2, 1),  rot: -38 },
      { label: 'S20', score: 20, pos: at(20, 128, -3, 0), rot: -36 },
      { label: 'S1',  score: 1,  pos: at(1, 128, 2, -1),  rot: -33, drama: 'THE SPREADSHEET HAS A FORMULA ERROR!' },
    ],
  },
  {
    p: 0, total: 7, call: 'Seven. The less said, the better.',
    darts: [
      { label: 'S1', score: 1, pos: at(1, 128, -2, 0), rot: -34 },
      { label: 'S5', score: 5, pos: at(5, 128, 2, 1),  rot: -30 },
      { label: 'S1', score: 1, pos: at(1, 128, 3, 0),  rot: -35, drama: 'HE HAS SPLIT THE ONES WITH SURGICAL PANIC!' },
    ],
  },
  {
    p: 1, total: 112, gameShot: true,
    hint: '112 · T20 → S20 → D16',
    requireCall: 'Mo Patel, one hundred and twelve. Surely not.',
    call: 'Game shot! One hundred and twelve! Nobody understands what just happened!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1, 1), rot: -45 },
      { label: 'S20', score: 20, pos: at(20, 128, 2, 0),  rot: -37 },
      { label: 'D16', score: 32, pos: at(16, 166, 0, 0),  rot: -43, win: true },
    ],
  },
]
const script7 = { MATCH: { startScore: 186, title: 'DARTS.AI PUB CHAOS', subtitle: 'EXHIBITION LEG · QUESTIONABLE DECISIONS' }, PLAYERS: P7, VISITS: V7, matchStats: makeStats(P7, V7) }

// ── 8: Nina "Nightshift" Blake vs Oscar "The Hammer" Holt ──────────────────
// Oscar dominates early. Nina storms back with back-to-back 180s and a 121 checkout.
const P8 = [
  {
    name: 'Nina Blake', nick: 'Nightshift', tag: 'NB',
    variant: 'cyberpunk', color: '#a3e635', cardBg: '#1a2e05',
    accessories: ['darts', 'shuriken', 'trophy'],
    bio: 'Career average 98.1 · 18 ranking titles · Plays best when everyone else is panicking',
    announce: 'The late-night specialist... Nina, Nightshift, Blake!',
  },
  {
    name: 'Oscar Holt', nick: 'The Hammer', tag: 'OH',
    variant: 'viking', color: '#f87171', cardBg: '#450a0a',
    accessories: ['darts', 'axe', 'trophy'],
    bio: 'Career average 99.4 · 21 ranking titles · Heavy scoring, heavier stare',
    announce: 'And bringing the blunt-force tungsten... Oscar, The Hammer, Holt!',
  },
]
const V8 = [
  {
    p: 0, total: 60, call: 'Sixty. Nina Blake still warming up.',
    darts: [
      { label: 'S20', score: 20, pos: at(20, 128, -2, 1), rot: -38 },
      { label: 'S20', score: 20, pos: at(20, 128, 3, 0),  rot: -35 },
      { label: 'S20', score: 20, pos: at(20, 128, 0, 3),  rot: -40 },
    ],
  },
  {
    p: 1, total: 180, ...max180('Oscar Holt is trying to end this early!'),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 0), rot: -46 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, 2),  rot: -43 },
      { label: 'T20', score: 60, pos: at(20, 103, 0, -2), rot: -40 },
    ],
  },
  {
    p: 0, total: 180, ...max180('Nina Blake has found another gear!'),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2.5, 1), rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 1, -2),   rot: -42 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, 1.5),  rot: -47 },
    ],
  },
  {
    p: 1, total: 140, call: 'One hundred and forty. Oscar leaves eighty-one.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 1), rot: -45 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, -2), rot: -42 },
      { label: 'S20', score: 20, pos: at(20, 128, 5, 0),  rot: -37 },
    ],
  },
  {
    p: 0, total: 180, ...max180('This is getting ridiculous!'),
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1, 0), rot: -44 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, 2),  rot: -41 },
      { label: 'T20', score: 60, pos: at(20, 103, 0, -3), rot: -48 },
    ],
  },
  {
    p: 1, total: 45, call: 'Forty-five. The Hammer has gone soft at the worst possible moment.',
    darts: [
      { label: 'S20', score: 20, pos: at(20, 128, 1, 0), rot: -37 },
      { label: 'S5',  score: 5,  pos: at(5, 128, 2, 1),   rot: -31, drama: 'INTO THE FIVE! THE DOOR IS OPEN!' },
      { label: 'S20', score: 20, pos: at(20, 128, -3, 0), rot: -38 },
    ],
  },
  {
    p: 0, total: 121, gameShot: true,
    hint: '121 · T20 → T11 → D14',
    requireCall: 'Nina Blake, one hundred and twenty-one for the match.',
    call: 'Game shot! One hundred and twenty-one! Nina, Nightshift, Blake completes the comeback!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1, -1),   rot: -46 },
      { label: 'T11', score: 33, pos: at(11, 103, -1, 2),   rot: -42 },
      { label: 'D14', score: 28, pos: at(14, 166, 0.5, 0),  rot: -39, win: true },
    ],
  },
]
const script8 = { MATCH: { startScore: 501, title: 'DARTS.AI COMEBACK NIGHT', subtitle: 'FINAL LEG · 501 · DOUBLE OUT' }, PLAYERS: P8, VISITS: V8, matchStats: makeStats(P8, V8) }

export const SCRIPTS = [script0, script1, script2, script3, script4, script5, script6, script7, script8].map(normaliseScript)
