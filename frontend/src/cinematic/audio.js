// Demo sound design: WebAudio-synthesised dart thuds / whooshes / crowd swells,
// plus SpeechSynthesis for the referee and MC. No audio assets needed.

let ctx = null
let noiseBuf = null
let enabled = true

function ac() {
  if (!ctx) {
    const AC = window.AudioContext || window.webkitAudioContext
    if (!AC) return null
    ctx = new AC()
  }
  if (ctx.state === 'suspended') ctx.resume()
  return ctx
}

function noise(c) {
  if (!noiseBuf) {
    noiseBuf = c.createBuffer(1, c.sampleRate * 2, c.sampleRate)
    const d = noiseBuf.getChannelData(0)
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1
  }
  const src = c.createBufferSource()
  src.buffer = noiseBuf
  return src
}

// ── Crowd ambience bed ───────────────────────────────────────────────────────
// A single looping filtered-noise source through a lowpass + gain we ramp.
// start()/stop() manage the lifecycle; setIntensity(0..1) sets the resting
// level; roar() swells for a big moment; hush() drops to near-silence for a
// checkout attempt (then restore() / setIntensity brings it back).
const crowdState = {
  src: null,
  lp: null,
  gain: null,
  base: 0.05,       // current resting intensity (0..1) mapped to a gain
  running: false,
}

// Map a 0..1 intensity to an actual gain value (kept low — it's a bed, not a roar).
function crowdGainFor(intensity) {
  return 0.012 + Math.max(0, Math.min(1, intensity)) * 0.07
}

export const crowd = {
  start() {
    if (!enabled) return
    if (crowdState.running) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const src = noise(c)
    src.loop = true
    const lp = c.createBiquadFilter()
    lp.type = 'lowpass'
    lp.frequency.value = 760            // muffled murmur
    const g = c.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.linearRampToValueAtTime(crowdGainFor(crowdState.base), t + 1.2)  // fade in
    src.connect(lp).connect(g).connect(c.destination)
    src.start(t)
    crowdState.src = src
    crowdState.lp = lp
    crowdState.gain = g
    crowdState.running = true
  },
  stop() {
    const c = ctx
    if (crowdState.src) {
      try {
        if (c && crowdState.gain) {
          const t = c.currentTime
          crowdState.gain.gain.cancelScheduledValues(t)
          crowdState.gain.gain.setValueAtTime(crowdState.gain.gain.value, t)
          crowdState.gain.gain.linearRampToValueAtTime(0.0001, t + 0.3)
          crowdState.src.stop(t + 0.35)
        } else {
          crowdState.src.stop()
        }
      } catch { /* already stopped */ }
    }
    crowdState.src = null
    crowdState.lp = null
    crowdState.gain = null
    crowdState.running = false
  },
  setIntensity(v) {
    crowdState.base = Math.max(0, Math.min(1, v))
    if (!enabled || !crowdState.running || !crowdState.gain) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    crowdState.gain.gain.cancelScheduledValues(t)
    crowdState.gain.gain.setValueAtTime(crowdState.gain.gain.value, t)
    crowdState.gain.gain.linearRampToValueAtTime(crowdGainFor(crowdState.base), t + 0.6)
  },
  // Swell up then settle back to the resting intensity (a big-moment roar).
  roar() {
    if (!enabled || !crowdState.running || !crowdState.gain || !crowdState.lp) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const g = crowdState.gain.gain
    const f = crowdState.lp.frequency
    g.cancelScheduledValues(t)
    g.setValueAtTime(g.value, t)
    g.linearRampToValueAtTime(0.22, t + 0.35)                         // swell
    g.linearRampToValueAtTime(crowdGainFor(crowdState.base), t + 1.9) // settle
    f.cancelScheduledValues(t)
    f.setValueAtTime(f.value, t)
    f.linearRampToValueAtTime(2000, t + 0.35)   // brighten on the roar
    f.linearRampToValueAtTime(760, t + 1.9)
  },
  // Drop to near-silence (a tense hush as a player goes for a finish).
  hush() {
    if (!enabled || !crowdState.running || !crowdState.gain) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const g = crowdState.gain.gain
    g.cancelScheduledValues(t)
    g.setValueAtTime(g.value, t)
    g.linearRampToValueAtTime(0.004, t + 0.5)
  },
}

