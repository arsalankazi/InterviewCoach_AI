/**
 * static/js/avatar/lip_sync.js
 *
 * Real-time Speech-Synced Lip-Sync Engine for 2D Corporate Avatar.
 *
 * Combines two complementary synchronization layers:
 * 1. Primary Word-Boundary Event Listener (SpeechSynthesisUtterance.onboundary)
 *    capturing phoneme/vowel emphasis at word transitions.
 * 2. High-Precision requestAnimationFrame Viseme Cadence Oscillator
 *    cycling natural mouth movements between word boundaries.
 */

class LipSyncEngine {
    constructor() {
        this.mouthElem = null;
        this.isSpeaking = false;
        this.animFrameId = null;
        this.lastVisemeTime = 0;
        this.cadenceIndex = 0;

        // Morphing path definitions (coordinates matching viewBox 0 0 200 240)
        this.VISEMES = {
            closed: 'M 88 121 Q 100 125 112 121',
            half:   'M 89 120 Q 100 128 111 120 Q 100 117 89 120 Z',
            open:   'M 87 119 Q 100 133 113 119 Q 100 115 87 119 Z',
            round:  'M 91 119 Q 100 131 109 119 Q 100 114 91 119 Z'
        };

        this.visemeCadence = ['half', 'open', 'half', 'closed', 'open', 'round', 'half', 'closed'];
        this.stepOscillator = this.stepOscillator.bind(this);
    }

    /**
     * Bind DOM mouth element
     * @param {Element} svgRoot - Root SVG element
     */
    init(svgRoot) {
        this.stop();
        if (!svgRoot) return;
        this.mouthElem = svgRoot.querySelector('#avatar-mouth') || document.getElementById('avatar-mouth');
        this.setViseme('closed');
    }

    /**
     * Update the mouth path to the specified viseme shape
     * @param {string} shapeKey - 'closed' | 'half' | 'open' | 'round'
     */
    setViseme(shapeKey) {
        if (!this.mouthElem) return;
        const pathData = this.VISEMES[shapeKey] || this.VISEMES.closed;
        this.mouthElem.setAttribute('d', pathData);
    }

    /**
     * requestAnimationFrame viseme cadence loop
     * @param {number} timestamp - High resolution timer from RAF
     */
    stepOscillator(timestamp) {
        if (!this.isSpeaking) return;

        if (!this.lastVisemeTime || timestamp - this.lastVisemeTime > 120) {
            this.lastVisemeTime = timestamp;
            this.cadenceIndex = (this.cadenceIndex + 1) % this.visemeCadence.length;
            this.setViseme(this.visemeCadence[this.cadenceIndex]);
        }

        this.animFrameId = requestAnimationFrame(this.stepOscillator);
    }

    /**
     * Start active lip-sync on speech playback
     * @param {SpeechSynthesisUtterance} utterance - Active speech synthesis object
     * @param {string} text - Spoken dialogue text
     */
    start(utterance, text) {
        this.isSpeaking = true;
        this.cadenceIndex = 0;
        this.lastVisemeTime = 0;

        if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
        this.animFrameId = requestAnimationFrame(this.stepOscillator);

        // Hook word boundaries for precise vowel mouth shapes
        if (utterance) {
            utterance.onboundary = (event) => {
                if (!this.isSpeaking) return;
                const idx = event.charIndex || 0;
                const char = (text && text[idx]) ? text[idx].toLowerCase() : '';
                if (['o', 'u', 'w'].includes(char)) {
                    this.setViseme('round');
                } else if (['a', 'e', 'i'].includes(char)) {
                    this.setViseme('open');
                } else {
                    this.setViseme('half');
                }
                this.lastVisemeTime = performance.now();
            };
        }
    }

    /**
     * Stop lip-sync and immediately reset mouth to neutral closed smile
     */
    stop() {
        this.isSpeaking = false;
        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId);
            this.animFrameId = null;
        }
        this.setViseme('closed');
    }
}

// Export globally for browser environment
if (typeof window !== 'undefined') {
    window.LipSyncEngine = LipSyncEngine;
}
