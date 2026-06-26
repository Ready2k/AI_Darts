// MC / commentary line bank for the cinematic broadcast. pickLine(event, ctx)
// returns a short caller string for an event, with anti-repeat so the same line
// never fires twice in a row for a given event. Keep lines SHORT — they're spoken
// by sound.say() and shouldn't pile up.
//
// ctx fields used (all optional): name, need, total, target, label, leader,
// victim, killer.

const fill = (tpl, ctx) =>
  tpl.replace(/\{(\w+)\}/g, (_, k) => (ctx?.[k] != null ? String(ctx[k]) : ''))

// Each event → an array of templates. {name} etc. are filled from ctx.
const LINES = {
  // Turn handover. The plain "{name} needs {need}" phrasing is kept as the first
  // variant so the existing per-turn intro is still possible (X01 fills `need`
  // with the score; other modes pass a phrase via `need`).
  turnIntro: [
    '{name} needs {need}',
    'Up steps {name}',
    '{name} to the oche',
    'Here comes {name}',
    'Over to {name}',
    'It\'s {name}\'s turn',
  ],
  // A big visit total (X01). ctx.total is the visit score.
  visitTotal: [
    'Get in there! {total}!',
    'Lovely darts! {total}!',
    'What a visit — {total}!',
    'Oh, that\'s class! {total}!',
    'Big score, {total}!',
  ],
  // A finish attempt missed.
  checkoutMiss: [
    'Just missed it!',
    'Agonising — so close!',
    'Rattled the wire!',
    'Not this time.',
    'Oh, he\'ll be sick with that.',
  ],
  // The lead changed hands.
  leadChange: [
    '{leader} hits the front!',
    'And there\'s the lead change — {leader} ahead!',
    '{leader} noses in front!',
    'New leader — {leader}!',
  ],
  // A Killer player just armed.
  killerArm: [
    'Locked and loaded!',
    '{name} is armed and dangerous!',
    '{name} becomes a killer!',
    'Watch out — {name} is live!',
  ],
  // A player was eliminated.
  eliminated: [
    '{victim} is out!',
    'And that\'s {victim} gone!',
    'Lights out for {victim}!',
    '{victim} is eliminated!',
  ],
  // A Cricket number was closed.
  cricketClose: [
    '{name} closes {label}!',
    '{label} shut down by {name}!',
    'That\'s {label} closed for {name}!',
  ],
  // The match is won.
  win: [
    'Game shot! {name} takes it!',
    'And {name} is the champion!',
    'It\'s all over — {name} wins!',
    'What a finish from {name}!',
  ],
}

// Remember the last template index used per event so we never repeat it.
const lastIdx = {}

export function pickLine(event, ctx = {}) {
  const bank = LINES[event]
  if (!bank || !bank.length) return ''
  let i = Math.floor(Math.random() * bank.length)
  if (bank.length > 1 && i === lastIdx[event]) {
    i = (i + 1) % bank.length   // bump off a repeat
  }
  lastIdx[event] = i
  return fill(bank[i], ctx)
}
