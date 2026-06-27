// Avatar / persona definitions for the flat-vector caricature art
// (src/art/Caricature.jsx). A persona shape is:
//   { id, name (nickname), variant, bg (card colour), theme,
//     accessories?: string[] (up to 3), catchphrase?: string }
// `variant` selects the character drawing; `bg` is the flat card colour behind
// it; `theme` keys the walk-on entrance sting in cinematic/audio.js (THEME_SEQS).
// The 8 built-ins below are fixed; users can author their own custom personas
// (persisted to localStorage) via the PersonaEditor — see getAllPersonas().

export const AVATARS = [
  { id: 'pubguy',   name: 'The Local',      variant: 'pubguy',   bg: '#8aa9d6', theme: 'pub' },
  { id: 'cyberpunk',name: 'Neon Shark',      variant: 'cyberpunk',bg: '#b48ad6', theme: 'cyber' },
  { id: 'ninja',    name: 'Shadow Dart',     variant: 'ninja',    bg: '#9fd1a8', theme: 'ninja' },
  { id: 'wizard',   name: 'Grand Magus',     variant: 'wizard',   bg: '#d6a98a', theme: 'wizard' },
  { id: 'viking',   name: 'Iron Dane',       variant: 'viking',   bg: '#6a8dac', theme: 'viking' },
  { id: 'cowboy',   name: 'Lone Shooter',    variant: 'cowboy',   bg: '#c49a5a', theme: 'cowboy' },
  { id: 'rockstar', name: 'The Axe Man',     variant: 'rockstar', bg: '#7c3f91', theme: 'rockstar' },
  { id: 'posh',     name: 'Lord Double',     variant: 'posh',     bg: '#4a7a6a', theme: 'fanfare' },
]

// Valid building blocks (must match what Caricature.jsx actually draws).
export const VARIANT_IDS   = ['pubguy', 'cyberpunk', 'ninja', 'wizard', 'viking', 'cowboy', 'rockstar', 'posh']
export const ACCESSORY_IDS = ['darts', 'trophy', 'pint', 'shuriken', 'axe', 'guitar', 'crown', 'horseshoe']
export const THEME_IDS     = ['pub', 'cyber', 'ninja', 'wizard', 'viking', 'cowboy', 'rockstar', 'fanfare']

const STORE_KEY = 'darts.personas'
const CUSTOM_PREFIX = 'custom:'

export function isCustomId(id) {
  return typeof id === 'string' && id.startsWith(CUSTOM_PREFIX)
}

// Read the custom-persona list from localStorage, robust to malformed/missing
// data (returns [] on any problem).
export function getCustomPersonas() {
  try {
    const raw = typeof localStorage !== 'undefined' && localStorage.getItem(STORE_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    if (!Array.isArray(arr)) return []
    return arr.filter((p) => p && typeof p.id === 'string' && p.variant)
  } catch {
    return []
  }
}

function writeCustomPersonas(list) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(list))
  } catch {
    /* storage unavailable / quota — non-fatal */
  }
}

// Built-ins + custom, for pickers.
export function getAllPersonas() {
  return [...AVATARS, ...getCustomPersonas()]
}

// Create or update a custom persona. Returns the saved persona (with id).
export function saveCustomPersona(p) {
  const id = isCustomId(p.id) ? p.id : `${CUSTOM_PREFIX}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
  const clean = {
    id,
    name: ((p.name || '').trim().slice(0, 24)) || 'New Player',
    variant: VARIANT_IDS.includes(p.variant) ? p.variant : 'pubguy',
    bg: /^#[0-9a-fA-F]{3,8}$/.test(p.bg || '') ? p.bg : '#8aa9d6',
    theme: THEME_IDS.includes(p.theme) ? p.theme : 'fanfare',
    accessories: Array.isArray(p.accessories)
      ? p.accessories.filter((a) => ACCESSORY_IDS.includes(a)).slice(0, 3)
      : [],
    catchphrase: (p.catchphrase || '').trim().slice(0, 60),
  }
  const list = getCustomPersonas().filter((q) => q.id !== id)
  list.push(clean)
  writeCustomPersonas(list)
  return clean
}

export function deleteCustomPersona(id) {
  writeCustomPersonas(getCustomPersonas().filter((q) => q.id !== id))
}

// Resolve any persona id (built-in or custom) → persona, falling back to the
// first built-in so callers always get a usable shape.
export function getAvatar(id) {
  return getAllPersonas().find((a) => a.id === id) || AVATARS[0]
}
