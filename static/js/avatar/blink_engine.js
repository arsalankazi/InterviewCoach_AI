/**
 * static/js/avatar/blink_engine.js
 *
 * Handles natural autonomous eye-blinking for the 2D vector avatar.
 * Runs continuously in all avatar states (idle, listening, thinking, speaking)
 * with a realistic human randomized interval between 2 and 6 seconds.
 */

class BlinkEngine {
    constructor() {
        this.leftEye = null;
        this.rightEye = null;
        this.timeoutId = null;
        this.isRunning = false;
        this.blinkDurationMs = 140;
    }

    /**
     * Bind DOM elements for left and right eyes
     * @param {Element} svgRoot - Root SVG element of the mounted avatar
     */
    init(svgRoot) {
        this.stop();
        if (!svgRoot) return;

        this.leftEye = svgRoot.querySelector('#avatar-left-eye') || document.getElementById('avatar-left-eye');
        this.rightEye = svgRoot.querySelector('#avatar-right-eye') || document.getElementById('avatar-right-eye');

        if (this.leftEye && this.rightEye) {
            this.start();
        }
    }

    /**
     * Start the continuous blinking loop
     */
    start() {
        this.isRunning = true;
        this.scheduleNextBlink();
    }

    /**
     * Stop the blinking loop
     */
    stop() {
        this.isRunning = false;
        if (this.timeoutId) {
            clearTimeout(this.timeoutId);
            this.timeoutId = null;
        }
        if (this.leftEye) this.leftEye.classList.remove('is-blinking');
        if (this.rightEye) this.rightEye.classList.remove('is-blinking');
    }

    /**
     * Execute a single natural eyelid blink
     */
    triggerBlink() {
        if (!this.isRunning || !this.leftEye || !this.rightEye) return;

        this.leftEye.classList.add('is-blinking');
        this.rightEye.classList.add('is-blinking');

        setTimeout(() => {
            if (this.leftEye) this.leftEye.classList.remove('is-blinking');
            if (this.rightEye) this.rightEye.classList.remove('is-blinking');
        }, this.blinkDurationMs);

        this.scheduleNextBlink();
    }

    /**
     * Schedule the next random blink (2000ms - 6000ms interval)
     */
    scheduleNextBlink() {
        if (!this.isRunning) return;
        if (this.timeoutId) clearTimeout(this.timeoutId);

        const nextDelay = 2000 + Math.random() * 4000;
        this.timeoutId = setTimeout(() => this.triggerBlink(), nextDelay);
    }
}

// Export globally for browser environment
if (typeof window !== 'undefined') {
    window.BlinkEngine = BlinkEngine;
}
