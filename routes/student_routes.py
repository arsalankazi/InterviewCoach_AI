import os
from pathlib import Path
from flask import (
    Blueprint,
    render_template,
    request,
    session,
    redirect,
    url_for,
    flash,
    current_app,
    send_from_directory,
    jsonify
)
from werkzeug.utils import secure_filename
from models.user import User
from models.interview_session import InterviewSession
from models.interview_message import InterviewMessage
from models.interview_report import InterviewReport
from services.resume_parser import extract_skills_from_pdf, SKILL_LIBRARY
from services.conversation_engine import get_next_question
from services.analysis_service import generate_interview_analysis
from utils.decorators import login_required

student_bp = Blueprint('student', __name__, url_prefix='/student')

# Predefined job roles for the interview setup form.
# Used by both the POST validator and the template dropdown.
JOB_ROLES = [
    "Generative AI Engineer",
    "Prompt Engineer",
    "AI/ML Engineer",
    "Data Analyst",
    "Data Scientist",
    "Data Engineer",
    "Business Analyst",
    "Business Intelligence (BI) Developer",
    "Cloud Engineer",
    "Cloud Solutions Architect",
    "DevOps Engineer",
    "Site Reliability Engineer (SRE)",
    "Software Engineer",
    "Full Stack Developer",
    "Frontend Developer",
    "Backend Developer",
    "Mobile App Developer",
    "QA/Test Automation Engineer",
    "Cybersecurity Analyst",
    "Product Manager",
    "UI/UX Designer",
    "Digital Marketing Analyst",
    "HR Executive",
    "Finance Analyst",
    "Operations Executive",
    "Other",
]

MAX_RESUME_SIZE = 15 * 1024 * 1024  # 15 MB
ALLOWED_EXTENSIONS = {'pdf'}


