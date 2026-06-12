export const ThrowState = {
  IDLE: 'idle',
  WALKING: 'walking',
  AIMING: 'aiming',
  THROWING: 'throwing',
  DART_FLIGHT: 'dart_flight',
  IMPACT: 'impact',
  SCORING: 'scoring',
  CELEBRATING: 'celebrating',
  DEFEATED: 'defeated',
  REPLAYING: 'replaying'
};

// Timing constants in milliseconds
export const TIMING = {
  AIM_DURATION: 400,        // Time spent in aiming pose
  THROW_DURATION: 150,      // Time for follow-through release pose
  FLIGHT_DURATION: 350,     // Time dart is flying (CSS animation duration)
  IMPACT_DELAY: 150,        // Time to wait after impact before scoring/resetting
  
  // Demo Mode Constants
  SLOW_MO_MULTIPLIER: 3,    // Speed multiplier for checkout replays
  WALK_ON_DURATION: 2000,   // Time for avatar to slide in
  CELEBRATION_DURATION: 3000,
  DEFEAT_DURATION: 3000
};
