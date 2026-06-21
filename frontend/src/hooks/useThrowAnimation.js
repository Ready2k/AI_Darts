import { useState, useCallback, useRef, useEffect } from 'react';
import { ThrowState, TIMING } from '../config/timing';

export function useThrowAnimation() {
  const [animState, setAnimState] = useState(ThrowState.IDLE);
  const [currentDart, setCurrentDart] = useState(null);

  const timerRefs = useRef([]);
  // Holds the current throw's onScored until it fires. If a new throw (or a
  // walk-on) preempts this one before its SCORING step, we flush it here so the
  // displayed game state is never stranded a dart behind — that stranding is
  // what froze the cinematic view when darts arrived faster than the animation.
  const pendingScored = useRef(null);

  const flushScored = useCallback(() => {
    const f = pendingScored.current;
    pendingScored.current = null;
    if (f) { try { f(); } catch { /* ignore */ } }
  }, []);

  const clearTimers = useCallback(() => {
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
  }, []);

  useEffect(() => {
    return clearTimers;
  }, [clearTimers]);

  const triggerWalkOn = useCallback(() => {
    flushScored()
    clearTimers()
    setAnimState(ThrowState.WALKING)
    const t = setTimeout(() => setAnimState(ThrowState.IDLE), TIMING.WALK_ON_DURATION)
    timerRefs.current.push(t)
  }, [clearTimers, flushScored])

  const triggerThrow = useCallback(({ dartResult, event = null, onScored }) => {
    flushScored();          // commit the previous dart if it hasn't scored yet
    clearTimers();
    setCurrentDart(dartResult);
    pendingScored.current = onScored ? () => onScored(dartResult) : null;

    const mult = (event?.replay?.slowMotion) ? (event.replay.multiplier || TIMING.SLOW_MO_MULTIPLIER) : 1;
    if (event?.replay?.slowMotion) {
      setAnimState(ThrowState.REPLAYING);
    }

    // 1. AIMING
    const aimState = (event?.replay?.slowMotion) ? ThrowState.REPLAYING : ThrowState.AIMING;
    setAnimState(aimState);

    const aimTimer = setTimeout(() => {
      // 2. THROWING
      setAnimState(ThrowState.THROWING);

      const throwTimer = setTimeout(() => {
        // 3. DART_FLIGHT
        setAnimState(ThrowState.DART_FLIGHT);

        const flightTimer = setTimeout(() => {
          // 4. IMPACT
          setAnimState(ThrowState.IMPACT);

          const impactTimer = setTimeout(() => {
            // 5. SCORING
            setAnimState(ThrowState.SCORING);
            flushScored();   // fire this throw's onScored exactly once

            // Return to IDLE shortly after
            const resetTimer = setTimeout(() => {
              if (event?.isCheckout) {
                setAnimState(ThrowState.CELEBRATING);
                timerRefs.current.push(setTimeout(() => setAnimState(ThrowState.IDLE), TIMING.CELEBRATION_DURATION));
              } else {
                setAnimState(ThrowState.IDLE);
              }
              setCurrentDart(null);
            }, 300 * mult);
            timerRefs.current.push(resetTimer);

          }, TIMING.IMPACT_DELAY * mult);
          timerRefs.current.push(impactTimer);

        }, TIMING.FLIGHT_DURATION * mult);
        timerRefs.current.push(flightTimer);

      }, TIMING.THROW_DURATION * mult);
      timerRefs.current.push(throwTimer);

    }, TIMING.AIM_DURATION * mult);
    timerRefs.current.push(aimTimer);

  }, [clearTimers, flushScored]);

  return {
    animState,
    currentDart,
    triggerThrow,
    triggerWalkOn,
  };
}
