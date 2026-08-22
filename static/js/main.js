/**
 * InterviewCoach AI - Core Frontend Logic
 */
document.addEventListener('DOMContentLoaded', () => {
    // Health check indicator verification
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
});
