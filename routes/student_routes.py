from flask import Blueprint, render_template, session, redirect, url_for, flash
from models.user import User
from utils.decorators import login_required

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    """
    Student Dashboard view showing summary statistics, status indicators, and quick action cards.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    
    if not user:
        flash("User profile not found. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    # Summary metrics (baseline placeholders for Module 3)
    metrics = {
        "total_interviews": 0,
        "avg_score": "N/A",
        "resume_status": "Not Uploaded"
    }

    return render_template('student/dashboard.html', user=user, metrics=metrics)


@student_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    """
    Student Profile view displaying personal details, email, and registration metadata.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User profile not found. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    return render_template('student/profile.html', user=user)


# ---------------------------------------------------------
# Action Link Placeholders (To be implemented in future modules)
# ---------------------------------------------------------

@student_bp.route('/interviews/new', methods=['GET'])
@login_required
def start_interview():
    """Placeholder endpoint for starting a new interview session."""
    flash("The AI Interview Engine will be unlocked in Module 4!", "info")
    return redirect(url_for('student.dashboard'))


@student_bp.route('/interviews/history', methods=['GET'])
@login_required
def interview_history():
    """Placeholder endpoint for viewing past interview history."""
    flash("Interview history and scorecard analytics will be available in Module 5!", "info")
    return redirect(url_for('student.dashboard'))


@student_bp.route('/resume/upload', methods=['GET'])
@login_required
def upload_resume():
    """Placeholder endpoint for resume upload and analysis."""
    flash("Resume parsing and skills extraction feature is coming in the next module!", "info")
    return redirect(url_for('student.dashboard'))
