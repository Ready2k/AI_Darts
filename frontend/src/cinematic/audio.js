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

export const sound = {
  get enabled() { return enabled },
  setEnabled(v) {
    enabled = v
    if (!v) window.speechSynthesis?.cancel()
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
    this.say('Locked and loaded', { rate: 1.02, pitch: 0.8 })
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

  // Referee / MC voice.
  say(text, { rate = 0.98, pitch = 0.92 } = {}) {
    if (!enabled || !window.speechSynthesis) return
    const u = new SpeechSynthesisUtterance(text)
    const v = pickVoice()
    if (v) u.voice = v
    u.rate = rate
    u.pitch = pitch
    u.volume = 1
    window.speechSynthesis.speak(u)
  },

  stop() {
    window.speechSynthesis?.cancel()
  },
}
