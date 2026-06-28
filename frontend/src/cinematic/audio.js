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
// Real audio crowd bed consisting of two looping layers: crowd-ambient.mp3 (pub murmur)
// and crowd-active.mp3 (louder crowd play-time). We crossfade between them based on
// the intensity (setIntensity). A one-shot crowd-roar.mp3 is triggered on big moments.
const crowdState = {
  running: false,
  base: 0.45,       // current resting intensity (0..1)
  
  // Audio nodes
  ambientSource: null,
  ambientGain: null,
  activeSource: null,
  activeGain: null,
  masterGain: null,
  
  // Cached buffers
  ambientBuffer: null,
  activeBuffer: null,
  roarBuffer: null,
}

async function loadCrowdBuffers() {
  const c = ac()
  if (!c) {
    console.warn("Crowd: AudioContext not available yet.")
    return
  }
  if (crowdState.ambientBuffer && crowdState.activeBuffer && crowdState.roarBuffer) return

  console.log("Crowd: Starting to load audio buffers...")
  const [ambient, active, roar] = await Promise.all([
    fetchAudioBuffer('/crowd-ambient.mp3?v=2'),
    fetchAudioBuffer('/crowd-active.mp3?v=2'),
    fetchAudioBuffer('/crowd-roar.mp3?v=2')
  ])

  crowdState.ambientBuffer = ambient
  crowdState.activeBuffer = active
  crowdState.roarBuffer = roar
  console.log("Crowd: Buffers loaded. Ambient:", !!ambient, "Active:", !!active, "Roar:", !!roar)
}

async function fetchAudioBuffer(url) {
  const c = ac()
  if (!c) return null
  try {
    const response = await fetch(url)
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
    const arrayBuffer = await response.arrayBuffer()
    return await c.decodeAudioData(arrayBuffer)
  } catch (err) {
    console.error(`Failed to load audio buffer from ${url}:`, err)
    return null
  }
}

function updateCrossfade(t, duration = 0.6) {
  if (!crowdState.running) return
  const c = ac(); if (!c) return
  
  const v = crowdState.base
  
  // Equal-power crossfade curves
  const ambientVol = Math.cos(v * Math.PI / 2)
  const activeVol = Math.sin(v * Math.PI / 2)
  
  // Scale to appropriate background bed volumes (max 0.08)
  const maxBedVolume = 0.08
  const targetAmbient = ambientVol * maxBedVolume
  const targetActive = activeVol * maxBedVolume

  if (crowdState.ambientGain) {
    const g = crowdState.ambientGain.gain
    g.cancelScheduledValues(t)
    g.setValueAtTime(g.value, t)
    g.linearRampToValueAtTime(targetAmbient, t + duration)
  }

  if (crowdState.activeGain) {
    const g = crowdState.activeGain.gain
    g.cancelScheduledValues(t)
    g.setValueAtTime(g.value, t)
    g.linearRampToValueAtTime(targetActive, t + duration)
  }

  if (crowdState.masterGain) {
    const g = crowdState.masterGain.gain
    g.cancelScheduledValues(t)
    g.setValueAtTime(g.value, t)
    g.linearRampToValueAtTime(1.0, t + duration)
  }
}

