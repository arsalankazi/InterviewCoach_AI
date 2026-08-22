from functools import wraps
from flask import session, redirect, url_for, flash, request
from utils.helpers import api_error


def login_required(f):
    """
    Decorator to restrict access to authenticated students.
    Redirects unauthenticated users to the student login page.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('student_id') or session.get('user_id')
        if not user_id:
            if request.is_json or request.path.startswith('/api/'):
                return api_error(message="Authentication required", status_code=401)
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Decorator to restrict access to authenticated administrators.
    Redirects logged-in students to their student dashboard and unauthenticated users to the admin login portal.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = session.get('admin_id')
        role = session.get('role')
        if not admin_id or role != 'admin':
            if request.is_json or request.path.startswith('/api/'):
                return api_error(message="Admin access required", status_code=403)
            flash("Administrator access required.", "error")

            # If user is a logged-in student, redirect to student dashboard
            if session.get('student_id') or session.get('user_id') or role == 'student':
                return redirect(url_for('student.dashboard'))

            return redirect(url_for('auth.admin_login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def guest_required(f):
    """
    Decorator to prevent already logged-in users from viewing login/registration forms.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('admin_id') or session.get('role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        if session.get('student_id') or session.get('user_id') or session.get('role') == 'student':
            return redirect(url_for('student.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
