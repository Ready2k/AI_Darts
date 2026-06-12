// Scripted championship final: Marcus "The Local" Bell v Kai "Shadow" Tanaka.
// Dart positions are board-mm (x right, y up) matching the canonical frame used
// by dartboard.py, so the broadcast board renders them exactly like real hits.

const SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

// Ring centre radii (mm): treble 103, double 166, outer single ~130.
const at = (seg, r, dDeg = 0, dR = 0) => {
  const a = ((SEGMENTS.indexOf(seg) * 18 + dDeg) * Math.PI) / 180
  return [Math.sin(a) * (r + dR), Math.cos(a) * (r + dR)]
}

export const MATCH = {
  startScore: 501,
  title: 'DARTS.AI WORLD CHAMPIONSHIP',
  subtitle: 'THE FINAL · 501 · DOUBLE OUT',
}

export const PLAYERS = [
  {
    name: 'Marcus Bell', nick: 'The Local', tag: 'MB',
    variant: 'pubguy', color: '#fb7185', cardBg: '#8aa9d6',
    accessories: ['darts', 'trophy', 'pint'],
    bio: 'Career average 98.6 · 14 ranking titles',
    announce: 'Ladies and gentlemen, please welcome... Marcus, The Local, Bell!',
  },
  {
    name: 'Kai Tanaka', nick: 'Shadow', tag: 'KT',
    variant: 'ninja', color: '#22d3ee', cardBg: '#9fd1a8',
    accessories: ['darts', 'trophy', 'shuriken'],
    bio: 'Career average 99.1 · Fastest arm in the game',
    announce: 'And his opponent... the silent assassin... Kai, Shadow, Tanaka!',
  },
]

// Each visit: { p, darts[{label, score, pos, rot, miss?, drama?}], total, call,
//              big?, hint?, requireCall?, gameShot? }
export const VISITS = [
  {
    p: 0, total: 180, big: '180', call: 'One hundred and eighty!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2.5, 1), rot: -44 },
      { label: 'T20', score: 60, pos: at(20, 103, 3, -2), rot: -36 },
      { label: 'T20', score: 60, pos: at(20, 103, 0.5, 3), rot: -50 },
    ],
  },
  {
    p: 1, total: 140, call: 'One hundred and forty.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -3, -1), rot: -40 },
      { label: 'T20', score: 60, pos: at(20, 103, 2, 2), rot: -47 },
      { label: 'S20', score: 20, pos: at(20, 132, 4, 0), rot: -38 },
    ],
  },
  {
    p: 0, total: 137, call: 'One hundred and thirty-seven.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1.5, -3), rot: -42 },
      { label: 'T19', score: 57, pos: at(19, 103, -2, 1), rot: -52 },
      { label: 'S20', score: 20, pos: at(20, 128, -4, 0), rot: -37 },
    ],
  },
  {
    p: 1, total: 45, call: 'Forty-five.',
    darts: [
      { label: 'S20', score: 20, pos: at(20, 130, -5, 2), rot: -45 },
      { label: 'S5', score: 5, pos: at(5, 128, 3, 0), rot: -33, drama: 'DRIFTS INTO THE 5!' },
      { label: 'S20', score: 20, pos: at(20, 134, 2, -3), rot: -48 },
    ],
  },
  {
    p: 0, total: 100, call: 'One hundred.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1, 2), rot: -39 },
      { label: 'S20', score: 20, pos: at(20, 126, 5, 1), rot: -46 },
      { label: 'S20', score: 20, pos: at(20, 131, -6, -1), rot: -41 },
    ],
  },
  {
    p: 1, total: 180, big: '180', call: 'One hundred and eighty!',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -2, 0), rot: -43 },
      { label: 'T20', score: 60, pos: at(20, 103, 2.5, -3), rot: -49 },
      { label: 'T20', score: 60, pos: at(20, 103, 0, 2.5), rot: -35 },
    ],
  },
  {
    p: 0, total: 68, call: 'Sixty-eight scored. Sixteen remaining.',
    hint: '84 · T20 → S8 → D8',
    requireCall: 'Marcus Bell, you require eighty-four.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, 1, 1), rot: -45 },
      { label: 'S8', score: 8, pos: at(8, 130, -3, 2), rot: -51 },
      { label: 'D8', score: 0, pos: at(8, 176, 1, 0), rot: -40, miss: true, drama: 'OUTSIDE THE WIRE!' },
    ],
  },
  {
    p: 1, total: 96, call: 'Ninety-six.',
    hint: '136 · T20 → T20 → D8',
    requireCall: 'Kai Tanaka, you require one hundred and thirty-six.',
    darts: [
      { label: 'T20', score: 60, pos: at(20, 103, -1.5, -1), rot: -38 },
      { label: 'S20', score: 20, pos: at(20, 127, 4, 2), rot: -44, drama: 'JUST OUTSIDE THE TREBLE!' },
      { label: 'S16', score: 16, pos: at(16, 130, 2, 0), rot: -47 },
    ],
  },
  {
    p: 0, total: 16, gameShot: true,
    hint: '16 · D8',
    requireCall: 'Marcus Bell. Sixteen, for the championship.',
    call: 'Game shot! And the match... Marcus, The Local, Bell!',
    darts: [
      { label: 'D8', score: 16, pos: at(8, 166, 0.5, 0), rot: -42, win: true },
    ],
  },
]

// Pre-computed for the winner card.
export function matchStats() {
  const s = PLAYERS.map(() => ({ pts: 0, darts: 0, maxima: 0 }))
  for (const v of VISITS) {
    s[v.p].pts += v.total
    s[v.p].darts += v.darts.length
    if (v.total === 180) s[v.p].maxima += 1
  }
  return s.map((x) => ({ ...x, avg: x.darts ? (3 * x.pts) / x.darts : 0 }))
}
