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
        const voiceCache = { male: null, female: null };
        const coachGender = 'female'; // Default coach gender for practice drill

        // Explicitly validates that the voice is English and rejects Hindi / non-English languages
        function isEnglishVoice(v) {
            if (!v || !v.lang) return false;
            const l = v.lang.toLowerCase().replace('_', '-');
            const name = (v.name || '').toLowerCase();

            // Explicitly reject Hindi (hi-IN) and other regional non-English language voices
            if (l.startsWith('hi') || l === 'hi' || /hindi|हिन्दी|marathi|tamil|telugu|kannada|bengali|gujarati/i.test(name)) {
                console.log(`[Voice] Rejected '${v.name}' — lang ${v.lang} is not English`);
                return false;
            }

            return l.startsWith('en');
        }

        // Strictly matches English India (en-IN) and rejects Hindi
        function isEnglishIndia(v) {
            if (!isEnglishVoice(v)) return false;
            const l = v.lang.toLowerCase().replace('_', '-');
            const name = (v.name || '').toLowerCase();
            return l === 'en-in' || l.startsWith('en-in') || 
                   ((/india|indian/i.test(name) || /ravi|heera|prabhat|swara|priya|ananya|neerja/i.test(name)) && l.startsWith('en'));
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
            return /male|man\b|boy|ravi|prabhat|george|david|daniel|guy|oliver|ryan|arthur|james|richard|mark|google uk english male|google us english male|google us english/i.test(name);
        }

        function resolveVoice(gender, voiceList) {
            if (!voiceList || !voiceList.length) {
                return {
                    voice: null,
                    pitch: gender === 'male' ? 0.5 : 1.0,
                    rate: gender === 'male' ? 0.9 : 0.95,
                    isFallback: true,
                    reason: 'No voices available in browser'
                };
            }

            // Strictly filter out non-English / Hindi voices
            const englishVoices = voiceList.filter(v => isEnglishVoice(v));
            const enInVoices = englishVoices.filter(v => isEnglishIndia(v));
            const enGbVoices = englishVoices.filter(v => v.lang && v.lang.toLowerCase().replace('_', '-').startsWith('en-gb'));
            const enUsVoices = englishVoices.filter(v => v.lang && v.lang.toLowerCase().replace('_', '-').startsWith('en-us'));

            console.log(`[Voice] Candidates evaluated:`, JSON.stringify(englishVoices.slice(0, 5).map(v => ({ name: v.name, lang: v.lang }))));

            if (gender === 'male') {
                // 1. en-IN Male voice (Microsoft Ravi, etc.) — pitch 0.95
                const inMale = enInVoices.find(v => isMaleVoice(v));
                if (inMale) {
                    return { voice: inMale, pitch: 0.95, rate: 0.95, isFallback: false, reason: 'en-IN male voice' };
                }

                // 2. en-GB Male voice (Microsoft George, Google UK English Male) — pitch 0.95
                const gbMale = enGbVoices.find(v => isMaleVoice(v));
                if (gbMale) {
                    return { voice: gbMale, pitch: 0.95, rate: 0.95, isFallback: false, reason: 'en-GB male voice' };
                }

                // 3. en-US Male voice (Microsoft David, Microsoft Mark, Google US English Male) — pitch 0.95
                const usMale = enUsVoices.find(v => isMaleVoice(v));
                if (usMale) {
                    return { voice: usMale, pitch: 0.95, rate: 0.95, isFallback: false, reason: 'en-US male voice' };
                }

                // 4. Any en-* Male voice — pitch 0.95
                const anyEnMale = englishVoices.find(v => isMaleVoice(v));
                if (anyEnMale) {
                    return { voice: anyEnMale, pitch: 0.95, rate: 0.95, isFallback: false, reason: 'English male voice' };
                }

                // 5. Any en-* voice (female fallback) — aggressive downshift pitch 0.5, rate 0.9
                if (englishVoices.length > 0) {
                    console.log("[Voice] Aggressive downshift: female voice used for male persona — pitch 0.5");
                    return { voice: englishVoices[0], pitch: 0.5, rate: 0.9, isFallback: true, reason: 'English female voice downshifted to male (pitch 0.5)' };
                }

                // 6. Default browser voice fallback — pitch 0.5, rate 0.9
                console.log("[Voice] Aggressive downshift: female voice used for male persona — pitch 0.5");
                return { voice: voiceList[0], pitch: 0.5, rate: 0.9, isFallback: true, reason: 'Default voice downshifted to male (pitch 0.5)' };
            } else {
                // FEMALE INTERVIEWER
                // 1. en-IN Female voice (Microsoft Heera, etc.) — pitch 1.0
                const inFemale = enInVoices.find(v => isFemaleVoice(v)) || enInVoices[0];
                if (inFemale) {
                    return { voice: inFemale, pitch: 1.0, rate: 0.95, isFallback: false, reason: 'en-IN female voice' };
                }

                // 2. en-GB Female voice (Microsoft Hazel) — pitch 1.0
                const gbFemale = enGbVoices.find(v => isFemaleVoice(v)) || enGbVoices[0];
                if (gbFemale) {
                    return { voice: gbFemale, pitch: 1.0, rate: 0.95, isFallback: false, reason: 'en-GB female voice' };
                }

                // 3. en-US Female voice (Microsoft Zira) — pitch 1.0
                const usFemale = enUsVoices.find(v => isFemaleVoice(v)) || enUsVoices[0];
                if (usFemale) {
                    return { voice: usFemale, pitch: 1.0, rate: 0.95, isFallback: false, reason: 'en-US female voice' };
                }

                // 4. Any en-* Female voice — pitch 1.0
                const anyEnFemale = englishVoices.find(v => isFemaleVoice(v));
                if (anyEnFemale) {
                    return { voice: anyEnFemale, pitch: 1.0, rate: 0.95, isFallback: false, reason: 'English female voice' };
                }

                // 5. Any en-* voice — pitch 1.0
                if (englishVoices.length > 0) {
                    return { voice: englishVoices[0], pitch: 1.0, rate: 0.95, isFallback: true, reason: 'English voice' };
                }

                // 6. Default voice — pitch 1.0
                return { voice: voiceList[0], pitch: 1.0, rate: 0.95, isFallback: true, reason: 'Default voice' };
            }
        }

        function getOrSelectVoice(gender) {
            const targetGender = gender || coachGender || 'female';

            if (voiceCache[targetGender]) {
                console.log(`[Voice] Using cached voice for ${targetGender}: ${voiceCache[targetGender].voice ? voiceCache[targetGender].voice.name : 'Default'}`);
                return voiceCache[targetGender];
            }

            if (!voices.length && synth) {
                voices = synth.getVoices() || [];
            }

            console.log(`[Voice] Initial selection for ${targetGender} — voices available: ${voices.length}`);
            const result = resolveVoice(targetGender, voices);
            voiceCache[targetGender] = result;

            console.log(`[Voice] Final: ${result.voice ? result.voice.name : 'Default'} | lang: ${result.voice ? result.voice.lang : 'n/a'} | pitch: ${result.pitch} | reason: ${result.reason}`);
            console.log(`[Voice Debug] Session gender: ${targetGender}, selected voice: ${result.voice ? result.voice.name : 'Default'}, lang: ${result.voice ? result.voice.lang : 'en'}, pitch: ${result.pitch}`);

            return result;
        }

        function loadVoices() {
            voices = synth ? synth.getVoices() : [];
            if (voices.length) {
                getOrSelectVoice(coachGender);
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

                const voiceSetup = getOrSelectVoice(coachGender);
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
            voiceCache[coachGender] = null; // Re-evaluate voice on toggle
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