// ── Walk-on theme stings ─────────────────────────────────────────────────────
// A few sequenced oscillator notes per persona vibe. Synth-only; respects mute.
const THEME_SEQS = {
  // Low horn fifths — Viking warhorn.
  viking: { type: 'sawtooth', gain: 0.18, notes: [
    [98.0, 0, 0.5], [147.0, 0, 0.5], [98.0, 0.55, 0.7], [196.0, 0.55, 0.7],
  ] },
  // Power chord — root + fifth + octave, all at once, gritty.
  rockstar: { type: 'square', gain: 0.12, notes: [
    [110, 0, 0.9], [164.8, 0, 0.9], [220, 0, 0.9], [330, 0.18, 0.7],
  ] },
  // Twangy major triad arpeggio — cowboy.
  cowboy: { type: 'triangle', gain: 0.16, notes: [
    [196, 0, 0.25], [246.9, 0.18, 0.25], [293.7, 0.36, 0.45], [392, 0.6, 0.5],
  ] },
  // Mysterious rising minor — ninja / shadow.
  ninja: { type: 'sine', gain: 0.16, notes: [
    [220, 0, 0.3], [261.6, 0.22, 0.3], [329.6, 0.44, 0.6],
  ] },
  // Shimmering arpeggio up — wizard.
  wizard: { type: 'triangle', gain: 0.14, notes: [
    [261.6, 0, 0.22], [329.6, 0.14, 0.22], [392, 0.28, 0.22], [523.3, 0.42, 0.5],
  ] },
  // Bright synth stab — cyberpunk / neon.
  cyber: { type: 'sawtooth', gain: 0.12, notes: [
    [440, 0, 0.18], [440, 0.2, 0.18], [587.3, 0.4, 0.5], [880, 0.4, 0.5],
  ] },
  // Pubby oompah two-note — the local.
  pub: { type: 'square', gain: 0.13, notes: [
    [130.8, 0, 0.28], [196, 0.3, 0.28], [130.8, 0.6, 0.28], [261.6, 0.6, 0.5],
  ] },
  // Regal trumpet fanfare — default / posh.
  fanfare: { type: 'square', gain: 0.13, notes: [
    [392, 0, 0.18], [392, 0.2, 0.18], [392, 0.4, 0.18], [523.3, 0.6, 0.7], [659.3, 0.6, 0.7],
  ] },
}

// Must be called from a user-gesture call stack (the demo button click).
export function unlockAudio() {
  const c = ac()
  if (c) {
    const b = c.createBuffer(1, 1, c.sampleRate)
    const s = c.createBufferSource()
    s.buffer = b
    s.connect(c.destination)
    s.start(0)
  }
  if (window.speechSynthesis) {
    selectBestVoice()
    // voices load async in Chrome — pick again once the list is ready
    if (!cachedVoice) {
      window.speechSynthesis.addEventListener('voiceschanged', selectBestVoice, { once: true })
    }
  }
}

let cachedVoice = null

function selectBestVoice() {
  const voices = window.speechSynthesis?.getVoices() || []
  if (!voices.length) return
  cachedVoice =
    // Chrome: online neural UK voices (best quality, authentic accent)
    voices.find((v) => v.name === 'Google UK English Male') ||
    // macOS: Apple Neural Engine — Daniel Enhanced/Premium
    voices.find((v) => v.name.includes('Daniel') && (v.name.includes('Enhanced') || v.name.includes('Premium'))) ||
    // macOS: any en-GB Enhanced/Premium neural voice
    voices.find((v) => v.lang === 'en-GB' && (v.name.includes('Enhanced') || v.name.includes('Premium'))) ||
    // Chrome: female UK neural fallback
    voices.find((v) => v.name === 'Google UK English Female') ||
    // Basic Daniel (macOS/Safari)
    voices.find((v) => v.name === 'Daniel') ||
    // Any en-GB voice
    voices.find((v) => v.lang === 'en-GB') ||
    // Any Enhanced/Premium English voice
    voices.find((v) => v.lang?.startsWith('en') && (v.name.includes('Enhanced') || v.name.includes('Premium'))) ||
    // Chrome US neural
    voices.find((v) => v.name === 'Google US English') ||
    // Any English voice as final fallback
    voices.find((v) => v.lang?.startsWith('en')) ||
    null
}

function pickVoice() {
  if (!cachedVoice) selectBestVoice()
  return cachedVoice
}

// ── Managed speech queue ─────────────────────────────────────────────────────
// SpeechSynthesis.speak() only enqueues — no overlap guard, no staleness. Over a
// match the MC lines pile up, talk over each other and drift behind the action.
// We serialise utterances (one at a time, chained on `onend`) and drop stale,
// *droppable* commentary so what's spoken stays in sync with what's on screen.
// `priority` lines (walk-on intros, rules, game-shot) always play through.
let _speechQ = []
let _speaking = false

