from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.user import User
from models.admin import Admin
from utils.validators import validate_registration, validate_login
from utils.decorators import guest_required

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# ---------------------------------------------------------
# Student Authentication Routes
# ---------------------------------------------------------

@auth_bp.route('/register', methods=['GET', 'POST'])
@guest_required
def register():
    """
    Student registration endpoint.
    GET: Displays the registration form.
    POST: Validates input, creates a new user, and initializes student session.
    """
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        is_valid, error_msg = validate_registration(name, email, password, confirm_password)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('auth/register.html', name=name, email=email), 400

        try:
            user = User.create(name=name, email=email, password=password)
            # Establish student session
            session.clear()
            session['student_id'] = user.id
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_email'] = user.email
            session['role'] = 'student'

            flash(f"Account created successfully! Welcome to InterviewCoach AI, {user.name}.", 'success')
            return redirect(url_for('student.dashboard'))
        except Exception as e:
            flash(f"Registration failed: {str(e)}", 'error')
            return render_template('auth/register.html', name=name, email=email), 500

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
@guest_required
def login():
    """
    Student login endpoint.
    GET: Displays student login form.
    POST: Authenticates credentials and starts session.
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        next_page = request.args.get('next') or request.form.get('next')

        is_valid, error_msg = validate_login(email, password)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('auth/login.html', email=email), 400

        user = User.get_by_email(email)
        if not user or not user.check_password(password):
            flash("Invalid email or password.", 'error')
            return render_template('auth/login.html', email=email), 401

        # Establish student session
        session.clear()
        session['student_id'] = user.id
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        session['role'] = 'student'

        flash(f"Welcome back, {user.name}!", 'success')
        
        # Prevent open redirect vulnerabilities
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('student.dashboard'))

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Student logout endpoint. Clears session and redirects to login.
    """
    session.clear()
    flash("You have been successfully logged out.", 'info')
    return redirect(url_for('auth.login'))


# ---------------------------------------------------------
# Administrator Authentication Routes
# ---------------------------------------------------------

@auth_bp.route('/admin/login', methods=['GET', 'POST'])
@guest_required
def admin_login():
    """
    Administrator login portal.
    Admin accounts cannot be self-registered and must be seeded.
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        next_page = request.args.get('next') or request.form.get('next')

        is_valid, error_msg = validate_login(email, password)
        if not is_valid:
            flash(error_msg, 'error')
            return render_template('auth/admin_login.html', email=email), 400

        admin = Admin.get_by_email(email)
        if not admin or not admin.check_password(password):
            flash("Invalid administrator credentials.", 'error')
            return render_template('auth/admin_login.html', email=email), 401

        # Establish admin session
        session.clear()
        session['admin_id'] = admin.id
        session['admin_name'] = admin.name
        session['admin_email'] = admin.email
        session['role'] = 'admin'

        flash(f"Admin authentication verified. Welcome, {admin.name}!", 'success')

        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('main.index'))

    return render_template('auth/admin_login.html')


@auth_bp.route('/admin/logout', methods=['GET', 'POST'])
def admin_logout():
    """
    Administrator logout endpoint. Clears session and redirects to admin login.
    """
    session.clear()
    flash("Administrator session ended.", 'info')
    return redirect(url_for('auth.admin_login'))
