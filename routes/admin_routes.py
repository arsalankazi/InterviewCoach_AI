from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from models.user import User
from models.admin import Admin
from models.interview_session import InterviewSession
from utils.decorators import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/', methods=['GET'])
@admin_bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    """
    Administrator Dashboard view displaying real-time system metrics,
    summary counts, and searchable student directory.
    """
    search_query = request.args.get('q', '').strip()

    # Retrieve students based on optional search filter
    students = User.get_all(search=search_query if search_query else None)

    # Calculate real-time database counts and baseline metrics
    total_students_count = User.count()
    total_interviews_count = InterviewSession.count_all()
    active_today_count = InterviewSession.count_today()

    metrics = {
        "total_students": total_students_count,
        "total_interviews": total_interviews_count,
        "active_today": active_today_count
    }

    admin_id = session.get('admin_id')
    current_admin = Admin.get_by_id(admin_id)

    return render_template(
        'admin/dashboard.html',
        admin=current_admin,
        students=students,
        metrics=metrics,
        search_query=search_query,
        filtered_count=len(students)
    )
