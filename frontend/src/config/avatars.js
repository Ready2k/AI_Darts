// Avatar definitions for the flat-vector caricature art (src/art/Caricature.jsx).
// `variant` selects the character drawing; `bg` is the flat card colour behind it.
// `variant` selects the character drawing; `bg` is the flat card colour behind
// it; `theme` keys the walk-on entrance sting in cinematic/audio.js (THEME_SEQS).
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

export function getAvatar(id) {
  return AVATARS.find(a => a.id === id) || AVATARS[0]
}
