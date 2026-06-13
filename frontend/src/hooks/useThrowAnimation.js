import { useState, useCallback, useRef, useEffect } from 'react';
import { ThrowState, TIMING } from '../config/timing';

export function useThrowAnimation() {
  const [animState, setAnimState] = useState(ThrowState.IDLE);
  const [currentDart, setCurrentDart] = useState(null);
  
  const timerRefs = useRef([]);

  const clearTimers = useCallback(() => {
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
  }, []);

  useEffect(() => {
    return clearTimers;
  }, [clearTimers]);

  const triggerWalkOn = useCallback(() => {
    clearTimers()
    setAnimState(ThrowState.WALKING)
    const t = setTimeout(() => setAnimState(ThrowState.IDLE), TIMING.WALK_ON_DURATION)
    timerRefs.current.push(t)
  }, [clearTimers])

  const triggerThrow = useCallback(({ dartResult, event = null, onScored }) => {
    clearTimers();
    setCurrentDart(dartResult);

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
            if (onScored) onScored(dartResult);
            
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
    
  }, [clearTimers]);

  return {
    animState,
    currentDart,
    triggerThrow,
    triggerWalkOn,
  };
}
