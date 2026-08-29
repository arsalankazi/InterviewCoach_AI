/**
 * InterviewCoach AI - Core Frontend Logic
 * Includes health check, flash auto-dismiss, cascading scroll-reveal observer,
 * statistical count-up animations, and skeleton loaders.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Accessibility check: does the user prefer reduced motion?
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // =============================================================
    // 1. Health Check Indicator
    // =============================================================
    const healthBadge = document.getElementById('health-badge');
    if (healthBadge) {
        fetch('/health')
            .then(res => res.json())
            .then(data => {
                if (data && data.success) {
                    const statusText = document.getElementById('status-text');
                    if (statusText) {
                        statusText.textContent = 'System Online';
                    }
                }
            })
            .catch(err => {
                console.warn('Health check query notice:', err);
            });
    }

    // =============================================================
    // 2. Global Flash Message Auto-Dismiss (5.5s timeout with fade-out)
    // =============================================================
    const flashAlerts = document.querySelectorAll('.flash-alert');
    flashAlerts.forEach((alert) => {
        setTimeout(() => {
            alert.classList.add('flash-dismissing');
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.parentNode.removeChild(alert);
                }
            }, 500); // matches CSS fade-out transition duration
        }, 5500);
    });

    // =============================================================
    // 3. Smooth Number / Stat Count-Up Animation
    // =============================================================
    function animateCountUp(el) {
        if (el.dataset.hasCounted) return;
        el.dataset.hasCounted = 'true';

        const rawText = el.getAttribute('data-count-up') || el.textContent.trim();
        // Parse prefix, number, and suffix (e.g. "85%", "25+", "$100", "0")
        const match = rawText.match(/^([^\d\.]*)(\d+(?:\.\d+)?)(.*)$/);
        if (!match) return;

        const prefix = match[1] || '';
        const targetNum = parseFloat(match[2]);
        const suffix = match[3] || '';
        const isFloat = match[2].includes('.');
        const duration = 1200; // ms

        if (prefersReducedMotion || isNaN(targetNum) || targetNum === 0) {
            el.textContent = rawText;
            const card = el.closest('.stat-card');
            if (card) card.classList.add('stat-counted');
            return;
        }

        const startTime = performance.now();

        function updateNumber(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // Ease-out cubic: 1 - pow(1 - progress, 3)
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const currentVal = targetNum * easeOut;

            if (isFloat) {
                el.textContent = `${prefix}${currentVal.toFixed(1)}${suffix}`;
            } else {
                el.textContent = `${prefix}${Math.round(currentVal)}${suffix}`;
            }

            if (progress < 1) {
                requestAnimationFrame(updateNumber);
            } else {
                el.textContent = rawText;
                const card = el.closest('.stat-card');
                if (card) card.classList.add('stat-counted');
            }
        }

        requestAnimationFrame(updateNumber);
    }

    // =============================================================
    // 4. Scroll-Reveal with Cascading Stagger
    // =============================================================
    const gridContainers = document.querySelectorAll('.stats-grid, .action-grid, .features-grid, .practice-grid, .history-grid');
    gridContainers.forEach(grid => {
        const children = grid.querySelectorAll('.reveal-on-scroll, .stat-card, .action-card');
        children.forEach((child, idx) => {
            child.style.setProperty('--reveal-index', idx);
            child.classList.add('reveal-on-scroll');
        });
    });

    const revealElements = document.querySelectorAll('.reveal-on-scroll, [data-count-up]');

    if (!prefersReducedMotion && 'IntersectionObserver' in window && revealElements.length > 0) {
        const revealObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const target = entry.target;
                    target.classList.add('is-revealed');

                    // If target or any child has count-up requirement, trigger animation
                    if (target.hasAttribute('data-count-up')) {
                        animateCountUp(target);
                    }
                    const countChildren = target.querySelectorAll('[data-count-up]');
                    countChildren.forEach(child => animateCountUp(child));

                    observer.unobserve(target);
                }
            });
        }, {
            threshold: 0.08,
            rootMargin: '0px 0px -20px 0px'
        });

        revealElements.forEach(el => revealObserver.observe(el));
    } else {
        // Fallback or reduced motion: reveal immediately
        revealElements.forEach(el => {
            el.classList.add('is-revealed');
            if (el.hasAttribute('data-count-up')) {
                animateCountUp(el);
            }
            const countChildren = el.querySelectorAll('[data-count-up]');
            countChildren.forEach(child => animateCountUp(child));
        });
    }

    // =============================================================
    // 5. Skeleton Screen Crossfade Transition
    // =============================================================
    const skeletonWrappers = document.querySelectorAll('.has-skeleton-loader');
    if (skeletonWrappers.length > 0) {
        const transitionDelay = prefersReducedMotion ? 0 : 180;

        setTimeout(() => {
            skeletonWrappers.forEach(wrapper => {
                wrapper.classList.add('skeleton-loaded');
                const hiddenReveals = wrapper.querySelectorAll('.reveal-on-scroll, [data-count-up]');
                hiddenReveals.forEach(el => {
                    el.classList.add('is-revealed');
                    if (el.hasAttribute('data-count-up')) {
                        animateCountUp(el);
                    }
                });
            });
        }, transitionDelay);
    }
});
