/**
 * static/js/practice_room.js
 * Practice Room Controller for InterviewCoach AI — Single-Topic Practice Mode.
 *
 * Handles:
 * - Speech-to-Text via VoiceInputManager with robust reset() logic.
 * - Text-to-Speech via TTSManager.
 * - Immediate and reliable textarea clearing after message submission.
 * - Restoring text if submission fails.
 * - Auto-scrolling, dynamic question counters, and end-practice flow.
 */

(function () {
    'use strict';

    const container = document.querySelector('.practice-room-container');
    if (!container) return;

    const SESSION_ID = container.dataset.sessionId ? parseInt(container.dataset.sessionId, 10) : null;
    const CHAT_URL   = container.dataset.chatUrl || (SESSION_ID ? `/student/practice/${SESSION_ID}/chat` : '');
    const USER_NAME  = container.dataset.studentName || 'Candidate';

    const messagesArea    = document.getElementById('chat-messages-area');
    const textarea        = document.getElementById('student-answer-input');
    const btnSend         = document.getElementById('btn-send-answer');
    const btnMic          = document.getElementById('btn-mic-toggle');
    const btnSpeaker      = document.getElementById('btn-speaker-toggle');
    const speakerIcon     = document.getElementById('speaker-icon');
    const micLiveBanner   = document.getElementById('mic-live-banner');
    const charDisplay     = document.getElementById('dock-char-count');
    const typingRow       = document.getElementById('typing-indicator');
    const currentQNumEl   = document.getElementById('current-q-num');

    let studentTurnsCount = 0;
    let isSubmitting      = false;

    // Count existing student messages on page load
    if (messagesArea) {
        studentTurnsCount = messagesArea.querySelectorAll('.row-student').length;
    }

    function updateCounter() {
        if (currentQNumEl) {
            currentQNumEl.textContent = Math.min(studentTurnsCount + 1, 6);
        }
    }
    updateCounter();

    // ── Auto-scroll Helper ───────────────────────────────────────────
    function scrollToBottom(smooth = true) {
        if (!messagesArea) return;
        requestAnimationFrame(() => {
            messagesArea.scrollTo({
                top: messagesArea.scrollHeight,
                behavior: smooth ? 'smooth' : 'auto'
            });
        });
    }
    scrollToBottom(false);

    // ── Clear Textarea & Reset Dimensions ────────────────────────────
    function clearTextarea() {
        if (!textarea) return;
        textarea.value = '';
        textarea.style.height = 'auto';
        if (charDisplay) {
            charDisplay.textContent = '0 / 3000';
        }
    }

    // ── Auto-resize Textarea & Char Counter ──────────────────────────
    function handleTextareaInput() {
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(textarea.scrollHeight, 140)}px`;
        if (charDisplay) {
            charDisplay.textContent = `${textarea.value.length} / 3000`;
        }
    }

    if (textarea) {
        textarea.addEventListener('input', handleTextareaInput);
        textarea.addEventListener('keydown', (e) => {
            // Send on Enter (without Shift) or on Ctrl+Enter
            if ((e.key === 'Enter' && !e.shiftKey) || (e.ctrlKey && e.key === 'Enter')) {
                e.preventDefault();
                sendPracticeAnswer();
            }
        });
    }

    if (btnSend) {
        btnSend.addEventListener('click', (e) => {
            e.preventDefault();
            sendPracticeAnswer();
        });
    }

    // ================================================================
    // MODULE: Text-to-Speech (TTSManager)
    // Indian English (en-IN) prioritization & mobile male pitch fix
    // ================================================================
    let activeUtterance = null; // Stored in module scope to prevent GC truncation in Chrome/Edge

    const TTSManager = (() => {
        const synth = window.speechSynthesis || null;
        let isMuted = false;
        let voices  = [];
        let selectedVoice = null;
        let selectedVoiceConfig = { pitch: 1.0, rate: 0.95, isIndian: false, isFallback: false, reason: '' };
        const coachGender = 'female'; // Default coach gender for practice drill

        function isIndianLang(v) {
            if (!v || !v.lang) return false;
            const l = v.lang.toLowerCase().replace('_', '-');
            return l === 'en-in' || l.startsWith('en-in') || l === 'hi-in' || /india|indian|hindi/i.test(v.name);
        }

        function isFemaleVoice(v) {
            if (!v) return false;
            const name = (v.name || '').toLowerCase();
            return /female|woman|girl|lady|heera|swara|zira|samantha|victoria|karen|hazel|susan|priya|ananya|neerja|kavya|jenny|aria|sonia|libby/i.test(name);
        }

        function isMaleVoice(v) {
            if (!v) return false;
            const name = (v.name || '').toLowerCase();
            if (isFemaleVoice(v)) return false;
            return /male|man\b|boy|ravi|prabhat|george|david|daniel|guy|oliver|ryan|arthur|james|richard|mark|google uk english male|google us english/i.test(name);
        }

        function resolveVoice(gender, voiceList) {
            if (!voiceList || !voiceList.length) {
                return {
                    voice: null,
                    pitch: gender === 'male' ? 0.82 : 1.05,
                    rate: 0.95,
                    isIndian: false,
                    isFallback: true,
                    reason: 'No voices available in browser'
                };
            }

            const enInVoices = voiceList.filter(v => isIndianLang(v));
            const enGbVoices = voiceList.filter(v => v.lang && v.lang.toLowerCase().startsWith('en-gb'));
            const enUsVoices = voiceList.filter(v => v.lang && v.lang.toLowerCase().startsWith('en-us'));
            const anyEnVoices = voiceList.filter(v => v.lang && v.lang.toLowerCase().startsWith('en'));

            if (gender === 'male') {
                const inMale = enInVoices.find(v => isMaleVoice(v));
                if (inMale) {
                    return { voice: inMale, pitch: 0.95, rate: 0.95, isIndian: true, isFallback: false, reason: 'en-IN male voice' };
                }
                if (enInVoices.length > 0) {
                    return { voice: enInVoices[0], pitch: 0.82, rate: 0.95, isIndian: true, isFallback: true, reason: 'en-IN voice with pitch downshift for male' };
                }
                const gbMale = enGbVoices.find(v => isMaleVoice(v));
                if (gbMale) {
                    return { voice: gbMale, pitch: 0.95, rate: 0.95, isIndian: false, isFallback: true, reason: 'en-GB male voice' };
                }
                const usMale = enUsVoices.find(v => isMaleVoice(v));
                if (usMale) {
                    return { voice: usMale, pitch: 0.95, rate: 0.95, isIndian: false, isFallback: true, reason: 'en-US male voice' };
                }
                const anyEnMale = anyEnVoices.find(v => isMaleVoice(v));
                if (anyEnMale) {
                    return { voice: anyEnMale, pitch: 0.95, rate: 0.95, isIndian: false, isFallback: true, reason: 'English male voice' };
                }
                if (anyEnVoices.length > 0) {
                    return { voice: anyEnVoices[0], pitch: 0.82, rate: 0.95, isIndian: false, isFallback: true, reason: 'English voice simulated male (pitch 0.82)' };
                }
                return { voice: voiceList[0], pitch: 0.82, rate: 0.95, isIndian: false, isFallback: true, reason: 'Default voice simulated male (pitch 0.82)' };
            } else {
                const inFemale = enInVoices.find(v => isFemaleVoice(v)) || enInVoices[0];
                if (inFemale) {
                    return { voice: inFemale, pitch: 1.05, rate: 0.95, isIndian: true, isFallback: false, reason: 'en-IN female voice' };
                }
                const gbFemale = enGbVoices.find(v => isFemaleVoice(v)) || enGbVoices[0];
                if (gbFemale) {
                    return { voice: gbFemale, pitch: 1.05, rate: 0.95, isIndian: false, isFallback: true, reason: 'en-GB female voice' };
                }
                const usFemale = enUsVoices.find(v => isFemaleVoice(v)) || enUsVoices[0];
                if (usFemale) {
                    return { voice: usFemale, pitch: 1.05, rate: 0.95, isIndian: false, isFallback: true, reason: 'en-US female voice' };
                }
                if (anyEnVoices.length > 0) {
                    const anyEnFemale = anyEnVoices.find(v => isFemaleVoice(v)) || anyEnVoices[0];
                    return { voice: anyEnFemale, pitch: 1.05, rate: 0.95, isIndian: false, isFallback: true, reason: 'English female voice' };
                }
                return { voice: voiceList[0], pitch: 1.05, rate: 0.95, isIndian: false, isFallback: true, reason: 'Default voice female' };
            }
        }

        function getOrSelectVoice() {
            if (selectedVoice) {
                console.log(`[Voice] Using cached voice: ${selectedVoice.name}`);
                return {
                    voice: selectedVoice,
                    pitch: selectedVoiceConfig.pitch,
                    rate: selectedVoiceConfig.rate
                };
            }

            if (!voices.length && synth) {
                voices = synth.getVoices() || [];
            }

            console.log(`[Voice] Initial selection — voices available: ${voices.length}`);
            const result = resolveVoice(coachGender, voices);
            selectedVoice = result.voice;
            selectedVoiceConfig = result;

            if (result.isFallback) {
                console.log(`[Voice] Fallback used: ${result.reason} — pitch adjusted to ${result.pitch}`);
            }
            console.log(`[Voice Debug] Session gender: ${coachGender}, selected voice: ${selectedVoice ? selectedVoice.name : 'Default'}, lang: ${selectedVoice ? selectedVoice.lang : 'en'}, pitch: ${result.pitch}`);

            return {
                voice: selectedVoice,
                pitch: selectedVoiceConfig.pitch,
                rate: selectedVoiceConfig.rate
            };
        }

        function loadVoices() {
            voices = synth ? synth.getVoices() : [];
            if (!selectedVoice && voices.length) {
                getOrSelectVoice();
            }
        }

        if (synth) {
            loadVoices();
            synth.addEventListener('voiceschanged', loadVoices);
            synth.onvoiceschanged = loadVoices;
            setTimeout(loadVoices, 500);
        }

        function speak(text, onEndCallback, onErrorCallback) {
            if (!synth || !text || isMuted) {
                if (typeof onEndCallback === 'function') onEndCallback();
                return;
            }
            try {
                synth.cancel(); // stop any ongoing speech
                if (synth.paused) synth.resume();

                const utterance = new SpeechSynthesisUtterance(text);
                activeUtterance = utterance; // Retain reference to prevent GC clipping

                const voiceSetup = getOrSelectVoice();
                utterance.rate   = voiceSetup.rate || 0.95;
                utterance.pitch  = voiceSetup.pitch || 1.0;
                utterance.volume = 1.0;
                if (voiceSetup.voice) utterance.voice = voiceSetup.voice;

                utterance.onstart = () => {
                    console.log('[PracticeRoom] TTS started.');
                };

                let called = false;
                function finish(isError = false, err = null) {
                    if (!called) {
                        called = true;
                        activeUtterance = null;
                        if (isError) {
                            console.warn('[PracticeRoom] TTS error encountered:', err);
                            if (typeof onErrorCallback === 'function') {
                                onErrorCallback(err);
                            } else if (typeof onEndCallback === 'function') {
                                onEndCallback();
                            }
                        } else {
                            console.log('[PracticeRoom] TTS ended. Scheduling redirect.');
                            if (typeof onEndCallback === 'function') {
                                onEndCallback();
                            }
                        }
                    }
                }

                utterance.onend = () => finish(false);
                utterance.onerror = (err) => finish(true, err);

                synth.speak(utterance);
            } catch (e) {
                console.warn('[PracticeRoom] Speech synthesis exception:', e);
                activeUtterance = null;
                if (typeof onErrorCallback === 'function') {
                    onErrorCallback(e);
                } else if (typeof onEndCallback === 'function') {
                    onEndCallback();
                }
            }
        }

        function toggle() {
            isMuted = !isMuted;
            selectedVoice = null; // Re-evaluate voice on toggle
            if (isMuted) {
                cancel();
                if (btnSpeaker) {
                    btnSpeaker.classList.add('is-muted');
                    btnSpeaker.title = 'AI Voice: OFF (Click to unmute)';
                }
                if (speakerIcon) speakerIcon.textContent = '🔇';
            } else {
                if (btnSpeaker) {
                    btnSpeaker.classList.remove('is-muted');
                    btnSpeaker.title = 'AI Voice: ON (Click to mute)';
                }
                if (speakerIcon) speakerIcon.textContent = '🔊';
            }
        }

        function cancel() {
            if (synth) {
                try { synth.cancel(); } catch (e) { /* ignore */ }
            }
            activeUtterance = null;
        }

        function isAvailableAndActive() {
            return !!synth && !isMuted;
        }

        window.addEventListener('pagehide', cancel);
        return { speak, toggle, cancel, isAvailableAndActive };
    })();

    if (btnSpeaker) {
        btnSpeaker.addEventListener('click', TTSManager.toggle);
    }

    // ================================================================
    // MODULE: Speech-to-Text (VoiceInputManager)
    // Reuses standard SpeechRecognition API with visual feedback and
    // robust state reset to prevent previous transcription carryover.
    // ================================================================
    const VoiceInputManager = (() => {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition || null;

        if (!SpeechRec) {
            if (btnMic) {
                btnMic.disabled = true;
                btnMic.title = 'Voice input is not supported in this browser (Use Chrome or Edge).';
            }
            return { toggle: () => {}, stop: () => {}, start: () => {}, reset: () => {} };
        }

        let recognition            = null;
        let isListening            = false;
        let sessionPrefix          = '';
        let sessionFinalTranscript = '';
        let restartBlocked         = false;

        function buildRecognition() {
            const rec = new SpeechRec();
            rec.continuous      = true;
            rec.interimResults  = true;
            rec.lang            = 'en-US';
            rec.maxAlternatives = 1;

            rec.onstart = () => {
                isListening = true;
                if (btnMic) btnMic.classList.add('is-listening');
                if (micLiveBanner) micLiveBanner.classList.remove('hidden');
                if (textarea) textarea.placeholder = 'Listening… speak your answer clearly';
            };

            rec.onresult = (event) => {
                if (!textarea) return;
                let interimChunk = '';
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const res = event.results[i];
                    if (res.isFinal) {
                        sessionFinalTranscript += res[0].transcript;
                    } else {
                        interimChunk += res[0].transcript;
                    }
                }
                textarea.value = sessionPrefix + sessionFinalTranscript + interimChunk;
                handleTextareaInput();
            };

            rec.onend = () => {
                if (isListening && !restartBlocked) {
                    sessionPrefix = sessionPrefix + sessionFinalTranscript;
                    sessionFinalTranscript = '';
                    try {
                        recognition = buildRecognition();
                        recognition.start();
                    } catch (err) {
                        _stopInternal();
                    }
                } else {
                    _stopInternal();
                }
            };

            rec.onerror = (event) => {
                if (event.error === 'no-speech') return; // ignore silence timeout
                console.warn('[VoiceInput] Error:', event.error);
                restartBlocked = true;
                _stopInternal();
            };

            return rec;
        }

        function _stopInternal() {
            isListening = false;
            if (btnMic) btnMic.classList.remove('is-listening');
            if (micLiveBanner) micLiveBanner.classList.add('hidden');
            if (textarea) {
                textarea.placeholder = 'Type your answer here, or click the mic to speak…';
            }
        }

        function start() {
            if (isListening || !textarea) return;
            const cur = textarea.value || '';
            sessionPrefix = cur.trim() ? cur.trimEnd() + ' ' : '';
            sessionFinalTranscript = '';
            restartBlocked = false;

            recognition = buildRecognition();
            try {
                recognition.start();
            } catch (err) {
                console.warn('[VoiceInput] start failed:', err);
                _stopInternal();
            }
        }

        function stop() {
            if (!isListening) return;
            restartBlocked = true;
            isListening = false;
            if (recognition) {
                try { recognition.stop(); } catch (_) {}
                recognition = null;
            }
            if (textarea) {
                textarea.value = (sessionPrefix + sessionFinalTranscript).trim();
                handleTextareaInput();
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

        function toggle() {
            if (isListening) stop();
            else start();
        }

        // Capture listeners on Send and Enter to immediately stop voice recognition
        if (btnSend) {
            btnSend.addEventListener('click', () => { if (isListening) stop(); }, { capture: true });
        }
        if (textarea) {
            textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey && isListening) stop();
            }, { capture: true });
        }

        return { toggle, stop, start, reset };
    })();

    if (btnMic) {
        btnMic.addEventListener('click', VoiceInputManager.toggle);
    }

    // ── Append Bubble Helper ─────────────────────────────────────────
    function appendBubble(sender, text) {
        const emptyState = document.getElementById('chat-empty-state');
        if (emptyState) emptyState.remove();

        const isAI = sender === 'ai';
        const now = new Date();
        const timeStr = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');

        const row = document.createElement('div');
        row.className = `practice-bubble-row ${isAI ? 'row-ai' : 'row-student'}`;
        
        const avatarHtml = isAI ? `<div class="bubble-avatar-ai" title="AI Practice Coach">🤖</div>` : '';
        const authorName = isAI ? 'AI Practice Coach' : USER_NAME;

        row.innerHTML = `
            ${avatarHtml}
            <div class="practice-bubble ${isAI ? 'bubble-ai' : 'bubble-student'}">
                <div class="bubble-meta">
                    <span class="bubble-author">${authorName}</span>
                    <span class="bubble-timestamp">${timeStr}</span>
                </div>
                <div class="bubble-text-content">${text.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
            </div>`;

        if (typingRow) {
            messagesArea.insertBefore(row, typingRow);
        } else {
            messagesArea.appendChild(row);
        }
        scrollToBottom();
    }

    function showTyping() {
        if (typingRow) typingRow.classList.remove('hidden');
        scrollToBottom();
    }

    function hideTyping() {
        if (typingRow) typingRow.classList.add('hidden');
    }

    function setControlsDisabled(state) {
        if (btnSend) btnSend.disabled = state;
        if (textarea) textarea.disabled = state;
        if (btnMic) btnMic.disabled = state;
    }

    let isDrillEnded = false;

    // ── Trigger End Practice & Auto-Redirect ─────────────────────────
    function triggerEndPractice(skipConfirm = false) {
        VoiceInputManager.reset();
        TTSManager.cancel();

        if (!skipConfirm && !confirm('End your practice drill and review your performance feedback?')) {
            return;
        }

        const overlay = document.getElementById('analysis-loading-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            overlay.classList.remove('hidden');
        }

        const form = document.getElementById('end-practice-form');
        if (form) form.submit();
    }

    window.endPracticeSession = function () {
        triggerEndPractice(false);
    };

    // ── Send Practice Answer ─────────────────────────────────────────
    window.sendPracticeAnswer = function (overrideAnswer) {
        if (isSubmitting) return;

        if (isDrillEnded) {
            triggerEndPractice(true);
            return;
        }

        // Immediately reset and stop any active voice input
        VoiceInputManager.reset();

        const answerText = (overrideAnswer !== undefined) 
            ? overrideAnswer 
            : (textarea ? textarea.value.trim() : '');

        if (answerText === '' && overrideAnswer === undefined) {
            if (textarea) textarea.focus();
            return;
        }

        // Optimistically render student bubble and immediately clear textarea
        if (answerText) {
            appendBubble('student', answerText);
            clearTextarea();
            studentTurnsCount++;
            updateCounter();
        }

        isSubmitting = true;
        setControlsDisabled(true);
        showTyping();

        fetch(CHAT_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
            body: JSON.stringify({ answer: answerText })
        })
        .then(r => {
            if (!r.ok) {
                return r.json().then(errData => {
                    throw new Error(errData.error || `Server error (${r.status})`);
                });
            }
            return r.json();
        })
        .then(data => {
            hideTyping();

            if (data.total_questions && currentQNumEl) {
                const totalEl = document.querySelector('.counter-total');
                if (totalEl) totalEl.textContent = data.total_questions;
                if (data.current_question_number) {
                    currentQNumEl.textContent = data.current_question_number;
                }
            }

            if (data.is_wrap_up) {
                // Drill has ended — lock controls and initiate auto-redirect
                isDrillEnded = true;
                setControlsDisabled(true);
                if (textarea) {
                    textarea.placeholder = "Practice drill complete! Generating your feedback report…";
                    textarea.disabled = true;
                }
                if (btnSend) btnSend.disabled = true;
                if (btnMic) btnMic.disabled = true;

                if (data.ai_message) {
                    appendBubble('ai', data.ai_message);
                }

                const wrapUpText = (data.ai_message || '').trim();
                const wordCount = wrapUpText ? wrapUpText.split(/\s+/).filter(Boolean).length : 0;
                const estimatedSecs = Math.max(3, Math.round(wordCount / 2.5));
                const isSpeakerActive = TTSManager.isAvailableAndActive();

                console.log(
                    `[PracticeRoom] Wrap-up detected. Message length: ${wrapUpText.length} chars, ~${wordCount} words, ` +
                    `estimated TTS duration: ~${estimatedSecs}s. Speaker active: ${isSpeakerActive}`
                );

                let redirectTriggered = false;
                let safetyTimer = null;
                let graceTimer = null;
                let countdownTimer = null;

                function clearAllTimers() {
                    if (safetyTimer) { clearTimeout(safetyTimer); safetyTimer = null; }
                    if (graceTimer) { clearTimeout(graceTimer); graceTimer = null; }
                    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
                }

                function doAutoRedirect() {
                    if (!redirectTriggered) {
                        redirectTriggered = true;
                        clearAllTimers();
                        triggerEndPractice(true);
                    }
                }

                // Construct initial banner UI
                let initialBannerHtml = '';
                if (isSpeakerActive && wrapUpText) {
                    initialBannerHtml = `
                        <span class="wrapup-icon">🔊</span>
                        <div class="wrapup-text-wrap">
                            <strong>Practice Drill Concluded!</strong>
                            <span id="wrapup-status-msg">AI is speaking... Report will open when finished.</span>
                        </div>
                    `;
                } else {
                    initialBannerHtml = `
                        <span class="wrapup-icon">🏁</span>
                        <div class="wrapup-text-wrap">
                            <strong>Practice Drill Concluded!</strong>
                            <span id="wrapup-status-msg">Opening your feedback scorecard in <span id="countdown-val" class="countdown-highlight">5</span>s…</span>
                        </div>
                    `;
                }

                const countdownRow = document.createElement('div');
                countdownRow.className = 'practice-wrapup-countdown-banner';
                countdownRow.id = 'practice-wrapup-banner';
                countdownRow.innerHTML = `
                    <div class="wrapup-banner-content">
                        ${initialBannerHtml}
                        <button type="button" id="btn-skip-report-now" class="btn btn-sm btn-primary wrapup-skip-btn">
                            Skip &amp; View Report Now &rarr;
                        </button>
                    </div>
                `;
                messagesArea.appendChild(countdownRow);
                scrollToBottom();

                const skipBtn = document.getElementById('btn-skip-report-now');
                if (skipBtn) {
                    skipBtn.addEventListener('click', (e) => {
                        e.preventDefault();
                        console.log('[PracticeRoom] Skip & View Report Now clicked. Cancelling TTS and redirecting immediately.');
                        TTSManager.cancel();
                        clearAllTimers();
                        doAutoRedirect();
                    });
                }

                if (isSpeakerActive && wrapUpText) {
                    // Safety Fallback (20 seconds) for rare cases where browser TTS stalls or drops onend
                    safetyTimer = setTimeout(() => {
                        console.warn('[PracticeRoom] Safety timeout (20s) fired. Forcing redirect.');
                        doAutoRedirect();
                    }, 20000);

                    // Speak wrap-up text; redirect on completion or error
                    TTSManager.speak(
                        wrapUpText,
                        // onEndCallback
                        () => {
                            const statusEl = document.getElementById('wrapup-status-msg');
                            if (statusEl) {
                                statusEl.innerHTML = '✅ Speech complete. Opening your report...';
                            }
                            graceTimer = setTimeout(() => {
                                doAutoRedirect();
                            }, 800);
                        },
                        // onErrorCallback
                        (err) => {
                            console.warn('[PracticeRoom] TTS error reported in wrap-up handler:', err);
                            const statusEl = document.getElementById('wrapup-status-msg');
                            if (statusEl) {
                                statusEl.innerHTML = '⚠️ Voice audio error. Opening your report in 3s...';
                            }
                            graceTimer = setTimeout(() => {
                                doAutoRedirect();
                            }, 3000);
                        }
                    );
                } else {
                    // Muted / No TTS fallback: 5-second countdown to allow student to read the closing message
                    if (wrapUpText) TTSManager.speak(wrapUpText);

                    let countdownSecs = 5;
                    const countdownValEl = document.getElementById('countdown-val');

                    countdownTimer = setInterval(() => {
                        countdownSecs--;
                        if (countdownValEl && countdownSecs >= 0) {
                            countdownValEl.textContent = countdownSecs;
                        }
                        if (countdownSecs <= 0) {
                            clearAllTimers();
                            doAutoRedirect();
                        }
                    }, 1000);

                    safetyTimer = setTimeout(doAutoRedirect, 5200);
                }
            } else {
                // Normal ongoing question turn
                setControlsDisabled(false);
                clearTextarea();

                if (data.ai_message) {
                    appendBubble('ai', data.ai_message);
                    TTSManager.speak(data.ai_message);
                } else if (data.error) {
                    appendBubble('ai', `⚠️ ${data.error}`);
                }

                if (textarea) textarea.focus();
            }
        })
        .catch(err => {
            hideTyping();
            setControlsDisabled(false);
            // Restore text so student doesn't lose their answer on error
            if (textarea && answerText) {
                textarea.value = answerText;
                handleTextareaInput();
            }
            appendBubble('ai', `⚠️ ${err.message || 'Network error communicating with Practice Coach. Please try again.'}`);
            console.error('[PracticeRoom]', err);
            if (textarea) textarea.focus();
        })
        .finally(() => {
            isSubmitting = false;
        });
    };
})();
