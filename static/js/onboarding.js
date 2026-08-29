/**
 * static/js/onboarding.js
 *
 * InterviewCoach AI — Student Dashboard Onboarding Tour
 *
 * Features:
 *   - Position-aware glassmorphic card (center, right, left)
 *   - Glowing Top Progress Bar
 *   - Step slide-in fade micro-transitions
 *   - Canvas-based confetti burst on completion
 *   - Z-index sibling architecture (no stacking context trapping)
 */

(function () {
    'use strict';

    /* ------------------------------------------------------------------ */
    /*  STEPS                                                               */
    /* ------------------------------------------------------------------ */
    var STEPS = [
        {
            icon:   '🌟',
            badge:  'Welcome · 1 of 6',
            title:  'Your AI Interview Coach Awaits',
            body:   "Let's walk through your dashboard so you can hit the ground running. This tour takes under a minute.",
            target: null,
            pos:    'center'
        },
        {
            icon:   '📄',
            badge:  'Resume · 2 of 6',
            title:  'Upload Your Resume',
            body:   'Upload a PDF resume so the AI can extract your skills and generate personalised interview questions.',
            target: '#tour-card-resume',
            pos:    'center'
        },
        {
            icon:   '🎙️',
            badge:  'Full Interview · 3 of 6',
            title:  'Start a Full Mock Interview',
            body:   'Launch a 4-stage AI-driven interview tailored to your target role, complete with a detailed scoring report.',
            target: '#tour-card-interview',
            pos:    'center'
        },
        {
            icon:   '⚡',
            badge:  'Quick Practice · 4 of 6',
            title:  'Quick Practice Drills',
            body:   'Pick a single topic and drill focused questions in 5 minutes. Great for rapid skill improvement.',
            target: '#tour-card-practice',
            pos:    'right'   /* target card is on the left — modal shifts right */
        },
        {
            icon:   '📚',
            badge:  'Progress · 5 of 6',
            title:  'Track Your Weak Topics',
            body:   'See every question you scored below 70%, with AI breakdown on how to improve each one.',
            target: '#tour-card-weak-topics',
            pos:    'left'    /* target card is on the right — modal shifts left */
        },
        {
            icon:   '🚀',
            badge:  'All Set · 6 of 6',
            title:  "You're All Set!",
            body:   'Click the robot mascot at any time to restart this tour. Good luck with your preparation!',
            target: null,
            pos:    'center'
        }
    ];

    /* ------------------------------------------------------------------ */
    /*  STATE                                                               */
    /* ------------------------------------------------------------------ */
    var step        = 0;
    var active      = false;
    var highlighted = null;

    /* ------------------------------------------------------------------ */
    /*  DOM REFS                                                            */
    /* ------------------------------------------------------------------ */
    var elBackdrop    = null;
    var elCard        = null;
    var elProgressBar = null;
    var elBadge       = null;
    var elBodyWrap    = null;
    var elIcon        = null;
    var elTitle       = null;
    var elDesc        = null;
    var elSkip        = null;
    var elBack        = null;
    var elNext        = null;

    /* ------------------------------------------------------------------ */
    /*  INLINE STYLE HELPER                                                 */
    /* ------------------------------------------------------------------ */
    function css(el, styles) {
        Object.assign(el.style, styles);
    }

    /* ------------------------------------------------------------------ */
    /*  CONFETTI CELEBRATION EFFECT                                         */
    /* ------------------------------------------------------------------ */
    function launchConfetti() {
        var canvas = document.createElement('canvas');
        css(canvas, {
            position:      'fixed',
            top:           '0',
            left:          '0',
            width:         '100vw',
            height:        '100vh',
            pointerEvents: 'none',
            zIndex:        '999999'
        });
        document.body.appendChild(canvas);

        var ctx = canvas.getContext('2d');
        var width = canvas.width = window.innerWidth;
        var height = canvas.height = window.innerHeight;

        var colors = ['#6366f1', '#a855f7', '#38bdf8', '#10b981', '#f59e0b', '#ec4899', '#ffffff'];
        var particles = [];
        var particleCount = 75;

        for (var i = 0; i < particleCount; i++) {
            particles.push({
                x: width * 0.5,
                y: height * 0.55,
                vx: (Math.random() - 0.5) * 16,
                vy: (Math.random() - 0.7) * 18 - 4,
                size: Math.random() * 8 + 4,
                color: colors[Math.floor(Math.random() * colors.length)],
                rotation: Math.random() * 360,
                rotSpeed: (Math.random() - 0.5) * 10,
                opacity: 1,
                decay: Math.random() * 0.015 + 0.01
            });
        }

        var startTime = performance.now();
        function updateConfetti() {
            var elapsed = performance.now() - startTime;
            ctx.clearRect(0, 0, width, height);

            var activeCount = 0;
            for (var j = 0; j < particles.length; j++) {
                var p = particles[j];
                p.x += p.vx;
                p.y += p.vy;
                p.vy += 0.45; // gravity
                p.vx *= 0.98; // friction
                p.rotation += p.rotSpeed;
                p.opacity -= p.decay;

                if (p.opacity > 0) {
                    activeCount++;
                    ctx.save();
                    ctx.translate(p.x, p.y);
                    ctx.rotate((p.rotation * Math.PI) / 180);
                    ctx.globalAlpha = Math.max(0, p.opacity);
                    ctx.fillStyle = p.color;
                    ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
                    ctx.restore();
                }
            }

            if (activeCount > 0 && elapsed < 2200) {
                requestAnimationFrame(updateConfetti);
            } else {
                if (canvas.parentNode) {
                    canvas.parentNode.removeChild(canvas);
                }
            }
        }

        requestAnimationFrame(updateConfetti);
    }

    /* ------------------------------------------------------------------ */
    /*  BUILD DOM (once)                                                    */
    /* ------------------------------------------------------------------ */
    function buildDOM() {
        if (elBackdrop) return;

        /* --- BACKDROP --- */
        elBackdrop = document.createElement('div');
        elBackdrop.id = 'ot-backdrop';
        css(elBackdrop, {
            position:             'fixed',
            top:                  '0',
            left:                 '0',
            width:                '100vw',
            height:               '100vh',
            background:           'rgba(11,15,25,0.82)',
            backdropFilter:       'blur(6px)',
            webkitBackdropFilter: 'blur(6px)',
            zIndex:               '9000',
            display:              'none'
        });
        elBackdrop.addEventListener('click', function () { skip(); });
        document.body.appendChild(elBackdrop);

        /* --- TOUR CARD --- */
        elCard = document.createElement('div');
        elCard.id = 'ot-card';
        elCard.setAttribute('role', 'dialog');
        elCard.setAttribute('aria-modal', 'true');
        elCard.setAttribute('aria-labelledby', 'ot-title');
        css(elCard, {
            position:             'fixed',
            zIndex:               '9002',
            width:                'calc(100% - 3rem)',
            maxWidth:             '520px',
            background:           'rgba(17,24,39,0.96)',
            border:               '1px solid rgba(99,102,241,0.35)',
            borderRadius:         '16px',
            padding:              '2rem',
            boxShadow:            '0 24px 60px rgba(0,0,0,0.85), 0 0 40px rgba(99,102,241,0.2), inset 0 1px 0 rgba(255,255,255,0.08)',
            backdropFilter:       'blur(20px)',
            webkitBackdropFilter: 'blur(20px)',
            color:                '#f1f5f9',
            display:              'none',
            flexDirection:        'column',
            gap:                  '1.25rem',
            boxSizing:            'border-box',
            fontFamily:           'inherit',
            overflow:             'hidden'
        });
        elCard.addEventListener('click', function (e) { e.stopPropagation(); });
        document.body.appendChild(elCard);

        /* --- PROGRESS TRACK & BAR --- */
        var progressTrack = document.createElement('div');
        progressTrack.id = 'ot-progress-track';
        css(progressTrack, {
            position:   'absolute',
            top:        '0',
            left:       '0',
            width:      '100%',
            height:     '4px',
            background: 'rgba(255,255,255,0.06)'
        });

        elProgressBar = document.createElement('div');
        elProgressBar.id = 'ot-progress-bar';
        css(elProgressBar, {
            height:     '100%',
            width:      '16.66%',
            background: 'linear-gradient(90deg, #6366f1, #a855f7, #38bdf8)',
            boxShadow:  '0 0 12px rgba(99,102,241,0.8)',
            transition: 'width 0.35s cubic-bezier(0.16, 1, 0.3, 1)'
        });
        progressTrack.appendChild(elProgressBar);
        elCard.appendChild(progressTrack);

        /* --- HEADER --- */
        var header = document.createElement('div');
        css(header, {
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'space-between',
            gap:            '0.75rem',
            marginTop:      '0.25rem'
        });

        elBadge = document.createElement('span');
        elBadge.id = 'ot-badge';
        css(elBadge, {
            fontSize:      '0.74rem',
            fontWeight:    '700',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color:         '#a5b4fc',
            background:    'rgba(99,102,241,0.15)',
            border:        '1px solid rgba(99,102,241,0.3)',
            padding:       '0.28rem 0.8rem',
            borderRadius:  '9999px'
        });

        var btnClose = document.createElement('button');
        btnClose.type = 'button';
        btnClose.id = 'ot-close';
        btnClose.setAttribute('aria-label', 'Close tour');
        btnClose.innerHTML = '&times;';
        css(btnClose, {
            background:   'transparent',
            border:       'none',
            fontSize:     '1.6rem',
            lineHeight:   '1',
            color:        '#64748b',
            cursor:       'pointer',
            padding:      '0.15rem 0.45rem',
            borderRadius: '6px'
        });
        btnClose.onmouseover = function () { this.style.color = '#f1f5f9'; this.style.background = 'rgba(255,255,255,0.09)'; };
        btnClose.onmouseout  = function () { this.style.color = '#64748b'; this.style.background = 'transparent'; };
        btnClose.addEventListener('click', function (e) { e.stopPropagation(); skip(); });

        header.appendChild(elBadge);
        header.appendChild(btnClose);

        /* --- BODY --- */
        elBodyWrap = document.createElement('div');
        elBodyWrap.id = 'ot-body';
        css(elBodyWrap, {
            display:       'flex',
            flexDirection: 'column',
            alignItems:    'center',
            textAlign:     'center',
            gap:           '0.65rem',
            padding:       '0.5rem 0'
        });

        elIcon = document.createElement('div');
        elIcon.id = 'ot-icon';
        css(elIcon, {
            fontSize:     '3rem',
            lineHeight:   '1',
            filter:       'drop-shadow(0 4px 14px rgba(99,102,241,0.45))',
            marginBottom: '0.1rem'
        });

        elTitle = document.createElement('h3');
        elTitle.id = 'ot-title';
        css(elTitle, {
            fontSize:      '1.38rem',
            fontWeight:    '800',
            color:         '#ffffff',
            letterSpacing: '-0.02em',
            margin:        '0',
            lineHeight:    '1.3'
        });

        elDesc = document.createElement('p');
        elDesc.id = 'ot-desc';
        css(elDesc, {
            fontSize:   '0.96rem',
            color:      '#94a3b8',
            lineHeight: '1.65',
            margin:     '0',
            maxWidth:   '420px'
        });

        elBodyWrap.appendChild(elIcon);
        elBodyWrap.appendChild(elTitle);
        elBodyWrap.appendChild(elDesc);

        /* --- FOOTER --- */
        var footer = document.createElement('div');
        css(footer, {
            display:        'flex',
            alignItems:     'center',
            justifyContent: 'space-between',
            paddingTop:     '1.2rem',
            borderTop:      '1px solid rgba(255,255,255,0.07)',
            gap:            '0.75rem'
        });

        elSkip = document.createElement('button');
        elSkip.type = 'button';
        elSkip.id = 'ot-skip';
        elSkip.textContent = 'Skip Tour';
        styleGhost(elSkip);
        elSkip.addEventListener('click', function (e) { e.stopPropagation(); skip(); });

        var navGroup = document.createElement('div');
        css(navGroup, { display: 'flex', alignItems: 'center', gap: '0.65rem' });

        elBack = document.createElement('button');
        elBack.type = 'button';
        elBack.id = 'ot-back';
        elBack.textContent = '\u2190 Back';
        styleOutline(elBack);
        elBack.addEventListener('click', function (e) { e.stopPropagation(); goTo(step - 1); });

        elNext = document.createElement('button');
        elNext.type = 'button';
        elNext.id = 'ot-next';
        elNext.textContent = 'Next \u2192';
        stylePrimary(elNext);
        elNext.addEventListener('click', function (e) {
            e.stopPropagation();
            if (step === STEPS.length - 1) { complete(); } else { goTo(step + 1); }
        });

        navGroup.appendChild(elBack);
        navGroup.appendChild(elNext);
        footer.appendChild(elSkip);
        footer.appendChild(navGroup);

        /* --- ASSEMBLE --- */
        elCard.appendChild(header);
        elCard.appendChild(elBodyWrap);
        elCard.appendChild(footer);
    }

    /* ------------------------------------------------------------------ */
    /*  BUTTON STYLES                                                       */
    /* ------------------------------------------------------------------ */
    function stylePrimary(btn) {
        css(btn, {
            background:   'linear-gradient(135deg,#6366f1,#4f46e5)',
            border:       '1px solid rgba(99,102,241,0.6)',
            borderRadius: '8px',
            color:        '#fff',
            fontSize:     '0.9rem',
            fontWeight:   '600',
            padding:      '0.52rem 1.15rem',
            cursor:       'pointer',
            whiteSpace:   'nowrap'
        });
        btn.onmouseover = function () { this.style.background = 'linear-gradient(135deg,#818cf8,#6366f1)'; };
        btn.onmouseout  = function () { this.style.background = 'linear-gradient(135deg,#6366f1,#4f46e5)'; };
    }

    function styleOutline(btn) {
        css(btn, {
            background:   'transparent',
            border:       '1px solid rgba(99,102,241,0.4)',
            borderRadius: '8px',
            color:        '#a5b4fc',
            fontSize:     '0.9rem',
            fontWeight:   '600',
            padding:      '0.52rem 1.15rem',
            cursor:       'pointer',
            whiteSpace:   'nowrap'
        });
        btn.onmouseover = function () { this.style.background = 'rgba(99,102,241,0.12)'; };
        btn.onmouseout  = function () { this.style.background = 'transparent'; };
    }

    function styleGhost(btn) {
        css(btn, {
            background:   'transparent',
            border:       '1px solid transparent',
            borderRadius: '8px',
            color:        '#64748b',
            fontSize:     '0.88rem',
            fontWeight:   '500',
            padding:      '0.52rem 0.9rem',
            cursor:       'pointer',
            whiteSpace:   'nowrap'
        });
        btn.onmouseover = function () { this.style.color = '#f1f5f9'; this.style.background = 'rgba(255,255,255,0.06)'; };
        btn.onmouseout  = function () { this.style.color = '#64748b'; this.style.background = 'transparent'; };
    }

    /* ------------------------------------------------------------------ */
    /*  CARD POSITIONING                                                    */
    /* ------------------------------------------------------------------ */
    function positionCard(pos) {
        if (pos === 'right') {
            css(elCard, {
                top:       '50%',
                left:      'auto',
                right:     '2.5rem',
                transform: 'translateY(-50%)'
            });
        } else if (pos === 'left') {
            css(elCard, {
                top:       '50%',
                left:      '2.5rem',
                right:     'auto',
                transform: 'translateY(-50%)'
            });
        } else {
            css(elCard, {
                top:       '50%',
                left:      '50%',
                right:     'auto',
                transform: 'translate(-50%, -50%)'
            });
        }
    }

    /* ------------------------------------------------------------------ */
    /*  HIGHLIGHT HELPERS                                                   */
    /* ------------------------------------------------------------------ */
    function applyHighlight(selector) {
        removeHighlight();
        if (!selector) return;
        var el = document.querySelector(selector);
        if (!el) return;

        highlighted = el;
        el._otPrevShadow   = el.style.boxShadow   || '';
        el._otPrevPosition = el.style.position     || '';
        el._otPrevZIndex   = el.style.zIndex       || '';
        el._otPrevBorder   = el.style.borderColor  || '';

        css(el, {
            boxShadow:   '0 0 0 3px #6366f1, 0 0 40px rgba(99,102,241,0.5)',
            position:    'relative',
            zIndex:      '9001',
            borderColor: '#818cf8'
        });

        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function removeHighlight() {
        if (!highlighted) return;
        css(highlighted, {
            boxShadow:   highlighted._otPrevShadow,
            position:    highlighted._otPrevPosition,
            zIndex:      highlighted._otPrevZIndex,
            borderColor: highlighted._otPrevBorder
        });
        highlighted = null;
    }

    /* ------------------------------------------------------------------ */
    /*  RENDER STEP                                                         */
    /* ------------------------------------------------------------------ */
    function render(index) {
        buildDOM();
        step = index;
        var s       = STEPS[step];
        var isFirst = step === 0;
        var isLast  = step === STEPS.length - 1;

        /* Update progress bar width */
        var progressPct = ((step + 1) / STEPS.length) * 100;
        if (elProgressBar) {
            elProgressBar.style.width = progressPct.toFixed(1) + '%';
        }

        /* Update content */
        elBadge.textContent = s.badge;
        elIcon.textContent  = s.icon;
        elTitle.textContent = s.title;
        elDesc.textContent  = s.body;

        /* Body slide micro-transition */
        if (elBodyWrap) {
            elBodyWrap.classList.remove('ot-body-slide-in');
            void elBodyWrap.offsetWidth; // trigger reflow
            elBodyWrap.classList.add('ot-body-slide-in');
        }

        /* Button visibility */
        elBack.style.display = isFirst ? 'none' : '';
        elSkip.style.display = isLast  ? 'none' : '';
        elNext.textContent   = isLast  ? 'Got It! Start Practicing \uD83D\uDE80' : 'Next \u2192';
        if (isLast) { stylePrimary(elNext); }

        /* Backdrop */
        css(elBackdrop, {
            display:              'block',
            background:           'rgba(11,15,25,0.82)',
            backdropFilter:       'blur(6px)',
            webkitBackdropFilter: 'blur(6px)'
        });

        if (s.target) {
            applyHighlight(s.target);
        } else {
            removeHighlight();
        }

        positionCard(s.pos || 'center');
        css(elCard, { display: 'flex' });
    }

    /* ------------------------------------------------------------------ */
    /*  FLOW CONTROLS                                                       */
    /* ------------------------------------------------------------------ */
    function goTo(index) {
        if (!active) return;
        if (index < 0 || index >= STEPS.length) return;
        removeHighlight();
        render(index);
    }

    function hide() {
        active = false;
        removeHighlight();
        if (elBackdrop) css(elBackdrop, { display: 'none' });
        if (elCard)     css(elCard,     { display: 'none' });
    }

    function callApi() {
        fetch('/student/complete-onboarding', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
        }).catch(function () {});
    }

    function skip() {
        hide();
        callApi();
    }

    function complete() {
        launchConfetti();
        hide();
        callApi();
    }

    function start() {
        buildDOM();
        active = true;
        render(0);
    }

    /* ------------------------------------------------------------------ */
    /*  KEYBOARD CONTROLS                                                   */
    /* ------------------------------------------------------------------ */
    window.addEventListener('keydown', function (e) {
        if (!active) return;
        if (e.key === 'Escape')          { e.preventDefault(); skip(); }
        else if (e.key === 'ArrowRight') { e.preventDefault(); goTo(step + 1); }
        else if (e.key === 'ArrowLeft')  { e.preventDefault(); goTo(step - 1); }
    });

    /* ------------------------------------------------------------------ */
    /*  PUBLIC API                                                          */
    /* ------------------------------------------------------------------ */
    window.startOnboardingTour = start;
    window.restartTour         = start;
    window.skipTour            = skip;
    window.completeTour        = complete;

}());
