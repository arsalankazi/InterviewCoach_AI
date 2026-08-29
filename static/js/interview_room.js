/**
 * static/js/interview_room.js
 *
 * Module 11 — Core conversational exchange, typing animations, Stage 1
 * initialization, auto-scrolling, and resilient retry logic.
 *
 * Module 10 — Voice I/O (Web Speech API), animated AI avatar, and
 * student camera self-view (getUserMedia). All client-side, no backend changes.
 *
 * Module 10 Polish — Thinking animation, ambient timer, 3-2-1 countdown,
 * fullscreen toggle, thinking filler cue, stage progress indicator, and
 * rotating tips banner.
 */

document.addEventListener('DOMContentLoaded', () => {
    const roomWrapper = document.querySelector('.interview-room-wrapper');
    if (!roomWrapper) return;

    // ─────────────────────────────────────────────
    // Session Configuration & State
    // ─────────────────────────────────────────────
    const sessionId         = parseInt(roomWrapper.dataset.sessionId, 10);
    const sessionStatus     = roomWrapper.dataset.sessionStatus || 'setup';
    const interviewerName   = roomWrapper.dataset.interviewerName || 'AI Interviewer';
    const interviewerGender = (roomWrapper.dataset.interviewerGender || 'male').toLowerCase();
    const studentName       = roomWrapper.dataset.studentName || 'Candidate';
    const jobRole           = roomWrapper.dataset.jobRole || 'the position';
    const isCompleted       = sessionStatus === 'completed';

    // ─────────────────────────────────────────────
    // DOM Elements — Module 11 core
    // ─────────────────────────────────────────────
    const chatContainer   = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');
    const chatInput       = document.getElementById('chat-input');
    const btnSend         = document.getElementById('btn-send');
    const turnCountElem   = document.getElementById('turn-count');
    const errorBanner     = document.getElementById('chat-error-banner');
    const errorTextElem   = document.getElementById('error-message-text');
    const btnRetry        = document.getElementById('btn-retry');

    let isSubmitting      = false;
    let pendingAnswerText = null;

    // ─────────────────────────────────────────────
    // Utilities
    // ─────────────────────────────────────────────
    function getCurrentTimeString() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function scrollToBottom(smooth = true) {
        if (!chatContainer) return;
        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto'
        });
    }

    function updateTurnCount() {
        if (!turnCountElem || !chatContainer) return;
        const turns = chatContainer.querySelectorAll('.message-turn:not(.typing-wrapper)').length;
        turnCountElem.textContent = turns;
    }

    // ─────────────────────────────────────────────
    // appendMessageBubble — builds + inserts a chat turn
    // ─────────────────────────────────────────────
    function appendMessageBubble(sender, messageText, timestamp = null) {
        const turnDiv     = document.createElement('div');
        turnDiv.className = `message-turn message-${sender} animate-bubble`;

        const timeStr     = timestamp || getCurrentTimeString();
        const avatarEmoji = interviewerGender === 'female' ? '👩‍💼' : '👨‍💼';
        const avatarClass = interviewerGender === 'female' ? 'avatar-female' : 'avatar-male';

        if (sender === 'ai') {
            turnDiv.innerHTML = `
                <div class="message-avatar-wrap ${avatarClass}">${avatarEmoji}</div>
                <div class="message-body">
                    <div class="message-sender-name"></div>
                    <div class="message-bubble bubble-ai"><p class="bubble-text"></p></div>
                    <div class="message-timestamp">${timeStr}</div>
                </div>
            `;
            turnDiv.querySelector('.message-sender-name').textContent = interviewerName;
            turnDiv.querySelector('.bubble-text').textContent = messageText;
        } else {
            turnDiv.innerHTML = `
                <div class="message-body">
                    <div class="message-sender-name"></div>
                    <div class="message-bubble bubble-student"><p class="bubble-text"></p></div>
                    <div class="message-timestamp">${timeStr}</div>
                </div>
                <div class="message-avatar-wrap avatar-student">🎓</div>
            `;
            turnDiv.querySelector('.message-sender-name').textContent = studentName;
            turnDiv.querySelector('.bubble-text').textContent = messageText;
        }

        if (typingIndicator && typingIndicator.parentNode === chatContainer) {
            chatContainer.insertBefore(turnDiv, typingIndicator);
        } else {
            chatContainer.appendChild(turnDiv);
        }

        updateTurnCount();
        scrollToBottom(true);

        // Module 10: speak new AI messages aloud
        if (sender === 'ai' && messageText) {
            try {
                if (typeof VoiceOutputManager !== 'undefined' && VoiceOutputManager.speak) {
                    VoiceOutputManager.speak(messageText);
                }
            } catch (err) {
                console.warn('[TTS] speak error:', err);
            }
        }

        // Live stats & transcript tracking
        try {
            if (typeof SessionStatsManager !== 'undefined') {
                if (sender === 'student') {
                    SessionStatsManager.recordStudentMessage(messageText);
                } else {
                    SessionStatsManager.recordAiMessage();
                }
            }
            if (typeof TranscriptManager !== 'undefined') {
                TranscriptManager.update();
            }
        } catch (statsErr) {
            console.warn('[Stats/Transcript] update error:', statsErr);
        }
    }

    // ─────────────────────────────────────────────
    // Typing Indicator
    // ─────────────────────────────────────────────
    function showTyping() {
        if (typingIndicator) { typingIndicator.style.display = 'flex'; scrollToBottom(true); }
    }

    function hideTyping() {
        if (typingIndicator) typingIndicator.style.display = 'none';
    }

    // ─────────────────────────────────────────────
    // Error Banner
    // ─────────────────────────────────────────────
    function showError(message) {
        if (errorBanner && errorTextElem) {
            errorTextElem.textContent = message || 'Failed to communicate with AI interviewer.';
            errorBanner.style.display = 'flex';
            scrollToBottom(true);
        }
    }

    function hideError() {
        if (errorBanner) errorBanner.style.display = 'none';
    }

    // ─────────────────────────────────────────────
    // Core Dispatcher: sendTurn
    // ─────────────────────────────────────────────
    async function sendTurn(answerText) {
        if (isSubmitting || isCompleted) return;

        isSubmitting      = true;
        pendingAnswerText  = answerText;
        hideError();
        showTyping();
        AvatarAnimator.startThinking();
        ThinkingFillerManager.show();

        if (chatInput) {
            chatInput.disabled = true;
            chatInput.value = '';
            chatInput.style.height = 'auto';
        }
        if (btnSend) btnSend.disabled = true;

        let responseData = null;

        try {
            const response = await fetch(`/student/interviews/${sessionId}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ answer: answerText })
            });

            if (!response.ok) {
                const errJson = await response.json().catch(() => ({}));
                const errMsg = errJson.error || `Server returned error (${response.status})`;
                showError(errMsg);
                return;
            }

            responseData = await response.json();
        } catch (networkError) {
            console.error('Interview chat connection error:', networkError);
            showError('Network connectivity issue. Please check your connection and retry.');
            return;
        } finally {
            hideTyping();
            ThinkingFillerManager.hide();
            AvatarAnimator.stopThinking();
            isSubmitting = false;

            if (!isCompleted) {
                if (chatInput) {
                    chatInput.disabled = false;
                    chatInput.value = '';
                    chatInput.style.height = 'auto';
                    chatInput.focus();
                }
                if (btnSend) btnSend.disabled = false;
            }
            scrollToBottom(true);
        }

        // Process and display AI response safely outside network try/catch
        try {
            if (responseData && (responseData.success || responseData.ai_message)) {
                appendMessageBubble('ai', responseData.ai_message);
                pendingAnswerText = null;

                // #8: Update stage progress from API response
                if (responseData.stage) {
                    StageProgressManager.update(responseData.stage, responseData.stage_name || '');
                }
            } else {
                const err = (responseData && responseData.error) ? responseData.error : 'Unable to receive interviewer response.';
                showError(err);
            }
        } catch (renderError) {
            console.error('Error displaying AI response bubble:', renderError);
        }
    }

    // ─────────────────────────────────────────────
    // Student Submit Handler
    // ─────────────────────────────────────────────
    function handleStudentSubmit() {
        if (!chatInput || isSubmitting || isCompleted) return;
        const text = chatInput.value.trim();
        if (!text) return;
        
        // Stop and reset voice input tracking so old transcription is not re-used
        VoiceInputManager.reset();

        appendMessageBubble('student', text);
        chatInput.value        = '';
        chatInput.style.height = 'auto';
        sendTurn(text);
    }

    if (btnSend) {
        btnSend.addEventListener('click', (e) => { e.preventDefault(); handleStudentSubmit(); });
    }

    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleStudentSubmit(); }
        });
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = `${Math.min(chatInput.scrollHeight, 130)}px`;
        });
    }

    if (btnRetry) {
        btnRetry.addEventListener('click', (e) => { e.preventDefault(); hideError(); sendTurn(pendingAnswerText); });
    }


    // =============================================================
    // Photo-Based Avatar & Real-time Overlay Lip-Sync Engine
    // =============================================================
    const AvatarLipSyncEngine = (() => {
        const mouthElem = document.getElementById('avatar-mouth');
        const leftEye   = document.getElementById('overlay-eye-left') || document.getElementById('avatar-left-eye');
        const rightEye  = document.getElementById('overlay-eye-right') || document.getElementById('avatar-right-eye');

        // Dynamic morphing mouth path coordinates (Bug 1 Fix: Subtle, natural micro-visemes)
        const VISEMES = {
            closed: 'M 20 30 Q 50 32 80 30',
            half:   'M 22 29 Q 50 36 78 29 Q 50 25 22 29 Z',
            open:   'M 20 28 Q 50 40 80 28 Q 50 20 20 28 Z',
            round:  'M 28 27 Q 50 38 72 27 Q 50 20 28 27 Z'
        };

        const visemeCadence = ['half', 'open', 'half', 'closed', 'open', 'round', 'half', 'closed'];

        let isSpeaking         = false;
        let animFrameId        = null;
        let lastVisemeTime     = 0;
        let cadenceIndex       = 0;
        let blinkTimeoutId     = null;

        // ── Autonomous Natural Eye-Blinking (Randomized 2-6s) ───
        function triggerBlink() {
            if (leftEye && rightEye) {
                leftEye.classList.add('is-blinking');
                rightEye.classList.add('is-blinking');

                setTimeout(() => {
                    if (leftEye)  leftEye.classList.remove('is-blinking');
                    if (rightEye) rightEye.classList.remove('is-blinking');
                }, 140);
            }
            scheduleBlink();
        }

        function scheduleBlink() {
            clearTimeout(blinkTimeoutId);
            const delay = 2200 + Math.random() * 4000;
            blinkTimeoutId = setTimeout(triggerBlink, delay);
        }

        // Initialize continuous blinking cycle
        scheduleBlink();

        // ── Set Viseme Mouth Shape ──────────────────────────────
        function setViseme(visemeKey) {
            if (!mouthElem) return;
            const pathData = VISEMES[visemeKey] || VISEMES.closed;
            mouthElem.setAttribute('d', pathData);
        }

        // ── High-Precision RAF Viseme Oscillator ────────────────
        function visemeStep(timestamp) {
            if (!isSpeaking) return;

            if (!lastVisemeTime || timestamp - lastVisemeTime > 125) {
                lastVisemeTime = timestamp;
                cadenceIndex = (cadenceIndex + 1) % visemeCadence.length;
                setViseme(visemeCadence[cadenceIndex]);
            }

            animFrameId = requestAnimationFrame(visemeStep);
        }

        // ── Start / Stop Speaking ───────────────────────────────
        function start(utterance, text) {
            isSpeaking     = true;
            cadenceIndex   = 0;
            lastVisemeTime = 0;

            if (animFrameId) cancelAnimationFrame(animFrameId);
            animFrameId = requestAnimationFrame(visemeStep);

            // Hook SpeechSynthesis onboundary event for word-level sync pulses
            if (utterance) {
                utterance.onboundary = (event) => {
                    if (!isSpeaking) return;
                    const idx = event.charIndex || 0;
                    const char = (text && text[idx]) ? text[idx].toLowerCase() : '';
                    if (['o', 'u', 'w'].includes(char)) {
                        setViseme('round');
                    } else if (['a', 'e', 'i'].includes(char)) {
                        setViseme('open');
                    } else {
                        setViseme('half');
                    }
                    lastVisemeTime = performance.now();
                };
            }
        }

        function stop() {
            isSpeaking = false;
            if (animFrameId) {
                cancelAnimationFrame(animFrameId);
                animFrameId = null;
            }
            setViseme('closed');
        }

        return { start, stop, setViseme };
    })();


    // =============================================================
    // MODULE 10 — Part C: AvatarAnimator
    // Three states: idle | is-thinking | is-speaking
    // =============================================================
    const AvatarAnimator = (() => {
        const ring         = document.getElementById('avatar-speaking-ring');
        const speakingBadge= document.getElementById('ai-speaking-badge');
        const speakingText = document.getElementById('ai-speaking-text');

        function startSpeaking(utterance = null, text = '') {
            if (ring) {
                ring.classList.remove('is-thinking');
                ring.classList.add('is-speaking');
            }
            if (speakingBadge) {
                speakingBadge.classList.add('is-speaking');
                if (speakingText) speakingText.textContent = 'SPEAKING...';
            }
            AvatarLipSyncEngine.start(utterance, text);
        }

        function stopSpeaking() {
            if (ring) ring.classList.remove('is-speaking');
            if (speakingBadge) {
                speakingBadge.classList.remove('is-speaking');
                if (speakingText) speakingText.textContent = 'IDLE';
            }
            AvatarLipSyncEngine.stop();
        }

        function startThinking() {
            if (!ring || ring.classList.contains('is-speaking')) return;
            ring.classList.add('is-thinking');
            if (speakingBadge) {
                speakingBadge.classList.remove('is-speaking');
                if (speakingText) speakingText.textContent = 'THINKING...';
            }
        }

        function stopThinking() {
            if (ring) ring.classList.remove('is-thinking');
            if (speakingBadge && !ring.classList.contains('is-speaking')) {
                if (speakingText) speakingText.textContent = 'IDLE';
            }
        }

        return { startSpeaking, stopSpeaking, startThinking, stopThinking };
    })();


    // =============================================================
    // MODULE 10 — Part A: VoiceOutputManager (Text-to-Speech)
    // =============================================================
    const VoiceOutputManager = (() => {
        const btnTts      = document.getElementById('btn-tts-toggle');
        const subtitleEl  = document.getElementById('ai-subtitle-text');
        const synth       = window.speechSynthesis;
        let isMuted       = false;
        let voices        = [];

        function loadVoices() { voices = synth ? synth.getVoices() : []; }
        if (synth) { loadVoices(); synth.addEventListener('voiceschanged', loadVoices); }

        function pickVoice() {
            if (!voices.length) return null;
            const preferred = interviewerGender === 'female'
                ? voices.find(v => v.lang.startsWith('en') && /female|woman|zira|samantha|victoria|karen/i.test(v.name))
                : voices.find(v => v.lang.startsWith('en') && /male|man|david|daniel|google us/i.test(v.name));
            return preferred || voices.find(v => v.lang.startsWith('en')) || voices[0] || null;
        }

        function setSubtitle(text) {
            if (subtitleEl && text) {
                subtitleEl.textContent = text;
            }
        }

        function speak(text) {
            setSubtitle(text);
            if (!synth || !text || isMuted) return;
            synth.cancel();
            const utterance  = new SpeechSynthesisUtterance(text);
            utterance.rate   = 0.95;
            utterance.pitch  = 1.0;
            utterance.volume = 1.0;
            const voice = pickVoice();
            if (voice) utterance.voice = voice;

            utterance.onstart = () => AvatarAnimator.startSpeaking(utterance, text);
            utterance.onend   = () => AvatarAnimator.stopSpeaking();
            utterance.onerror = () => AvatarAnimator.stopSpeaking();

            synth.speak(utterance);
        }

        function mute() {
            isMuted = true;
            if (synth) synth.cancel();
            AvatarAnimator.stopSpeaking();
            if (btnTts) {
                const iconEl = btnTts.querySelector('.ctrl-icon');
                if (iconEl) iconEl.textContent = '🔇';
                const labelEl = btnTts.querySelector('.ctrl-label');
                if (labelEl) labelEl.textContent = 'Speaker Off';
                btnTts.setAttribute('aria-label', 'Unmute AI voice');
                btnTts.classList.add('is-muted');
            }
        }

        function unmute() {
            isMuted = false;
            if (btnTts) {
                const iconEl = btnTts.querySelector('.ctrl-icon');
                if (iconEl) iconEl.textContent = '🔊';
                const labelEl = btnTts.querySelector('.ctrl-label');
                if (labelEl) labelEl.textContent = 'Speaker On';
                btnTts.setAttribute('aria-label', 'Mute AI voice');
                btnTts.classList.remove('is-muted');
            }
        }

        function cancel() {
            if (synth) { synth.cancel(); }
            AvatarAnimator.stopSpeaking();
        }

        if (btnTts) btnTts.addEventListener('click', () => { isMuted ? unmute() : mute(); });
        window.addEventListener('pagehide', cancel);

        return { speak, mute, unmute, cancel, setSubtitle };
    })();


    // =============================================================
    // MODULE 10 — Part B: VoiceInputManager (Speech-to-Text)
    // continuous:true keeps the mic alive through natural pauses.
    // Preserves existing textarea content when toggled off & on.
    // finalTranscript accumulates confirmed words; interim shows
    // live preview. The mic only stops on explicit user action.
    // =============================================================
    const VoiceInputManager = (() => {
        const btnMic         = document.getElementById('btn-mic');
        const listeningBadge = document.getElementById('mic-listening-badge');
        const SpeechRec      = window.SpeechRecognition || window.webkitSpeechRecognition || null;

        if (!SpeechRec) {
            if (btnMic) {
                btnMic.disabled = true;
                btnMic.title    = 'Voice input is not supported in this browser. Please use Chrome or Edge.';
                btnMic.setAttribute('aria-label', 'Voice input unavailable');
            }
            return { start: () => {}, stop: () => {}, toggle: () => {}, reset: () => {} };
        }

        let isListening             = false; // true while the student intends the mic to be on
        let recognition             = null;
        let sessionPrefix           = '';    // stores text already in textarea prior to this mic activation
        let sessionFinalTranscript  = '';    // accumulates confirmed speech for the current mic session
        let restartBlocked          = false; // prevents restart loop on intentional stop

        // ── Build a fresh SpeechRecognition instance ──────────────────
        function buildRecognition() {
            const rec           = new SpeechRec();
            rec.continuous      = true;   // keep going through natural pauses
            rec.interimResults  = true;   // live preview while speaking
            rec.lang            = 'en-US';
            rec.maxAlternatives = 1;

            rec.onstart = () => {
                isListening = true;
                if (btnMic)         btnMic.classList.add('is-listening');
                if (listeningBadge) listeningBadge.classList.add('visible');
                if (chatInput)      chatInput.placeholder = 'Listening… speak your answer';
            };

            rec.onresult = (event) => {
                if (!chatInput) return;

                // Walk only the new results since last event (event.resultIndex onward)
                let interimChunk = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const result = event.results[i];
                    if (result.isFinal) {
                        // Append confirmed word(s) to the accumulator
                        sessionFinalTranscript += result[0].transcript;
                    } else {
                        interimChunk += result[0].transcript;
                    }
                }

                // Append newly transcribed speech (finals + interim) to what was already typed/spoken
                chatInput.value = sessionPrefix + sessionFinalTranscript + interimChunk;
                chatInput.style.height = 'auto';
                chatInput.style.height = `${Math.min(chatInput.scrollHeight, 130)}px`;
            };

            // onend fires when browser stops (e.g., brief silence or tab blur).
            // If the student hasn't explicitly stopped, restart transparently.
            rec.onend = () => {
                if (isListening && !restartBlocked) {
                    // Transparent restart: fold finalized words into sessionPrefix
                    sessionPrefix = sessionPrefix + sessionFinalTranscript;
                    sessionFinalTranscript = '';
                    try {
                        recognition = buildRecognition();
                        recognition.start();
                    } catch (e) {
                        console.warn('[VoiceInput] restart failed:', e);
                        _stopInternal();
                    }
                } else {
                    _stopInternal();
                }
            };

            rec.onerror = (event) => {
                // 'no-speech' is not a real error — just silence; let onend restart
                if (event.error === 'no-speech') return;
                console.warn('[VoiceInput] error:', event.error);
                restartBlocked = true;
                _stopInternal();
            };

            return rec;
        }

        // ── Internal teardown (called by onend or onerror) ────────────
        function _stopInternal() {
            isListening = false;
            if (btnMic)         btnMic.classList.remove('is-listening');
            if (listeningBadge) listeningBadge.classList.remove('visible');
            if (chatInput) {
                chatInput.placeholder = 'Type your answer here… (Press Enter to send, Shift+Enter for new line)';
                chatInput.focus();
            }
        }

        // ── Public API ────────────────────────────────────────────────
        function start() {
            if (isListening || isCompleted || !chatInput) return;

            // Preserve whatever text is currently in the textarea
            const currentVal = chatInput.value || '';
            sessionPrefix = currentVal.trim() ? currentVal.trimEnd() + ' ' : '';
            sessionFinalTranscript = '';
            restartBlocked = false;

            recognition = buildRecognition();
            try {
                recognition.start();
            } catch (e) {
                console.warn('[VoiceInput] start failed:', e);
                _stopInternal();
            }
        }

        function stop() {
            if (!isListening) return;
            restartBlocked = true; // signal onend not to restart
            isListening    = false;
            if (recognition) {
                try { recognition.stop(); } catch (_) {}
                recognition = null;
            }
            if (chatInput) {
                // Cleanly commit the combined text into the input
                chatInput.value = (sessionPrefix + sessionFinalTranscript).trim();
                chatInput.style.height = 'auto';
                chatInput.style.height = `${Math.min(chatInput.scrollHeight, 130)}px`;
            }
            sessionPrefix = '';
            sessionFinalTranscript = '';
            _stopInternal();
        }

        function reset() {
            if (isListening) {
                restartBlocked = true;
                isListening = false;
                if (recognition) {
                    try { recognition.stop(); } catch (_) {}
                    recognition = null;
                }
                _stopInternal();
            }
            sessionPrefix = '';
            sessionFinalTranscript = '';
        }

        function toggle() { isListening ? stop() : start(); }
        if (btnMic) btnMic.addEventListener('click', toggle);

        // Stop mic when Send is clicked so the final text is preserved cleanly
        if (btnSend) {
            btnSend.addEventListener('click', () => { if (isListening) stop(); }, { capture: true });
        }
        if (chatInput) {
            chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey && isListening) stop();
            }, { capture: true });
        }

        return { start, stop, toggle, reset };
    })();


    // =============================================================
    // MODULE 10 — Part D: CameraManager (getUserMedia self-view)
    // =============================================================
    const CameraManager = (() => {
        const videoEl        = document.getElementById('camera-preview');
        const offPlaceholder = document.getElementById('camera-off-placeholder');
        const btnCam         = document.getElementById('btn-cam-toggle');
        let stream           = null;
        let isOn             = false;

        async function init() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                if (offPlaceholder) offPlaceholder.style.display = 'flex';
                if (videoEl) videoEl.style.display = 'none';
                updateLabel();
                return;
            }
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                if (videoEl) { videoEl.srcObject = stream; videoEl.style.display = 'block'; }
                if (offPlaceholder) offPlaceholder.style.display = 'none';
                isOn = true;
                updateLabel();
            } catch (err) {
                console.info('[Camera] Unavailable or denied:', err.name);
                if (offPlaceholder) offPlaceholder.style.display = 'flex';
                if (videoEl) videoEl.style.display = 'none';
                isOn = false;
                updateLabel();
            }
        }

        function turnOff() {
            if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
            if (videoEl) { videoEl.srcObject = null; videoEl.style.display = 'none'; }
            if (offPlaceholder) offPlaceholder.style.display = 'flex';
            isOn = false; updateLabel();
        }

        async function turnOn() {
            if (isOn) return;
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                if (videoEl) { videoEl.srcObject = stream; videoEl.style.display = 'block'; }
                if (offPlaceholder) offPlaceholder.style.display = 'none';
                isOn = true; updateLabel();
            } catch (err) { console.warn('[Camera] Restart failed:', err.name); }
        }

        function toggle() { isOn ? turnOff() : turnOn(); }

        function teardown() { if (stream) stream.getTracks().forEach(t => t.stop()); }

        function updateLabel() {
            if (!btnCam) return;
            const iconEl = btnCam.querySelector('.tile-btn-icon');
            const textEl = btnCam.querySelector('.tile-btn-text');
            if (iconEl) { iconEl.textContent = '📹'; }
            if (textEl) { textEl.textContent = isOn ? 'Camera On' : 'Camera Off'; }
            if (!iconEl && !textEl) btnCam.textContent = isOn ? '📷 On' : '📷 Off';
            btnCam.title = isOn ? 'Turn camera off' : 'Turn camera on';
        }

        if (btnCam) btnCam.addEventListener('click', toggle);
        window.addEventListener('pagehide', teardown);
        init();

        return { init, toggle, teardown };
    })();


    // =============================================================
    // MODULE 10 POLISH — #3: InterviewTimer
    // Counts up from 00:00 since page load.
    // =============================================================
    const InterviewTimer = (() => {
        const timerEl  = document.getElementById('interview-timer');
        const startMs  = Date.now();
        let interval   = null;

        function pad(n) { return String(n).padStart(2, '0'); }

        function tick() {
            const elapsed = Math.floor((Date.now() - startMs) / 1000);
            const mm      = Math.floor(elapsed / 60);
            const ss      = elapsed % 60;
            if (timerEl) timerEl.textContent = `${pad(mm)}:${pad(ss)}`;
        }

        function start() {
            tick();
            interval = setInterval(tick, 1000);
        }

        function stop() { if (interval) { clearInterval(interval); interval = null; } }

        window.addEventListener('pagehide', stop);
        start();

        return { stop };
    })();


    // =============================================================
    // Google Meet Side Panel Manager (Chat & Tips Panels)
    // =============================================================
    const MeetPanelManager = (() => {
        const chatPanel    = document.getElementById('meet-chat-panel');
        const tipsPanel    = document.getElementById('meet-tips-panel');
        const btnToggleChat= document.getElementById('btn-toggle-chat');
        const btnCloseChat = document.getElementById('btn-close-chat');
        const btnToggleTips= document.getElementById('btn-toggle-tips');
        const btnCloseTips = document.getElementById('btn-close-tips');
        const unreadBadge  = document.getElementById('chat-unread-badge');

        let isChatOpen = true; // Default open on desktop
        let isTipsOpen = false;
        let unreadCount= 0;

        function setChatOpen(open) {
            isChatOpen = open;
            if (chatPanel) {
                chatPanel.style.display = open ? 'flex' : 'none';
            }
            if (btnToggleChat) {
                btnToggleChat.classList.toggle('active', open);
            }
            if (open) {
                if (isTipsOpen) setTipsOpen(false);
                unreadCount = 0;
                if (unreadBadge) {
                    unreadBadge.style.display = 'none';
                    unreadBadge.textContent = '0';
                }
                scrollToBottom(false);
            }
        }

        function setTipsOpen(open) {
            isTipsOpen = open;
            if (tipsPanel) {
                tipsPanel.style.display = open ? 'flex' : 'none';
            }
            if (btnToggleTips) {
                btnToggleTips.classList.toggle('active', open);
            }
            if (open && isChatOpen) {
                setChatOpen(false);
            }
        }

        function notifyNewMessage() {
            if (!isChatOpen) {
                unreadCount++;
                if (unreadBadge) {
                    unreadBadge.textContent = String(unreadCount);
                    unreadBadge.style.display = 'flex';
                }
            }
        }

        if (btnToggleChat) {
            btnToggleChat.addEventListener('click', () => setChatOpen(!isChatOpen));
        }
        if (btnCloseChat) {
            btnCloseChat.addEventListener('click', () => setChatOpen(false));
        }

        if (btnToggleTips) {
            btnToggleTips.addEventListener('click', () => setTipsOpen(!isTipsOpen));
        }
        if (btnCloseTips) {
            btnCloseTips.addEventListener('click', () => setTipsOpen(false));
        }

        return { setChatOpen, setTipsOpen, notifyNewMessage };
    })();


    // =============================================================
    // MODULE 10 POLISH — #4: CountdownManager
    // Shows 3-2-1 overlay before the first greeting fires.
    // =============================================================
    const CountdownManager = (() => {
        const overlay = document.getElementById('countdown-overlay');
        let digitEl   = document.getElementById('countdown-digit');

        function show(onComplete) {
            // Safety: if overlay/digit missing, skip straight to interview
            if (!overlay || !digitEl) {
                try { onComplete(); } catch (e) { console.error('[CountdownManager] onComplete failed:', e); }
                return;
            }

            overlay.classList.remove('hidden');
            overlay.style.display = 'flex';
            let count = 3;

            function tick() {
                try {
                    if (count < 1) {
                        // Countdown complete — hide overlay and fire interview
                        overlay.classList.add('hidden');
                        overlay.style.display = 'none';
                        try { onComplete(); } catch (e) { console.error('[CountdownManager] onComplete failed:', e); }
                        return;
                    }

                    // Update digit text
                    digitEl.textContent = String(count);

                    // Re-trigger CSS animation without DOM replacement:
                    // Removing + re-adding the animation via reflow avoids losing the reference.
                    digitEl.style.animation = 'none';
                    void digitEl.offsetWidth; // force reflow
                    digitEl.style.animation  = '';

                    count--;
                    setTimeout(tick, 1000);
                } catch (err) {
                    // If anything goes wrong, don't leave the student frozen — complete immediately
                    console.error('[CountdownManager] tick error, skipping countdown:', err);
                    overlay.classList.add('hidden');
                    overlay.style.display = 'none';
                    try { onComplete(); } catch (e) { console.error('[CountdownManager] onComplete failed:', e); }
                }
            }

            tick();
        }

        return { show };
    })();


    // =============================================================
    // MODULE 10 POLISH — #5: FullscreenManager
    // =============================================================
    const FullscreenManager = (() => {
        const btn  = document.getElementById('btn-fullscreen');
        const root = document.documentElement;

        if (!document.fullscreenEnabled && !document.webkitFullscreenEnabled) {
            if (btn) btn.classList.add('hidden');
            return {};
        }

        function enter() {
            if (root.requestFullscreen) root.requestFullscreen();
            else if (root.webkitRequestFullscreen) root.webkitRequestFullscreen();
        }

        function exit() {
            if (document.exitFullscreen) document.exitFullscreen();
            else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
        }

        function toggle() {
            const isFull = document.fullscreenElement || document.webkitFullscreenElement;
            isFull ? exit() : enter();
        }

        function onFullscreenChange() {
            const isFull = document.fullscreenElement || document.webkitFullscreenElement;
            if (btn) {
                btn.textContent = isFull ? '✕' : '⛶';
                btn.title       = isFull ? 'Exit fullscreen' : 'Fullscreen mode';
                btn.setAttribute('aria-label', isFull ? 'Exit fullscreen' : 'Enter fullscreen');
            }
        }

        if (btn) btn.addEventListener('click', toggle);
        document.addEventListener('fullscreenchange', onFullscreenChange);
        document.addEventListener('webkitfullscreenchange', onFullscreenChange);

        return { enter, exit, toggle };
    })();


    // =============================================================
    // MODULE 10 POLISH — #7: ThinkingFillerManager
    // Shows a rotating text cue near avatar during API wait.
    // =============================================================
    const ThinkingFillerManager = (() => {
        const fillerDiv  = document.getElementById('thinking-filler');
        const fillerText = document.getElementById('filler-text');
        const fillerIcon = document.getElementById('filler-avatar-emoji');

        const CUES = [
            'Hmm, let me consider that…',
            'Thinking…',
            'Processing your response…',
            'One moment…',
            'Evaluating your answer…',
            'Formulating the next question…',
        ];

        const ICONS = ['🤔', '💭', '🧠', '⏳'];

        function show() {
            if (!fillerDiv || !fillerText) return;
            const cue  = CUES[Math.floor(Math.random() * CUES.length)];
            const icon = ICONS[Math.floor(Math.random() * ICONS.length)];
            if (fillerText) fillerText.textContent = cue;
            if (fillerIcon) fillerIcon.textContent = icon;
            fillerDiv.classList.add('visible');
        }

        function hide() {
            if (fillerDiv) fillerDiv.classList.remove('visible');
        }

        return { show, hide };
    })();


    // =============================================================
    // MODULE 10 POLISH — #8: StageProgressManager
    // Updates stage dot indicator from API response data.stage.
    // =============================================================
    const StageProgressManager = (() => {
        const dots         = document.querySelectorAll('#stage-dots .stage-dot');
        const stageNameEl  = document.getElementById('stage-name-text');

        // Short friendly names for each stage number
        const STAGE_SHORT = {
            1: 'Greeting & Readiness',
            2: 'Introduction',
            3: 'Technical Questions',
            4: 'Deep Dive',
        };

        function update(stageNum, stageName) {
            const num = parseInt(stageNum, 10);
            if (isNaN(num)) return;

            dots.forEach((dot, idx) => {
                const dotStage = idx + 1;
                dot.classList.remove('active', 'completed');
                if (dotStage < num)  dot.classList.add('completed');
                if (dotStage === num) dot.classList.add('active');
            });

            if (stageNameEl) {
                stageNameEl.textContent = STAGE_SHORT[num] || stageName || `Stage ${num}`;
            }
        }

        return { update };
    })();


    // =============================================================
    // MODULE 10 POLISH — #10: TipsRotator
    // Cycles through 8 interview tips in the sidebar every 7s.
    // =============================================================
    const TipsRotator = (() => {
        const tipTextEl  = document.getElementById('rotating-tip-text');
        const dotRow     = document.getElementById('tip-dot-row');

        const TIPS = [
            'Maintain a steady pace — rushing signals nervousness, while clarity signals confidence.',
            'Structure your answers: state your point first, then explain the reasoning behind it.',
            'Use the STAR method for behavioural questions: Situation, Task, Action, Result.',
            'It\'s okay to pause briefly before answering — thinking signals depth, not weakness.',
            'Reference specific past projects or metrics when discussing your technical experience.',
            'Ask for clarification if a question is ambiguous — it shows professional communication.',
            'Avoid filler words ("um", "like", "you know") — a brief pause is always cleaner.',
            'End strong: summarise your answer with a clear, confident one-sentence conclusion.',
        ];

        let currentIndex = 0;

        // Build indicator dots
        function buildDots() {
            if (!dotRow) return;
            dotRow.innerHTML = '';
            TIPS.forEach((_, i) => {
                const d = document.createElement('div');
                d.className = `tip-dot${i === 0 ? ' active' : ''}`;
                dotRow.appendChild(d);
            });
        }

        function updateDots(idx) {
            if (!dotRow) return;
            dotRow.querySelectorAll('.tip-dot').forEach((d, i) => {
                d.classList.toggle('active', i === idx);
            });
        }

        function next() {
            if (!tipTextEl) return;
            tipTextEl.classList.add('fading');
            setTimeout(() => {
                currentIndex = (currentIndex + 1) % TIPS.length;
                tipTextEl.textContent = TIPS[currentIndex];
                tipTextEl.classList.remove('fading');
                updateDots(currentIndex);
            }, 400); // matches CSS transition duration
        }

        function init() {
            buildDots();
            if (tipTextEl) tipTextEl.textContent = TIPS[0];
            setInterval(next, 7000);
        }

        init();

        return { next };
    })();


    // =============================================================
    // SessionStatsManager — Honest real-time session statistics
    // Derives all values from actual chat DOM / timestamps only.
    // =============================================================
    const SessionStatsManager = (() => {
        const elAnswersCount  = document.getElementById('stat-answers-count');
        const elAvgWords      = document.getElementById('stat-avg-words');
        const elActiveStage   = document.getElementById('stat-active-stage-tag');
        const elPaceTime      = document.getElementById('stat-pace-time');
        const elQuestionsAsked= document.getElementById('stat-questions-asked');

        let studentMessageCount = 0;
        let totalStudentWords   = 0;
        let aiMessageCount      = 0;
        let sessionStartMs      = Date.now();
        let lastTurnTimestamp   = Date.now();
        let totalPaceSecs       = 0;
        let paceRecordCount     = 0;
        let currentStage        = 1;

        // Called each time a student message bubble is appended
        function recordStudentMessage(text) {
            if (!text) return;

            // Pace timing: seconds from last AI question to this student answer
            const nowMs      = Date.now();
            const paceSecs   = Math.round((nowMs - lastTurnTimestamp) / 1000);
            if (paceSecs > 1 && paceSecs < 600) { // sanity-check: 1s–10min
                totalPaceSecs   += paceSecs;
                paceRecordCount += 1;
            }

            const wordCount    = text.trim().split(/\s+/).filter(Boolean).length;
            studentMessageCount++;
            totalStudentWords += wordCount;

            refresh();
        }

        // Called each time an AI message bubble is appended
        function recordAiMessage() {
            aiMessageCount++;
            lastTurnTimestamp = Date.now(); // reset pace timer after AI speaks
            refresh();
        }

        function setStage(num) {
            currentStage = parseInt(num, 10) || currentStage;
            refresh();
        }

        // Seed from existing messages already in DOM on page load
        function seedFromDom() {
            if (!chatContainer) return;
            const studentMsgs = chatContainer.querySelectorAll('.message-student .bubble-text');
            const aiMsgs      = chatContainer.querySelectorAll('.message-ai .bubble-text');
            aiMessageCount    = aiMsgs.length;
            studentMsgs.forEach((el) => {
                const words = (el.textContent || '').trim().split(/\s+/).filter(Boolean).length;
                studentMessageCount++;
                totalStudentWords += words;
            });
            refresh();
        }

        function refresh() {
            const avgWords  = studentMessageCount > 0
                ? Math.round(totalStudentWords / studentMessageCount)
                : 0;
            const avgPace   = paceRecordCount > 0
                ? Math.round(totalPaceSecs / paceRecordCount)
                : null;

            const stageLabels = {
                1: 'Stage 1 — Intro',
                2: 'Stage 2 — Technical',
                3: 'Stage 3 — Role-Specific',
                4: 'Stage 4 — Behavioral',
            };

            if (elAnswersCount)   elAnswersCount.textContent   = String(studentMessageCount);
            if (elAvgWords)       elAvgWords.textContent       = String(avgWords);
            if (elActiveStage)    elActiveStage.textContent    = stageLabels[currentStage] || `Stage ${currentStage}`;
            if (elPaceTime)       elPaceTime.textContent       = avgPace !== null ? String(avgPace) : '--';

            // Also update Interviewer Details "Questions Asked"
            if (elQuestionsAsked) elQuestionsAsked.textContent = String(aiMessageCount);
        }

        seedFromDom();

        return { recordStudentMessage, recordAiMessage, setStage, refresh };
    })();


    // =============================================================
    // TranscriptManager — Read-only formatted conversation log
    // Builds the Transcript tab from existing chat DOM nodes.
    // =============================================================
    const TranscriptManager = (() => {
        const transcriptList = document.getElementById('transcript-entries-list');

        function update() {
            if (!transcriptList || !chatContainer) return;
            transcriptList.innerHTML = '';

            const turns = chatContainer.querySelectorAll('.message-turn:not(.typing-wrapper)');
            turns.forEach((turn) => {
                const isStudent = turn.classList.contains('message-student');
                const textEl    = turn.querySelector('.bubble-text');
                const timeEl    = turn.querySelector('.message-timestamp');
                if (!textEl) return;

                const entry = document.createElement('div');
                entry.className = `transcript-entry${isStudent ? ' entry-student' : ''}`;

                const speakerEl  = document.createElement('span');
                speakerEl.className = 'entry-speaker';
                speakerEl.textContent = isStudent ? `${studentName} (You)` : `${interviewerName}`;

                const bodyEl     = document.createElement('p');
                bodyEl.className = 'entry-text';
                bodyEl.textContent = textEl.textContent || '';

                entry.appendChild(speakerEl);
                entry.appendChild(bodyEl);
                if (timeEl && timeEl.textContent.trim()) {
                    const tsEl = document.createElement('span');
                    tsEl.className = 'entry-timestamp';
                    tsEl.textContent = timeEl.textContent.trim();
                    entry.appendChild(tsEl);
                }
                transcriptList.appendChild(entry);
            });
        }

        // Expose globally (called by switchPanelTab in HTML)
        window.updateTranscriptDocument = update;

        return { update };
    })();


    // =============================================================
    // ChecklistProgressManager — Vertical 5-stage progress checklist
    // Reads stage from StageProgressManager updates.
    // =============================================================
    const ChecklistProgressManager = (() => {
        const fillBar    = document.getElementById('checklist-progress-fill');
        const labelEl    = document.getElementById('checklist-progress-label');
        const percentEl  = document.getElementById('checklist-progress-percent');

        // Map API stages (1–4) to display stages (1–5, stage 5 = Final Feedback)
        // Stage 4 = Behavioral → Stage 5 = Final Feedback triggers on session end
        function update(stageNum) {
            const num = parseInt(stageNum, 10);
            if (isNaN(num) || num < 1) return;

            // Mark stage items completed / active
            for (let i = 1; i <= 5; i++) {
                const item = document.getElementById(`stage-check-${i}`);
                if (!item) continue;
                item.classList.remove('active', 'completed');
                const icon = item.querySelector('.stage-status-icon');

                if (i < num) {
                    item.classList.add('completed');
                    if (icon) icon.textContent = '✓';
                } else if (i === num) {
                    item.classList.add('active');
                    if (icon) icon.textContent = String(i);
                } else {
                    if (icon && i < 5) icon.textContent = String(i);
                }
            }

            // Progress bar: map stage 1-4 → 25%/50%/75%/100% for the bar
            const pct = Math.min(100, Math.round((num / 4) * 100));
            if (fillBar)   fillBar.style.width     = `${pct}%`;
            if (labelEl)   labelEl.textContent      = `Stage ${Math.min(num, 4)} of 4`;
            if (percentEl) percentEl.textContent    = `${pct}%`;

            // Update stats panel too
            SessionStatsManager.setStage(num);
        }

        // Patch StageProgressManager.update to also drive the checklist
        const _origUpdate = StageProgressManager.update.bind(StageProgressManager);
        StageProgressManager.update = function(stageNum, stageName) {
            _origUpdate(stageNum, stageName);
            update(stageNum);
        };

        // Initialize at Stage 1
        update(1);

        return { update };
    })();


    // =============================================================
    // Global helper: Copy full transcript to clipboard
    // Called by btn-copy-transcript in HTML
    // =============================================================
    window.copyFullTranscript = function copyFullTranscript() {
        if (!chatContainer) return;
        const turns   = chatContainer.querySelectorAll('.message-turn:not(.typing-wrapper)');
        const lines   = [];
        turns.forEach((turn) => {
            const isStudent = turn.classList.contains('message-student');
            const textEl    = turn.querySelector('.bubble-text');
            if (!textEl) return;
            const speaker   = isStudent ? `${studentName} (You)` : interviewerName;
            lines.push(`${speaker}: ${textEl.textContent.trim()}`);
        });
        const fullText = lines.join('\n\n');
        if (!fullText) return;

        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(fullText).then(() => {
                const btn = document.getElementById('btn-copy-transcript');
                if (btn) {
                    btn.textContent = '✅ Copied!';
                    setTimeout(() => { btn.textContent = '📋 Copy Text'; }, 2000);
                }
            }).catch(() => {});
        }
    };


    // =============================================================
    // MicrophoneManager — Updates tile button state for mic btn
    // =============================================================
    const MicrophoneButtonManager = (() => {
        const btnMic = document.getElementById('btn-mic');
        if (!btnMic) return {};

        function setListening(active) {
            const iconEl  = btnMic.querySelector('.tile-btn-icon');
            const textEl  = btnMic.querySelector('.tile-btn-text');
            if (active) {
                btnMic.classList.add('is-listening');
                if (iconEl) iconEl.textContent = '🎤';
                if (textEl) textEl.textContent = 'Listening…';
            } else {
                btnMic.classList.remove('is-listening');
                if (iconEl) iconEl.textContent = '🎤';
                if (textEl) textEl.textContent = 'Mic On';
            }
        }

        return { setListening };
    })();


    // =============================================================
    // Initial Page Load Sequence
    // =============================================================
    scrollToBottom(false);

    // Guarantee that analysis overlay is strictly hidden on initial load
    const analysisOverlay = document.getElementById('analysis-loading-overlay');
    if (analysisOverlay) {
        analysisOverlay.classList.add('hidden');
        analysisOverlay.classList.remove('visible');
        analysisOverlay.style.display = 'none';
    }

    if (!isCompleted) {
        const existingTurns = chatContainer
            ? chatContainer.querySelectorAll('.message-turn:not(.typing-wrapper)')
            : [];

        if (existingTurns.length === 0) {
            // #4: Show 3-2-1 countdown THEN fire the greeting
            CountdownManager.show(() => sendTurn(null));
        }
    }

});
