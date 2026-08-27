/**
 * static/js/avatar/avatar_states.js
 *
 * Defines the 4 interactive states for the AI interviewer avatar:
 * - IDLE: Calm vertical breathing float, neutral smile, continuous natural eye-blinking.
 * - LISTENING: Active mic attentive state, slight head tilt toward candidate, emerald glow ring.
 * - THINKING: Gemini API in-flight generation, furrowed eyebrows in contemplation, sapphire pulse ring.
 * - SPEAKING: Dynamic lip-sync viseme animation, raised engaging eyebrows, speaking glow ring.
 */

const AvatarStates = Object.freeze({
    IDLE: 'idle',
    LISTENING: 'listening',
    THINKING: 'thinking',
    SPEAKING: 'speaking'
});

const AvatarStateConfig = Object.freeze({
    [AvatarStates.IDLE]: {
        cssClass: 'state-idle',
        glowRingClass: 'ring-idle',
        browOffset: 0,
        headTiltDeg: 0,
        mouthViseme: 'closed'
    },
    [AvatarStates.LISTENING]: {
        cssClass: 'state-listening',
        glowRingClass: 'ring-listening',
        browOffset: 0,
        headTiltDeg: 1.8, // Attentive tilt toward candidate
        mouthViseme: 'closed'
    },
    [AvatarStates.THINKING]: {
        cssClass: 'state-thinking',
        glowRingClass: 'ring-thinking',
        browOffset: 1.2, // Subtle furrowed brow in contemplation
        headTiltDeg: -1.0,
        mouthViseme: 'closed'
    },
    [AvatarStates.SPEAKING]: {
        cssClass: 'state-speaking',
        glowRingClass: 'ring-speaking',
        browOffset: -1.8, // Elevated engaging eyebrows
        headTiltDeg: 0,
        mouthViseme: 'cadence' // Driven by LipSyncEngine
    }
});

// Export globally for browser environment
if (typeof window !== 'undefined') {
    window.AvatarStates = AvatarStates;
    window.AvatarStateConfig = AvatarStateConfig;
}
