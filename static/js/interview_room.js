/**
 * static/js/interview_room.js
 * 
 * Module 11: Virtual AI Interviewer Frontend Controller
 * Handles real-time conversational exchange, typing animations,
 * Stage 1 initialization, auto-scrolling, and resilient retry logic.
 */

document.addEventListener('DOMContentLoaded', () => {
    const roomWrapper = document.querySelector('.interview-room-wrapper');
    if (!roomWrapper) return;

    // Session Configuration & State
    const sessionId = parseInt(roomWrapper.dataset.sessionId, 10);
    const sessionStatus = roomWrapper.dataset.sessionStatus || 'setup';
    const interviewerName = roomWrapper.dataset.interviewerName || 'AI Interviewer';
    const interviewerGender = (roomWrapper.dataset.interviewerGender || 'male').toLowerCase();
    const studentName = roomWrapper.dataset.studentName || 'Candidate';
    const isCompleted = sessionStatus === 'completed';

    // DOM Elements
    const chatContainer = document.getElementById('chat-messages');
    const typingIndicator = document.getElementById('typing-indicator');
    const chatInput = document.getElementById('chat-input');
    const btnSend = document.getElementById('btn-send');
    const turnCountElem = document.getElementById('turn-count');
    const errorBanner = document.getElementById('chat-error-banner');
    const errorTextElem = document.getElementById('error-message-text');
    const btnRetry = document.getElementById('btn-retry');

    let isSubmitting = false;
    let pendingAnswerText = null;

    /**
     * Format current time as HH:MM AM/PM
     */
    function getCurrentTimeString() {
        const now = new Date();
        return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Auto-scroll message container to bottom
     */
    function scrollToBottom(smooth = true) {
        if (!chatContainer) return;
        chatContainer.scrollTo({
            top: chatContainer.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto'
        });
    }

    /**
     * Update turn counter in header
     */
    function updateTurnCount() {
        if (!turnCountElem || !chatContainer) return;
        const turns = chatContainer.querySelectorAll('.message-turn:not(.typing-wrapper)').length;
        turnCountElem.textContent = turns;
    }

    /**
     * Build and append a message turn bubble to the conversation stream
     */
    function appendMessageBubble(sender, messageText, timestamp = null) {
        const turnDiv = document.createElement('div');
        turnDiv.className = `message-turn message-${sender} animate-bubble`;

        const timeStr = timestamp || getCurrentTimeString();
        const avatarEmoji = interviewerGender === 'female' ? '👩‍💼' : '👨‍💼';
        const avatarClass = interviewerGender === 'female' ? 'avatar-female' : 'avatar-male';

        if (sender === 'ai') {
            turnDiv.innerHTML = `
                <div class="message-avatar-wrap ${avatarClass}">
                    ${avatarEmoji}
                </div>
                <div class="message-body">
                    <div class="message-sender-name"></div>
                    <div class="message-bubble bubble-ai">
                        <p class="bubble-text"></p>
                    </div>
                    <div class="message-timestamp">${timeStr}</div>
                </div>
            `;
            // Secure text assignment to prevent XSS
            turnDiv.querySelector('.message-sender-name').textContent = interviewerName;
            turnDiv.querySelector('.bubble-text').textContent = messageText;
        } else {
            turnDiv.innerHTML = `
                <div class="message-body">
                    <div class="message-sender-name"></div>
                    <div class="message-bubble bubble-student">
                        <p class="bubble-text"></p>
                    </div>
                    <div class="message-timestamp">${timeStr}</div>
                </div>
                <div class="message-avatar-wrap avatar-student">
                    🎓
                </div>
            `;
            turnDiv.querySelector('.message-sender-name').textContent = studentName;
            turnDiv.querySelector('.bubble-text').textContent = messageText;
        }

        // Insert before typing indicator
        if (typingIndicator && typingIndicator.parentNode === chatContainer) {
            chatContainer.insertBefore(turnDiv, typingIndicator);
        } else {
            chatContainer.appendChild(turnDiv);
        }

        updateTurnCount();
        scrollToBottom(true);
    }

    /**
     * Show/Hide animated typing indicator
     */
    function showTyping() {
        if (typingIndicator) {
            typingIndicator.style.display = 'flex';
            scrollToBottom(true);
        }
    }

    function hideTyping() {
        if (typingIndicator) {
            typingIndicator.style.display = 'none';
        }
    }

    /**
     * Show inline error banner with retry
     */
    function showError(message) {
        if (errorBanner && errorTextElem) {
            errorTextElem.textContent = message || 'Failed to communicate with AI interviewer.';
            errorBanner.style.display = 'flex';
            scrollToBottom(true);
        }
    }

    function hideError() {
        if (errorBanner) {
            errorBanner.style.display = 'none';
        }
    }

    /**
     * Core Dispatcher: Post student answer or initial turn to backend conversation engine
     */
    async function sendTurn(answerText) {
        if (isSubmitting || isCompleted) return;

        isSubmitting = true;
        pendingAnswerText = answerText;
        hideError();
        showTyping();

        if (chatInput) chatInput.disabled = true;
        if (btnSend) btnSend.disabled = true;

        try {
            const response = await fetch(`/student/interviews/${sessionId}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ answer: answerText })
            });

            const data = await response.json();

            if (data && (data.success || data.ai_message)) {
                appendMessageBubble('ai', data.ai_message);
                pendingAnswerText = null;
            } else {
                const err = (data && data.error) ? data.error : 'Unable to receive interviewer response.';
                showError(err);
            }
        } catch (networkError) {
            console.error('Interview chat connection error:', networkError);
            showError('Network connectivity issue. Please check your connection and retry.');
        } finally {
            hideTyping();
            isSubmitting = false;

            if (!isCompleted) {
                if (chatInput) {
                    chatInput.disabled = false;
                    chatInput.focus();
                }
                if (btnSend) {
                    btnSend.disabled = false;
                }
            }
            scrollToBottom(true);
        }
    }

    /**
     * Event: Student submits answer
     */
    function handleStudentSubmit() {
        if (!chatInput || isSubmitting || isCompleted) return;

        const text = chatInput.value.trim();
        if (!text) return;

        // Immediately append student bubble to conversation
        appendMessageBubble('student', text);

        // Reset input field and height
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // Dispatch answer to AI engine
        sendTurn(text);
    }

    // Bind Send Button Click
    if (btnSend) {
        btnSend.addEventListener('click', (e) => {
            e.preventDefault();
            handleStudentSubmit();
        });
    }

    // Bind Keyboard Shortcuts in Textarea
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleStudentSubmit();
            }
        });

        // Auto-resize textarea height
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            const newHeight = Math.min(chatInput.scrollHeight, 130);
            chatInput.style.height = `${newHeight}px`;
        });
    }

    // Bind Retry Button Click
    if (btnRetry) {
        btnRetry.addEventListener('click', (e) => {
            e.preventDefault();
            hideError();
            sendTurn(pendingAnswerText);
        });
    }

    // Initial page load behavior
    scrollToBottom(false);

    // If session is active and no message turns exist yet, automatically trigger Stage 1 Greeting
    if (!isCompleted) {
        const existingTurns = chatContainer.querySelectorAll('.message-turn:not(.typing-wrapper)');
        if (existingTurns.length === 0) {
            sendTurn(null);
        }
    }
});