def allowed_file(filename):
    """Verify if the uploaded file has an allowed PDF extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@student_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    """
    Student Dashboard view showing summary statistics, live resume status, and action cards.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User profile not found. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    # Dynamic metrics based on student data
    user_sessions = InterviewSession.get_by_user(user.id)
    metrics = {
        "total_interviews": len(user_sessions),
        "avg_score": "N/A",
        "has_resume": user.has_resume(),
        "resume_filename": user.resume_filename,
        "resume_uploaded_at": user.resume_uploaded_at,
        "resume_status": "Uploaded" if user.has_resume() else "Not Uploaded"
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
# Resume Upload & Management Routes (Module 6)
# ---------------------------------------------------------

@student_bp.route('/resume/upload', methods=['GET', 'POST'])
@login_required
def upload_resume():
    """
    Resume upload endpoint.
    GET: Displays the upload interface and current resume status.
    POST: Validates PDF format, enforces 15MB limit, replaces prior uploads, and stores the file.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        # Verify file presence in the request
        if 'resume' not in request.files:
            flash("No file part in the request.", "error")
            return render_template('student/resume_upload.html', user=user), 400

        file = request.files['resume']

        # Verify a file was actually selected
        if file.filename == '':
            flash("Please select a PDF resume file to upload.", "error")
            return render_template('student/resume_upload.html', user=user), 400

        # Validate file extension
        if not allowed_file(file.filename):
            flash("Invalid file type. Only PDF files (.pdf) are accepted.", "error")
            return render_template('student/resume_upload.html', user=user), 400

        # Validate file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size == 0:
            flash("The selected PDF file is empty.", "error")
            return render_template('student/resume_upload.html', user=user), 400

        if file_size > MAX_RESUME_SIZE:
            flash("File size exceeds the 15MB limit. Please upload a smaller PDF document.", "error")
            return render_template('student/resume_upload.html', user=user), 400

        upload_folder = current_app.config.get(
            'UPLOAD_FOLDER',
            str(Path(current_app.root_path) / 'static' / 'uploads' / 'resumes')
        )
        upload_dir = Path(upload_folder)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Remove previous resume file if it exists to avoid orphaned files
        if user.has_resume():
            user.delete_resume(upload_folder=upload_dir)

        # Unique, collision-free filename pattern
        stored_filename = f"user_{user.id}_resume.pdf"
        file_dest = upload_dir / stored_filename

        try:
            file.save(str(file_dest))
            user.update_resume(stored_filename)

            # ── Auto-extract skills from the uploaded PDF ─────────────────
            parse_result = extract_skills_from_pdf(str(file_dest))
            if parse_result['extraction_failed']:
                flash(
                    "Resume uploaded, but text could not be extracted "
                    "(possibly a scanned/image-only PDF). "
                    "You can add your skills manually.",
                    "warning"
                )
            elif not parse_result['skills']:
                user.save_skills([])
                flash(
                    "Resume uploaded successfully! No recognisable skills were "
                    "detected automatically — you can add them manually.",
                    "warning"
                )
            else:
                user.save_skills(parse_result['skills'])
                flash(
                    f"Resume uploaded! "
                    f"{len(parse_result['skills'])} skill(s) detected automatically.",
                    "success"
                )

            return redirect(url_for('student.dashboard'))
        except Exception as e:
            flash(f"Failed to save resume file: {str(e)}", "error")
            return render_template('student/resume_upload.html', user=user), 500

    return render_template('student/resume_upload.html', user=user)


# ---------------------------------------------------------
# Resume View / Download Route (Module 6)
# ---------------------------------------------------------

@student_bp.route('/resume/view', methods=['GET'])
@student_bp.route('/resume/download', methods=['GET'])
@login_required
def view_resume():
    """
    View or download the student's current uploaded resume PDF.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user or not user.has_resume():
        flash("No uploaded resume found. Please upload your resume first.", "warning")
        return redirect(url_for('student.upload_resume'))

    upload_folder = current_app.config.get(
        'UPLOAD_FOLDER',
        str(Path(current_app.root_path) / 'static' / 'uploads' / 'resumes')
    )

    return send_from_directory(
        upload_folder,
        user.resume_filename,
        mimetype='application/pdf',
        as_attachment=False
    )


# ---------------------------------------------------------
# Skills Management Routes (Module 7)
# ---------------------------------------------------------

@student_bp.route('/skills', methods=['GET'])
@login_required
def skills_manager():
    """
    Display the student's extracted skills and allow manual add/remove.
    GET: Renders the skills management page.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    current_skills = user.get_skills()
    # Build addable skills list: exclude what the user already has
    addable_skills = [s for s in SKILL_LIBRARY if s not in current_skills]

    return render_template(
        'student/skills.html',
        user=user,
        skills=current_skills,
        addable_skills=addable_skills
    )


@student_bp.route('/skills/update', methods=['POST'])
@login_required
def update_skills():
    """
    Handle add or remove skill actions from the skills management page.
    POST params:
        action     : 'add' | 'remove'
        skill      : skill name string
        custom_skill: free-text custom skill (used when action='add' and skill='__custom__')
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    action = request.form.get('action', '').strip()
    skill_value = request.form.get('skill', '').strip()
    custom_skill = request.form.get('custom_skill', '').strip()

    current_skills = user.get_skills()

    if action == 'remove':
        if skill_value in current_skills:
            current_skills.remove(skill_value)
            user.save_skills(current_skills)
            flash(f"'{skill_value}' removed from your skills.", "success")
        else:
            flash("Skill not found in your list.", "warning")

    elif action == 'add':
        # Determine the skill to add — dropdown selection or free-text input
        if skill_value == '__custom__':
            skill_to_add = custom_skill
        else:
            skill_to_add = skill_value

        if not skill_to_add:
            flash("Please select or type a skill to add.", "warning")
        elif skill_to_add in current_skills:
            flash(f"'{skill_to_add}' is already in your skills list.", "warning")
        elif len(skill_to_add) > 60:
            flash("Skill name is too long (max 60 characters).", "error")
        else:
            current_skills.append(skill_to_add)
            user.save_skills(current_skills)
            flash(f"'{skill_to_add}' added to your skills.", "success")
    else:
        flash("Unknown action.", "error")

    return redirect(url_for('student.skills_manager'))


# ---------------------------------------------------------
# Interview Setup Routes (Module 8)
# ---------------------------------------------------------

@student_bp.route('/interviews/new', methods=['GET', 'POST'])
@login_required
def interview_setup():
    """
    Interview Setup page.
    GET:  Render the setup form (gender selector, interviewer name, job role).
    POST: Validate inputs, persist a new interview session, redirect to dashboard
          with an informational flash (interview room built in Module 11).
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        gender = request.form.get('interviewer_gender', '').strip()
        name   = request.form.get('interviewer_name', '').strip()
        role   = request.form.get('job_role', '').strip()
        custom = request.form.get('custom_role', '').strip()

        errors = []

        # ── Validate gender ──────────────────────────────────────────────
        if gender not in ('male', 'female'):
            errors.append("Please select an interviewer (Male or Female).")

        # ── Validate interviewer name ────────────────────────────────────
        if not name:
            errors.append("Please enter a name for your interviewer.")
        elif len(name) > 50:
            errors.append("Interviewer name must be 50 characters or fewer.")

        # ── Validate job role ────────────────────────────────────────────
        if role == 'Other':
            if not custom:
                errors.append("Please specify your job role in the custom field.")
            elif len(custom) > 80:
                errors.append("Custom job role must be 80 characters or fewer.")
            else:
                resolved_role = custom
        elif role in JOB_ROLES:
            resolved_role = role
        else:
            errors.append("Please select a valid job role from the list.")
            resolved_role = ''

        if errors:
            for msg in errors:
                flash(msg, "error")
            return render_template(
                'student/interview_setup.html',
                user=user,
                job_roles=JOB_ROLES,
                form_data=request.form
            ), 422

        # ── Persist session ──────────────────────────────────────────────
        created_session = InterviewSession.create(
            user_id=user.id,
            interviewer_gender=gender,
            interviewer_name=name,
            job_role=resolved_role
        )

        flash(
            f"Interview session with {name} ({resolved_role}) configured! Welcome to your interview room.",
            "success"
        )
        return redirect(url_for('student.interview_room', session_id=created_session.id))

    # GET — render empty setup form
    return render_template(
        'student/interview_setup.html',
        user=user,
        job_roles=JOB_ROLES,
        form_data={}
    )


# ---------------------------------------------------------
# Virtual AI Interview Room Routes (Module 11)
# ---------------------------------------------------------

@student_bp.route('/interviews/<int:session_id>/room', methods=['GET'])
@login_required
def interview_room(session_id: int):
    """
    Virtual AI Interview Room interface (Module 11).
    Renders split-screen view with interviewer profile card and interactive chat stream.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    interview_session = InterviewSession.get_by_id(session_id)
    if not interview_session:
        flash(f"Interview session #{session_id} not found.", "error")
        return redirect(url_for('student.dashboard'))

    # Authorization check: verify session belongs to logged-in student
    if interview_session.user_id != user.id:
        flash("You do not have permission to access this interview session.", "error")
        return redirect(url_for('student.dashboard'))

    # Retrieve existing message turns for this session
    messages = InterviewMessage.get_by_session(session_id)

    return render_template(
        'student/interview_room.html',
        user=user,
        interview_session=interview_session,
        messages=messages
    )


@student_bp.route('/interviews/<int:session_id>/end', methods=['POST'])
@login_required
def end_interview(session_id: int):
    """
    End active interview session (Module 12).
    Triggers AI performance analysis via Gemini, saves the report to interview_reports,
    marks the session status='completed', and redirects to the results page.
    Gracefully handles Gemini API failures — still completes the session and
    shows an 'analysis unavailable' state on the results page.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    interview_session = InterviewSession.get_by_id(session_id)
    if not interview_session:
        flash(f"Interview session #{session_id} not found.", "error")
        return redirect(url_for('student.dashboard'))

    if interview_session.user_id != user.id:
        flash("You do not have permission to modify this interview session.", "error")
        return redirect(url_for('student.dashboard'))

    # Fetch full conversation history for analysis
    messages = InterviewMessage.get_by_session(session_id)

    # Attempt AI analysis — falls back gracefully if Gemini is unavailable
    try:
        analysis = generate_interview_analysis(interview_session, messages)
    except Exception as exc:
        current_app.logger.error(
            f"[EndInterview] Unexpected error during analysis for session #{session_id}: {exc}"
        )
        analysis = None

    # Persist the report regardless of whether analysis succeeded
    if analysis:
        InterviewReport.create(
            session_id=session_id,
            technical_score=analysis['technical_score'],
            communication_score=analysis['communication_score'],
            overall_score=analysis['overall_score'],
            confidence_level=analysis['confidence_level'],
            strengths=analysis['strengths'],
            weaknesses=analysis['weaknesses'],
            suggestions=analysis['suggestions'],
            analysis_available=True
        )
    else:
        InterviewReport.create_unavailable(session_id)

    # Always mark the session completed — analysis failures must not leave it stuck
    interview_session.complete()

    return redirect(url_for('student.interview_results', session_id=session_id))


@student_bp.route('/interviews/<int:session_id>/results', methods=['GET'])
@login_required
def interview_results(session_id: int):
    """
    Interview Results page (Module 12).
    Displays the AI-generated performance analysis for a completed session,
    including score indicators, confidence level, strengths, weaknesses,
    and actionable improvement suggestions.
    Shows a friendly 'analysis unavailable' state if the report could not be generated.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    interview_session = InterviewSession.get_by_id(session_id)
    if not interview_session:
        flash(f"Interview session #{session_id} not found.", "error")
        return redirect(url_for('student.dashboard'))

    if interview_session.user_id != user.id:
        flash("You do not have permission to view this report.", "error")
        return redirect(url_for('student.dashboard'))

    # Only completed sessions have results
    if interview_session.status != 'completed':
        flash("This interview session has not been completed yet.", "warning")
        return redirect(url_for('student.interview_room', session_id=session_id))

    # Load the report — may be None for legacy sessions completed before Module 12
    report = InterviewReport.get_by_session(session_id)

    return render_template(
        'student/interview_results.html',
        user=user,
        interview_session=interview_session,
        report=report
    )



# ---------------------------------------------------------
# AI Conversation Engine API Endpoints (Module 9)
# ---------------------------------------------------------

@student_bp.route('/interviews/<int:session_id>/chat', methods=['POST'])
@login_required
def interview_chat(session_id: int):
    """
    Backend Chat API endpoint for processing candidate answers and generating
    the next AI interviewer question turn (Module 9).
    Accepts JSON body: {"answer": "candidate answer text"}
    Returns JSON: {
        "success": bool,
        "ai_message": str,
        "sender": "ai",
        "session_id": int,
        "status": "in_progress",
        "message_count": int,
        "error": str | None
    }
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized session."}), 401

    interview_session = InterviewSession.get_by_id(session_id)
    if not interview_session:
        return jsonify({"success": False, "error": f"Interview session {session_id} not found."}), 404

    # Security check: ensure student owns this session
    if interview_session.user_id != user.id:
        return jsonify({
            "success": False,
            "error": "Forbidden: You do not have permission to access this session."
        }), 403

    # Extract answer text from JSON or form payload
    data = request.get_json(silent=True) or {}
    student_answer = data.get('answer') if data.get('answer') is not None else request.form.get('answer')

    # Dispatch to conversation engine
    result = get_next_question(session_id=session_id, student_answer=student_answer)

    status_code = 200 if result.get("success") or result.get("fallback_used") else 500
    return jsonify(result), status_code


@student_bp.route('/interviews/<int:session_id>/messages', methods=['GET'])
@login_required
def get_interview_messages(session_id: int):
    """
    Retrieve full multi-turn conversation history for an interview session.
    Returns JSON: {"success": True, "session_id": int, "messages": [...]}
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized session."}), 401

    interview_session = InterviewSession.get_by_id(session_id)
    if not interview_session:
        return jsonify({"success": False, "error": f"Interview session {session_id} not found."}), 404

    if interview_session.user_id != user.id:
        return jsonify({
            "success": False,
            "error": "Forbidden: You do not have permission to access this session."
        }), 403

    messages = InterviewMessage.get_by_session(session_id)
    return jsonify({
        "success": True,
        "session_id": session_id,
        "status": interview_session.status,
        "count": len(messages),
        "messages": [m.to_dict() for m in messages]
    }), 200


# ---------------------------------------------------------
# Action Link Placeholders (To be implemented in future modules)
# ---------------------------------------------------------

@student_bp.route('/interviews/history', methods=['GET'])
@login_required
def interview_history():
    """Placeholder endpoint for viewing past interview history."""
    flash("Interview history and scorecard analytics will be available in a future module!", "info")
    return redirect(url_for('student.dashboard'))
