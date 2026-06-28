// MC / commentary line bank for the cinematic broadcast. pickLine(event, ctx)
// returns a short caller string for an event, with anti-repeat so the same line
// never fires twice in a row for a given event. Keep lines SHORT — they're spoken
// by sound.say() and shouldn't pile up.
//
// Strings wrapped in <speak>…</speak> are parsed by the SSML processor in
// audio.js — prosody/emphasis/break tags shape how they sound. Plain strings
// still work for simple cases.
//
// ctx fields used (all optional): name, need, total, target, label, leader,
// victim, killer, foe.

const fill = (tpl, ctx) =>
  tpl.replace(/\{(\w+)\}/g, (_, k) => (ctx?.[k] != null ? String(ctx[k]) : ''))

// Each event → an array of templates. {name} etc. are filled from ctx.
const LINES = {
  // Turn handover — punchy, MC-style, variety of openers. No breaks: these fire
  // every visit, so dead air here drags the whole match.
  turnIntro: [
    '<speak><emphasis level="strong">{name}</emphasis> needs <prosody pitch="-1st">{need}</prosody>.</speak>',
    '<speak>Up steps <prosody pitch="+1st">{name}</prosody>.</speak>',
    '<speak><prosody rate="fast">{name}</prosody> to the oche!</speak>',
    '<speak>Here comes <emphasis level="strong">{name}</emphasis>.</speak>',
    '<speak>Over to <prosody pitch="+1st">{name}</prosody>.</speak>',
    '<speak>It\'s <emphasis level="moderate">{name}</emphasis>\'s turn.</speak>',
  ],
  // A big visit total (X01). ctx.total is the visit score — keep it snappy.
  visitTotal: [
    '<speak><prosody rate="fast" pitch="+1st">Get in there!</prosody> <emphasis level="strong">{total}!</emphasis></speak>',
    '<speak>Lovely darts! <prosody pitch="+1st">{total}!</prosody></speak>',
    '<speak>What a visit — <prosody pitch="+2st">{total}!</prosody></speak>',
    '<speak>Oh, <prosody pitch="+1st">that\'s class!</prosody> <emphasis level="strong">{total}!</emphasis></speak>',
    '<speak><prosody rate="fast">Big score</prosody> — <prosody pitch="+2st">{total}!</prosody></speak>',
  ],
  // A finish attempt missed.
  checkoutMiss: [
    '<speak><prosody pitch="-1st" rate="slow">Just missed it!</prosody></speak>',
    '<speak><emphasis level="moderate">Agonising</emphasis> — so close!</speak>',
    '<speak>Rattled the wire!</speak>',
    '<speak><prosody rate="0.9" pitch="-1st">Not this time.</prosody></speak>',
    '<speak>Oh, <prosody pitch="-1st">he\'ll be sick with that.</prosody></speak>',
  ],
  // The lead changed hands.
  leadChange: [
    '<speak><emphasis level="strong">{leader}</emphasis> hits the front!</speak>',
    '<speak>And there\'s the lead change — <prosody pitch="+1st">{leader}</prosody> ahead!</speak>',
    '<speak><prosody rate="fast">{leader}</prosody> noses in front!</speak>',
    '<speak>New leader — <emphasis level="strong">{leader}!</emphasis></speak>',
  ],
  // A Killer player just armed.
  killerArm: [
    '<speak><prosody rate="fast" pitch="+2st">Locked and loaded!</prosody></speak>',
    '<speak><emphasis level="strong">{name}</emphasis> is <prosody pitch="+1st">armed and dangerous!</prosody></speak>',
    '<speak><prosody pitch="+1st">{name}</prosody> becomes a <emphasis level="strong">killer!</emphasis></speak>',
    '<speak>Watch out — <prosody rate="fast" pitch="+2st">{name} is live!</prosody></speak>',
  ],
  // A player was eliminated.
  eliminated: [
    '<speak><prosody pitch="-2st" rate="slow">{victim} is out!</prosody></speak>',
    '<speak>And that\'s <prosody pitch="-1st">{victim}</prosody> <emphasis level="strong">gone!</emphasis></speak>',
    '<speak><prosody rate="slow" pitch="-2st">Lights out</prosody> for {victim}!</speak>',
    '<speak><emphasis level="strong">{victim}</emphasis> is <prosody pitch="-2st">eliminated!</prosody></speak>',
  ],
  // A Cricket number was closed.
  cricketClose: [
    '<speak><emphasis level="moderate">{name}</emphasis> closes <prosody pitch="+1st">{label}!</prosody></speak>',
    '<speak><prosody pitch="+1st">{label}</prosody> shut down by {name}!</speak>',
    '<speak>That\'s <prosody pitch="+1st">{label}</prosody> closed for <emphasis level="moderate">{name}!</emphasis></speak>',
  ],
  // The recurring AI nemesis ("The Machine") trash-talks. Short + droppable —
  // these are flavour, never priority. ctx.name = the nemesis, ctx.foe = human.
  nemesis: [
    '<speak><prosody pitch="-2st" rate="0.9">The Machine does not miss.</prosody></speak>',
    '<speak><prosody pitch="-1st">Resistance is futile, {foe}.</prosody></speak>',
    '<speak>You cannot out-throw a machine.</speak>',
    '<speak><prosody pitch="-1st">{name}</prosody> is just warming up.</speak>',
    '<speak><prosody rate="0.85" pitch="-2st">Calculating your defeat, {foe}.</prosody></speak>',
    '<speak>The Machine has seen this leg before.</speak>',
  ],
  // The match is won.
  win: [
    '<speak><prosody rate="slow" pitch="+3st">Game <break time="300ms"/> shot!</prosody> <emphasis level="strong">{name} takes it!</emphasis></speak>',
    '<speak>And <emphasis level="strong">{name}</emphasis> <prosody pitch="+2st">is the champion!</prosody></speak>',
    '<speak><prosody rate="slow">It\'s all over</prosody> — <prosody pitch="+2st">{name} wins!</prosody></speak>',
    '<speak>What a <prosody pitch="+1st">finish</prosody> from <emphasis level="strong">{name}!</emphasis></speak>',
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
