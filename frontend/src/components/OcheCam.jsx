import { ThrowState } from '../config/timing';
import Caricature from '../art/Caricature';

// Map live throw-animation states onto caricature poses.
const POSE = {
  [ThrowState.IDLE]: 'idle',
  [ThrowState.WALKING]: 'idle',
  [ThrowState.AIMING]: 'aim',
  [ThrowState.REPLAYING]: 'aim',
  [ThrowState.THROWING]: 'throw',
  [ThrowState.DART_FLIGHT]: 'throw',
  [ThrowState.IMPACT]: 'throw',
  [ThrowState.SCORING]: 'throw',
  [ThrowState.CELEBRATING]: 'celebrate',
  [ThrowState.DEFEATED]: 'defeated',
};

export default function OcheCam({ avatar, animState }) {
  if (!avatar) return null;

  const pose = POSE[animState] || 'idle';
  const isHighlight = pose === 'aim' || pose === 'throw' || pose === 'celebrate';

  let containerStyle = {};
  let charStyle = {};
  if (animState === ThrowState.WALKING) {
    containerStyle = { animation: 'oche-walk-on 2s ease-out forwards' };
    charStyle = { animation: 'oche-walk-bounce 0.5s infinite alternate' };
  } else if (animState === ThrowState.CELEBRATING) {
    containerStyle = { animation: 'oche-celebrate-pulse 1s infinite alternate' };
    charStyle = { animation: 'oche-celebrate-bounce 0.4s infinite alternate ease-out' };
  } else if (pose === 'idle') {
    charStyle = { animation: 'oche-idle-bob 2.6s ease-in-out infinite' };
  }

  return (
    <div className={`relative w-40 h-40 flex-shrink-0 rounded-xl overflow-hidden border transition-all duration-300 ${
      isHighlight
        ? 'border-cyan-400/80 shadow-[0_0_30px_rgba(0,240,255,0.3)] scale-105 z-20'
        : 'border-white/20 shadow-lg'
    }`} style={{ background: avatar.bg, ...containerStyle }}>
      {/* Background ambiance */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/30 to-transparent pointer-events-none" />

      {/* Label / Nameplate */}
      <div className="absolute top-2 left-2 right-2 flex justify-between items-center z-10">
        <span className="px-2 py-0.5 rounded bg-black/60 text-[10px] font-bold text-cyan-200 tracking-wider uppercase border border-white/10">
          Oche Cam
        </span>
        {animState === ThrowState.WALKING && (
          <span className="px-2 py-0.5 rounded bg-fuchsia-500/80 text-[10px] font-bold text-white tracking-widest uppercase animate-pulse">
            Walk On
          </span>
        )}
      </div>

      {/* The player */}
      <div className="absolute inset-0 flex items-end justify-center pt-6" style={charStyle}>
        <Caricature variant={avatar.variant} pose={pose} className="h-full w-auto" />
      </div>

      <style>{`
        @keyframes oche-walk-on {
          0% { transform: translateX(100%); opacity: 0; }
          100% { transform: translateX(0); opacity: 1; }
        }
        @keyframes oche-walk-bounce {
          0% { transform: translateY(0); }
          100% { transform: translateY(-5px); }
        }
        @keyframes oche-idle-bob {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-4px); }
        }
        @keyframes oche-celebrate-pulse {
          0% { box-shadow: 0 0 20px rgba(0,255,0,0.2); border-color: rgba(0,255,0,0.5); }
          100% { box-shadow: 0 0 50px rgba(0,255,0,0.6); border-color: rgba(0,255,0,0.9); }
        }
        @keyframes oche-celebrate-bounce {
          0% { transform: translateY(0) scale(1); }
          100% { transform: translateY(-12px) scale(1.06); }
        }
      `}</style>
    </div>
  );
}
