/**
 * static/js/mascot.js
 *
 * Decorative AI Robot Mascot for Student Dashboard.
 * Self-contained idle eye-blink loop and navigation to the
 * "How It Works" standalone page upon click.
 */
document.addEventListener('DOMContentLoaded', () => {
    const mascotContainer = document.getElementById('dashboard-mascot');
    const mascotEyes = document.querySelectorAll('.mascot-eye-lid');

    if (!mascotContainer) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // =========================================================
    // 1. Periodic Eye Blink Engine
    // =========================================================
    function scheduleBlink() {
        if (prefersReducedMotion) return;
        const delay = 3200 + Math.random() * 2300;
        setTimeout(() => {
            mascotEyes.forEach(lid => {
                lid.style.opacity = '1';
                lid.style.transform = 'scaleY(1)';
            });
            setTimeout(() => {
                mascotEyes.forEach(lid => {
                    lid.style.opacity = '0';
                    lid.style.transform = 'scaleY(0)';
                });
                scheduleBlink();
            }, 140);
        }, delay);
    }

    if (!prefersReducedMotion) {
        scheduleBlink();
    }

    // =========================================================
    // 2. Click / Keyboard — Restart Dashboard Onboarding Tour
    // =========================================================
    function triggerTourRestart() {
        if (typeof window.restartTour === 'function') {
            window.restartTour();
        } else {
            window.location.href = '/student/how-it-works';
        }
    }

    mascotContainer.addEventListener('click', () => {
        triggerTourRestart();
    });

    mascotContainer.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            triggerTourRestart();
        }
    });
});