export const crowd = {
  async start() {
    if (!enabled) return
    if (crowdState.running) return
    crowdState.running = true
    console.log("Crowd: start() called.")

    const c = ac(); if (!c) return
    
    // Ensure buffers are loaded
    await loadCrowdBuffers()
    if (!crowdState.running) {
      console.log("Crowd: stopped while loading buffers.")
      return
    }

    const t = c.currentTime
    console.log("Crowd: starting audio sources...")

    // Create master gain for the background bed
    crowdState.masterGain = c.createGain()
    crowdState.masterGain.gain.setValueAtTime(0, t)
    crowdState.masterGain.gain.linearRampToValueAtTime(1, t + 1.2)
    crowdState.masterGain.connect(c.destination)

    // Start ambient loop
    if (crowdState.ambientBuffer) {
      crowdState.ambientSource = c.createBufferSource()
      crowdState.ambientSource.buffer = crowdState.ambientBuffer
      crowdState.ambientSource.loop = true
      crowdState.ambientGain = c.createGain()
      crowdState.ambientSource.connect(crowdState.ambientGain).connect(crowdState.masterGain)
      crowdState.ambientSource.start(t)
    }

    // Start active loop
    if (crowdState.activeBuffer) {
      crowdState.activeSource = c.createBufferSource()
      crowdState.activeSource.buffer = crowdState.activeBuffer
      crowdState.activeSource.loop = true
      crowdState.activeGain = c.createGain()
      crowdState.activeSource.connect(crowdState.activeGain).connect(crowdState.masterGain)
      crowdState.activeSource.start(t)
    }

    updateCrossfade(t)
  },

  stop() {
    console.log("Crowd: stop() called.")
    crowdState.running = false
    const c = ctx
    const t = c ? c.currentTime : 0

    if (c && crowdState.masterGain) {
      try {
        crowdState.masterGain.gain.cancelScheduledValues(t)
        crowdState.masterGain.gain.setValueAtTime(crowdState.masterGain.gain.value, t)
        crowdState.masterGain.gain.linearRampToValueAtTime(0.0001, t + 0.3)
        
        const ambient = crowdState.ambientSource
        const active = crowdState.activeSource
        setTimeout(() => {
          try { ambient?.stop() } catch {}
          try { active?.stop() } catch {}
        }, 350)
      } catch {
        try { crowdState.ambientSource?.stop() } catch {}
        try { crowdState.activeSource?.stop() } catch {}
      }
    } else {
      try { crowdState.ambientSource?.stop() } catch {}
      try { crowdState.activeSource?.stop() } catch {}
    }

    crowdState.ambientSource = null
    crowdState.ambientGain = null
    crowdState.activeSource = null
    crowdState.activeGain = null
    crowdState.masterGain = null
  },

  setIntensity(v) {
    crowdState.base = Math.max(0, Math.min(1, v))
    if (!enabled || !crowdState.running) return
    const c = ac(); if (!c) return
    updateCrossfade(c.currentTime, 0.6)
  },

  hush() {
    if (!enabled || !crowdState.running || !crowdState.masterGain) return
    const c = ac(); if (!c) return
    const t = c.currentTime
    const g = crowdState.masterGain.gain
    g.cancelScheduledValues(t)
    g.setValueAtTime(g.value, t)
    g.linearRampToValueAtTime(0.05, t + 0.5) // fade bed down to 5% volume
  },

  roar() {
    console.log("Crowd: roar() triggered. running:", crowdState.running, "hasRoarBuffer:", !!crowdState.roarBuffer, "enabled:", enabled)
    if (!enabled || !crowdState.running || !crowdState.roarBuffer) return
    const c = ac(); if (!c) return
    const t = c.currentTime

    // Play one-shot roar at full volume, bypassing the bed's masterGain
    const roarSrc = c.createBufferSource()
    roarSrc.buffer = crowdState.roarBuffer
    
    const roarGain = c.createGain()
    roarGain.gain.setValueAtTime(0, t)
    roarGain.gain.linearRampToValueAtTime(0.3, t + 0.15) // quick swell
    roarGain.gain.setValueAtTime(0.3, t + 1.5)
    roarGain.gain.exponentialRampToValueAtTime(0.0001, t + 4.5) // natural decay

    roarSrc.connect(roarGain).connect(c.destination)
    roarSrc.start(t)
    roarSrc.stop(t + 4.6)

    // Ensure the bed's masterGain is restored
    if (crowdState.masterGain) {
      const g = crowdState.masterGain.gain
      g.cancelScheduledValues(t)
      g.setValueAtTime(g.value, t)
      g.linearRampToValueAtTime(1.0, t + 0.1)
    }

    // Temporarily boost active bed to blend with the roar
    if (crowdState.activeGain) {
      const g = crowdState.activeGain.gain
      g.cancelScheduledValues(t)
      g.setValueAtTime(g.value, t)
      g.linearRampToValueAtTime(0.12, t + 0.3)
      g.linearRampToValueAtTime(Math.sin(crowdState.base * Math.PI / 2) * 0.08, t + 3.0)
    }
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

// ── Voice picker helpers ─────────────────────────────────────────────────────
const VOICE_STORAGE_KEY = 'darts_voice_uri'

/** Returns all English voices, en-GB first then other en-* */
export function getAvailableVoices() {
  const all = window.speechSynthesis?.getVoices() || []
  const enGB = all.filter((v) => v.lang === 'en-GB')
  const enOther = all.filter((v) => v.lang?.startsWith('en') && v.lang !== 'en-GB')
  return [...enGB, ...enOther]
}

/** Persist a voice choice and immediately apply it */
export function setSelectedVoice(voiceURI) {
  try { localStorage.setItem(VOICE_STORAGE_KEY, voiceURI) } catch { /* storage blocked */ }
  const voices = window.speechSynthesis?.getVoices() || []
  cachedVoice = voices.find((v) => v.voiceURI === voiceURI) || cachedVoice
}

/** Read the stored voice URI (may be null if never set) */
export function getSelectedVoiceURI() {
  try { return localStorage.getItem(VOICE_STORAGE_KEY) } catch { return null }
}

/**
 * Fire cb once voices are available (handles Chrome's async voiceschanged).
 * If voices are already loaded the callback fires synchronously.
 */
export function onVoicesReady(cb) {
  if (!window.speechSynthesis) return
  const voices = window.speechSynthesis.getVoices()
  if (voices.length) { cb(voices); return }
  window.speechSynthesis.addEventListener('voiceschanged', () => cb(window.speechSynthesis.getVoices()), { once: true })
}

function selectBestVoice() {
  const voices = window.speechSynthesis?.getVoices() || []
  if (!voices.length) return

  // 1. Honour the user's explicit choice stored in localStorage.
  const storedURI = getSelectedVoiceURI()
  if (storedURI) {
    const stored = voices.find((v) => v.voiceURI === storedURI)
    if (stored) { cachedVoice = stored; return }
  }

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

// ── Lightweight SSML parser ──────────────────────────────────────────────────
// SpeechSynthesisUtterance doesn't parse SSML natively in browsers, so we do a
// minimal parse: split on <break> tags into separate chained utterances, map
// <prosody> / <emphasis> attributes onto rate/pitch adjustments, and strip all
// remaining tags before passing plain text to the utterance.
//
// Returns Array<{text, rate, pitch, volume, delayBefore}>.
// Each element becomes one queued utterance; delayBefore adds a silent gap.

function parseSSML(raw) {
  if (!raw || !raw.trim().startsWith('<speak>')) {
    // Plain text — return a single segment with no adjustments.
    return [{ text: raw || '', rate: 1, pitch: 1, volume: 1, delayBefore: 0 }]
  }

  // Strip outer <speak>…</speak>
  let src = raw.replace(/^\s*<speak>\s*/i, '').replace(/\s*<\/speak>\s*$/i, '')

  // Split on <break … /> into segments; each segment gets its own utterance
  // with a preceding delay equal to the break time.
  const breakRe = /<break(?:\s+time="(\d+(?:\.\d+)?)(ms|s)")?[^>]*\/>/gi
  const rawSegments = []
  let last = 0
  let m
  breakRe.lastIndex = 0
  while ((m = breakRe.exec(src)) !== null) {
    rawSegments.push({ markup: src.slice(last, m.index), delayBefore: 0 })
    const val = m[1] ? parseFloat(m[1]) : 200
    const unit = m[2] || 'ms'
    const ms = unit === 's' ? val * 1000 : val
    last = m.index + m[0].length
    rawSegments.push({ markup: '', delayBefore: ms })   // silent gap segment
  }
  rawSegments.push({ markup: src.slice(last), delayBefore: 0 })

  // Merge the zero-text gap delay into the next real segment so we don't enqueue
  // empty utterances — just carry the delay forward.
  const merged = []
  let pendingDelay = 0
  for (const seg of rawSegments) {
    if (seg.markup.trim() === '') {
      pendingDelay += seg.delayBefore
    } else {
      merged.push({ markup: seg.markup, delayBefore: pendingDelay + seg.delayBefore })
      pendingDelay = 0
    }
  }
  if (!merged.length) return [{ text: '', rate: 1, pitch: 1, volume: 1, delayBefore: 0 }]

  // For each segment, parse prosody/emphasis and strip tags.
  return merged.map(({ markup, delayBefore }) => {
    let rate = 1, pitch = 1, volume = 1

    // <prosody rate="fast|slow|0.9|…"> → rate multiplier
    const prosodyRateMatch = markup.match(/rate="([^"]+)"/i)
    if (prosodyRateMatch) {
      const rv = prosodyRateMatch[1]
      if (rv === 'fast' || rv === 'x-fast') rate *= 1.25
      else if (rv === 'slow' || rv === 'x-slow') rate *= 0.75
      else if (rv === 'medium') rate *= 1.0
      else { const n = parseFloat(rv); if (!isNaN(n)) rate *= n }
    }

    // <prosody pitch="+2st"|"-1st"|"high"|"low"> → pitch adjust
    const prosodyPitchMatch = markup.match(/pitch="([^"]+)"/i)
    if (prosodyPitchMatch) {
      const pv = prosodyPitchMatch[1]
      if (pv === 'high' || pv === 'x-high') pitch += 0.15
      else if (pv === 'low' || pv === 'x-low') pitch -= 0.15
      else {
        // "+2st" / "-1st" semitone notation → approx 6% per semitone
        const stMatch = pv.match(/^([+-]?\d+(?:\.\d+)?)st$/)
        if (stMatch) pitch += parseFloat(stMatch[1]) * 0.06
        else { const n = parseFloat(pv); if (!isNaN(n)) pitch += n }
      }
    }

    // <prosody volume="loud|soft|…"> → volume
    const prosodyVolMatch = markup.match(/volume="([^"]+)"/i)
    if (prosodyVolMatch) {
      const vv = prosodyVolMatch[1]
      if (vv === 'loud' || vv === 'x-loud') volume = 1.0
      else if (vv === 'soft' || vv === 'x-soft') volume = 0.6
      else { const n = parseFloat(vv); if (!isNaN(n)) volume = Math.min(1, Math.max(0, n)) }
    }

    // <emphasis level="strong|moderate|reduced"> → rate/pitch nudge
    const emphMatch = markup.match(/emphasis[^>]+level="([^"]+)"/i)
    if (emphMatch) {
      const lv = emphMatch[1]
      if (lv === 'strong') { rate *= 0.88; pitch += 0.08 }
      else if (lv === 'moderate') { rate *= 0.94; pitch += 0.04 }
      else if (lv === 'reduced') { rate *= 1.05; pitch -= 0.04 }
    }

    // Strip all remaining XML tags and decode common entities
    const text = markup
      .replace(/<[^>]+>/g, '')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&apos;/g, "'")
      .replace(/&quot;/g, '"')
      .replace(/\s+/g, ' ')
      .trim()

    // Clamp to sensible utterance ranges
    return { text, rate: Math.max(0.5, Math.min(2, rate)), pitch: Math.max(0.5, Math.min(2, pitch)), volume, delayBefore }
  }).filter((s) => s.text.length > 0)
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

