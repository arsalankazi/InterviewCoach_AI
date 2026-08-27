/**
 * static/js/avatar/avatar_controller.js
 *
 * Central Controller for 2D Corporate AI Interviewer Avatar.
 *
 * Responsibilities:
 * - Mounts SVG vector portrait asynchronously into #avatar-mount-point
 * - Coordinates BlinkEngine, LipSyncEngine, and AvatarStates
 * - Exposes high-level state management API for interview_room.js
 * - Guarantees graceful degradation on browser incompatibilities
 */

class AvatarController {
    constructor() {
        this.container = null;
        this.svgElement = null;
        this.headElement = null;
        this.eyebrowsGroup = null;
        this.leftBrow = null;
        this.rightBrow = null;

        this.gender = 'male';
        this.currentState = (typeof AvatarStates !== 'undefined') ? AvatarStates.IDLE : 'idle';

        this.blinkEngine = (typeof BlinkEngine !== 'undefined') ? new BlinkEngine() : null;
        this.lipSyncEngine = (typeof LipSyncEngine !== 'undefined') ? new LipSyncEngine() : null;
        this.isInitialized = false;
    }

    /**
     * Initialize avatar controller and load SVG asset
     * @param {Object} options
     * @param {string} options.mountPointId - ID of DOM container (e.g. 'avatar-mount-point')
     * @param {string} options.gender - 'male' | 'female'
     */
    async init(options = {}) {
        const mountId = options.mountPointId || 'avatar-mount-point';
        this.container = document.getElementById(mountId);
        this.gender = (options.gender || 'male').toLowerCase();

        if (!this.container) {
            console.warn(`[AvatarController] Container #${mountId} not found.`);
            return;
        }

        try {
            await this.loadAvatarSvg();
            this.bindElements();

            if (this.blinkEngine) this.blinkEngine.init(this.svgElement);
            if (this.lipSyncEngine) this.lipSyncEngine.init(this.svgElement);

            this.isInitialized = true;
            this.setState((typeof AvatarStates !== 'undefined') ? AvatarStates.IDLE : 'idle');
            console.log(`[AvatarController] Corporate avatar (${this.gender}) mounted successfully.`);
        } catch (err) {
            console.error('[AvatarController] Error initializing avatar:', err);
        }
    }

    /**
     * Fetch and inject SVG asset into the container
     */
    async loadAvatarSvg() {
        const svgPath = `/static/avatars/${this.gender}_avatar.svg`;
        try {
            const res = await fetch(svgPath);
            if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${svgPath}`);
            const svgText = await res.text();
            this.container.innerHTML = svgText;
        } catch (fetchErr) {
            console.warn('[AvatarController] Fetch failed, checking existing inline SVG:', fetchErr);
            // If already present in DOM as fallback, keep it
        }
    }

    /**
     * Cache animatable element references
     */
    bindElements() {
        this.svgElement = this.container.querySelector('svg') || this.container;
        this.headElement = this.svgElement.querySelector('#avatar-head');
        this.leftBrow = this.svgElement.querySelector('#avatar-left-brow');
        this.rightBrow = this.svgElement.querySelector('#avatar-right-brow');
        this.eyebrowsGroup = this.svgElement.querySelector('#avatar-eyebrows');
    }

    /**
     * Set interactive avatar state
     * @param {string} stateName - 'idle' | 'listening' | 'thinking' | 'speaking'
     */
    setState(stateName) {
        if (!stateName) return;
        this.currentState = stateName;

        const config = (typeof AvatarStateConfig !== 'undefined')
            ? AvatarStateConfig[stateName]
            : null;

        // Update container classes for glow rings and lighting transitions
        if (this.container) {
            this.container.classList.remove('state-idle', 'state-listening', 'state-thinking', 'state-speaking');
            this.container.classList.add(`state-${stateName}`);
        }

        // Apply state-specific head tilt
        if (this.headElement && config) {
            const tilt = config.headTiltDeg || 0;
            this.headElement.style.transform = tilt !== 0 ? `rotate(${tilt}deg)` : '';
            this.headElement.style.transition = 'transform 0.35s cubic-bezier(0.16, 1, 0.3, 1)';
        }

        // Apply state-specific eyebrow offset
        if (config && typeof config.browOffset === 'number') {
            const browY = config.browOffset;
            if (this.leftBrow) this.leftBrow.style.transform = `translateY(${browY}px)`;
            if (this.rightBrow) this.rightBrow.style.transform = `translateY(${browY}px)`;
        }

        // Stop lip-sync if transitioning away from speaking
        if (stateName !== 'speaking' && this.lipSyncEngine) {
            this.lipSyncEngine.stop();
        }
    }

    /**
     * Trigger speech lip-sync animation
     * @param {SpeechSynthesisUtterance} utterance
     * @param {string} text
     */
    speak(utterance, text) {
        this.setState((typeof AvatarStates !== 'undefined') ? AvatarStates.SPEAKING : 'speaking');
        if (this.lipSyncEngine) {
            this.lipSyncEngine.start(utterance, text);
        }
    }

    /**
     * Stop speaking and return to idle state
     */
    stopSpeaking() {
        if (this.lipSyncEngine) {
            this.lipSyncEngine.stop();
        }
        this.setState((typeof AvatarStates !== 'undefined') ? AvatarStates.IDLE : 'idle');
    }

    /**
     * Reset avatar to default calm idle state
     */
    reset() {
        if (this.lipSyncEngine) this.lipSyncEngine.stop();
        this.setState((typeof AvatarStates !== 'undefined') ? AvatarStates.IDLE : 'idle');
    }
}

// Global singleton instance for easy integration
if (typeof window !== 'undefined') {
    window.AvatarController = AvatarController;
    window.avatarController = new AvatarController();
}