function _clearSpeech() {
  _speechQ = []
  _speaking = false
  try { window.speechSynthesis?.cancel() } catch { /* no-op */ }
}

function _drainSpeech() {
  if (_speaking || !window.speechSynthesis) return
  const now = Date.now()
  // Skip droppable lines that have aged out — speaking them now would lag play.
  while (_speechQ.length && _speechQ[0].drop && now - _speechQ[0].t > _speechQ[0].ttl) {
    _speechQ.shift()
  }
  const item = _speechQ.shift()
  if (!item) return
  const u = new SpeechSynthesisUtterance(item.text)
  const v = pickVoice()
  if (v) u.voice = v
  u.rate = item.rate
  u.pitch = item.pitch
  u.volume = 1
  // Watchdog: some browsers drop `onend`, which would wedge the queue forever.
  // Estimate the utterance length and force-advance if `onend` never fires.
  const estMs = Math.min(12000, 700 + item.text.length * 75)
  let wd = null
  const done = () => {
    if (wd) { clearTimeout(wd); wd = null }
    if (_speaking) { _speaking = false; _drainSpeech() }
  }
  _speaking = true
  u.onend = done
  u.onerror = done
  wd = setTimeout(done, estMs + 1500)
  window.speechSynthesis.speak(u)
}

export const sound = {
  get enabled() { return enabled },
  setEnabled(v) {
    enabled = v
    if (!v) {
      _clearSpeech()
      crowd.stop()      // silence the ambience bed on mute
    }
  },

  // Dart leaving the hand.
  whoosh() {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const src = noise(c)
    const bp = c.createBiquadFilter()
    bp.type = 'bandpass'
    bp.Q.value = 1.2
    bp.frequency.setValueAtTime(400, t)
    bp.frequency.exponentialRampToValueAtTime(2400, t + 0.16)
    const g = c.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.12, t + 0.05)
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.2)
    src.connect(bp).connect(g).connect(c.destination)
    src.start(t); src.stop(t + 0.25)
  },

  // Dart hitting sisal.
  thud() {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const osc = c.createOscillator()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(170, t)
    osc.frequency.exponentialRampToValueAtTime(48, t + 0.1)
    const og = c.createGain()
    og.gain.setValueAtTime(0.55, t)
    og.gain.exponentialRampToValueAtTime(0.001, t + 0.14)
    osc.connect(og).connect(c.destination)
    osc.start(t); osc.stop(t + 0.16)

    const click = noise(c)
    const hp = c.createBiquadFilter()
    hp.type = 'highpass'
    hp.frequency.value = 2500
    const cg = c.createGain()
    cg.gain.setValueAtTime(0.18, t)
    cg.gain.exponentialRampToValueAtTime(0.001, t + 0.04)
    click.connect(hp).connect(cg).connect(c.destination)
    click.start(t); click.stop(t + 0.05)
  },

  // Crowd swell — bigger=true for 180s and the game shot.
  cheer(big = false) {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const dur = big ? 2.6 : 1.4
    const src = noise(c)
    src.loop = true
    const lp = c.createBiquadFilter()
    lp.type = 'lowpass'
    lp.frequency.setValueAtTime(900, t)
    lp.frequency.linearRampToValueAtTime(big ? 2200 : 1400, t + 0.4)
    lp.frequency.linearRampToValueAtTime(700, t + dur)
    const g = c.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(big ? 0.4 : 0.18, t + 0.35)
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
    src.connect(lp).connect(g).connect(c.destination)
    src.start(t); src.stop(t + dur + 0.1)
  },

  // ── Killer mode SFX ──────────────────────────────────────────────────────

  // Gunshot — a dart being "fired" in Killer.
  gunshot() {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    // crack
    const src = noise(c)
    const hp = c.createBiquadFilter()
    hp.type = 'highpass'; hp.frequency.value = 1100
    const g = c.createGain()
    g.gain.setValueAtTime(0.6, t)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.12)
    src.connect(hp).connect(g).connect(c.destination)
    src.start(t); src.stop(t + 0.13)
    // body thump
    const osc = c.createOscillator()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(130, t)
    osc.frequency.exponentialRampToValueAtTime(42, t + 0.12)
    const og = c.createGain()
    og.gain.setValueAtTime(0.5, t)
    og.gain.exponentialRampToValueAtTime(0.001, t + 0.15)
    osc.connect(og).connect(c.destination)
    osc.start(t); osc.stop(t + 0.16)
  },

  // Cash register "ka-ching" — a hit that counts toward arming.
  kerching() {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const ding = (at, f) => {
      const o = c.createOscillator()
      o.type = 'triangle'; o.frequency.value = f
      const g = c.createGain()
      g.gain.setValueAtTime(0.0001, at)
      g.gain.exponentialRampToValueAtTime(0.32, at + 0.008)
      g.gain.exponentialRampToValueAtTime(0.001, at + 0.3)
      o.connect(g).connect(c.destination)
      o.start(at); o.stop(at + 0.32)
    }
    ding(t, 1318); ding(t + 0.09, 1760)   // rising two-note ka-ching
  },

  // Slide-rack "chk-chk" + spoken cue when a player becomes armed.
  lockLoad() {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const click = (at) => {
      const src = noise(c)
      const bp = c.createBiquadFilter()
      bp.type = 'bandpass'; bp.Q.value = 9; bp.frequency.value = 2700
      const g = c.createGain()
      g.gain.setValueAtTime(0.55, at)
      g.gain.exponentialRampToValueAtTime(0.001, at + 0.05)
      src.connect(bp).connect(g).connect(c.destination)
      src.start(at); src.stop(at + 0.06)
    }
    click(t); click(t + 0.14)
    // The spoken "armed" call is now varied by the commentary bank at the call
    // site (CinematicGame Killer effect); lockLoad() is just the rack SFX.
  },

  // Comedic descending "ouch" — a life knocked off a player.
  ouch() {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const o = c.createOscillator()
    o.type = 'sawtooth'
    o.frequency.setValueAtTime(540, t)
    o.frequency.exponentialRampToValueAtTime(170, t + 0.2)
    const g = c.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.28, t + 0.02)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.24)
    o.connect(g).connect(c.destination)
    o.start(t); o.stop(t + 0.26)
  },

  // Decelerating ratchet ticks for the spin-the-wheel number picker.
  _tick(c, at) {
    const src = noise(c)
    const bp = c.createBiquadFilter()
    bp.type = 'bandpass'; bp.Q.value = 7; bp.frequency.value = 1900
    const g = c.createGain()
    g.gain.setValueAtTime(0.13, at)
    g.gain.exponentialRampToValueAtTime(0.001, at + 0.02)
    src.connect(bp).connect(g).connect(c.destination)
    src.start(at); src.stop(at + 0.025)
  },
  wheelSpin(durationMs = 3400) {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t0 = c.currentTime
    const dur = durationMs / 1000
    let t = 0, gap = 0.028
    while (t < dur) {
      this._tick(c, t0 + t)
      t += gap
      gap *= 1.062            // slow down toward the end
    }
  },
  // Bright bell when the wheel lands.
  ding() {
    if (!enabled) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const o = c.createOscillator()
    o.type = 'sine'
    o.frequency.setValueAtTime(880, t)
    o.frequency.exponentialRampToValueAtTime(1320, t + 0.02)
    const g = c.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(0.32, t + 0.01)
    g.gain.exponentialRampToValueAtTime(0.001, t + 0.5)
    o.connect(g).connect(c.destination)
    o.start(t); o.stop(t + 0.52)
  },

  // Walk-on entrance sting — a few sequenced notes themed to the persona.
  // themeId falls back to a regal fanfare for anything unmapped.
  walkOnTheme(themeId) {
    if (!enabled) return
    const c = ac(); if (!c) return
    const seq = THEME_SEQS[themeId] || THEME_SEQS.fanfare
    const t0 = c.currentTime + 0.02
    seq.notes.forEach(([freq, at, dur]) => {
      const o = c.createOscillator()
      o.type = seq.type
      o.frequency.value = freq
      const g = c.createGain()
      const start = t0 + at
      g.gain.setValueAtTime(0.0001, start)
      g.gain.exponentialRampToValueAtTime(seq.gain, start + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, start + dur)
      o.connect(g).connect(c.destination)
      o.start(start); o.stop(start + dur + 0.05)
    })
  },

  // Referee / MC voice. Routed through the managed queue so lines never overlap
  // and stale commentary is dropped to stay in sync. `priority: true` marks a
  // must-play line (walk-on intro, rules, game-shot) that is never dropped;
  // `ttl` is how long a droppable line may wait before it's skipped.
  say(text, { rate = 0.98, pitch = 0.92, ttl = 3000, priority = false } = {}) {
    if (!enabled || !window.speechSynthesis || !text) return
    _speechQ.push({ text, rate, pitch, t: Date.now(), ttl, drop: !priority })
    _drainSpeech()
  },

  stop() {
    _clearSpeech()
    crowd.stop()
  },
}