function _speakSegment(item) {
  if (!window.speechSynthesis) return
  const doSpeak = () => {
    const u = new SpeechSynthesisUtterance(item.text)
    const v = pickVoice()
    if (v) u.voice = v
    u.rate = item.rate
    u.pitch = item.pitch
    u.volume = item.volume ?? 1
    // Watchdog: some browsers drop `onend`, which would wedge the queue forever.
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
  if (item.delayBefore > 0) {
    setTimeout(doSpeak, item.delayBefore)
  } else {
    doSpeak()
  }
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
  _speakSegment(item)
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
  //
  // `text` may be a plain string OR an SSML string wrapped in <speak>…</speak>.
  // SSML <break> tags split the utterance into multiple chained queue items so
  // that pauses play correctly without blocking the queue between them.
  say(text, { rate = 0.98, pitch = 0.92, ttl = 3000, priority = false } = {}) {
    if (!enabled || !window.speechSynthesis || !text) return
    const segments = parseSSML(text)
    const now = Date.now()
    for (const seg of segments) {
      _speechQ.push({
        text: seg.text,
        // SSML prosody values are multiplied on top of the caller's base rate/pitch
        rate: rate * seg.rate,
        pitch: pitch * seg.pitch,
        volume: seg.volume,
        delayBefore: seg.delayBefore,
        t: now,
        ttl,
        drop: !priority,
      })
    }
    _drainSpeech()
  },

  stop() {
    _clearSpeech()
    crowd.stop()
  },
}
