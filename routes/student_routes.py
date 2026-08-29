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
from models.question_feedback import QuestionFeedback
from services.resume_parser import extract_skills_from_pdf, SKILL_LIBRARY
from services.conversation_engine import get_next_question
from services.practice_engine import get_practice_question
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
    Stats (Total Interviews, Average Score, Weak Topics) reflect ONLY full_interview sessions.
    Practice sessions are counted separately and displayed with their own card.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User profile not found. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    # --- Full interview stats (excludes practice) ---
    full_sessions = InterviewSession.get_full_interviews_by_user(user.id)
    evaluated_reports = [
        r for r in InterviewReport.get_all_by_user(user.id)
        if r.get('analysis_available') and r.get('overall_score') is not None
        and r.get('session_type', 'full_interview') != 'practice'
    ]
    # Fallback: filter via session join if session_type not in report dict
    if evaluated_reports and 'session_type' not in evaluated_reports[0]:
        full_session_ids = {s.id for s in full_sessions}
        evaluated_reports = [
            r for r in evaluated_reports
            if r.get('session_id') in full_session_ids
        ]
    avg_score = f"{round(sum(r['overall_score'] for r in evaluated_reports) / len(evaluated_reports))}%" if evaluated_reports else "N/A"

    # --- Weak topics from full interviews only ---
    weak_topics = QuestionFeedback.get_weak_topics_by_user(user.id, session_type='full_interview')

    # --- Practice session count for the Quick Practice card ---
    practice_sessions = InterviewSession.get_practice_sessions_by_user(user.id)

    metrics = {
        "total_interviews": len(full_sessions),
        "avg_score": avg_score,
        "has_resume": user.has_resume(),
        "resume_filename": user.resume_filename,
        "resume_uploaded_at": user.resume_uploaded_at,
        "resume_status": "Uploaded" if user.has_resume() else "Not Uploaded",
        "practice_session_count": len(practice_sessions),
    }

    show_tour = not bool(user.onboarding_completed)

    return render_template(
        'student/dashboard.html',
        user=user,
        metrics=metrics,
        weak_topics=weak_topics,
        show_tour=show_tour
    )


@student_bp.route('/complete-onboarding', methods=['POST'])
@login_required
def complete_onboarding():
    """
    Mark the student dashboard onboarding tour as completed.
    """
    user_id = session.get('student_id') or session.get('user_id')
    User.mark_onboarding_complete(user_id)
    return jsonify({"success": True, "message": "Onboarding completed successfully."}), 200


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


@student_bp.route('/how-it-works', methods=['GET'])
@login_required
def how_it_works():
    """
    Standalone 'How the AI Works' page.
    Displays the full technical architecture, scoring rubric, and system transparency notes.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User profile not found. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    return render_template('student/how_it_works.html', user=user)


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

        # Persist granular question-by-question feedback if extracted
        if analysis.get('question_breakdown'):
            try:
                QuestionFeedback.create_batch(session_id, analysis['question_breakdown'])
            except Exception as q_err:
                current_app.logger.warning(
                    f"[EndInterview] Failed saving question breakdown for session #{session_id}: {q_err}"
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
    Interview Results page (Modules 12, 13 & Question-Level Feedback).
    Displays the AI-generated performance analysis for a completed session,
    including score rings, confidence assessment, strengths, weaknesses,
    actionable improvement recommendations, rich Chart.js visual analytics,
    and granular question-by-question evaluation breakdown.
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

    # Load granular question-by-question feedback for this session
    question_feedback = QuestionFeedback.get_by_session(session_id)

    # Prepare chart payloads for Module 13
    current_chart_data = None
    progress_chart_data = []
    has_progress_history = False

    if report and report.analysis_available:
        current_chart_data = {
            "labels": ["Technical Score", "Communication Score", "Overall Score"],
            "scores": [report.technical_score, report.communication_score, report.overall_score]
        }

        # Retrieve all completed reports for this candidate to construct the trend line chart
        all_user_reports = InterviewReport.get_all_by_user(user.id)
        for idx, r in enumerate(all_user_reports, start=1):
            date_str = (r.get('report_created_at') or r.get('session_created_at') or '')[:10]
            progress_chart_data.append({
                "session_id": r['session_id'],
                "label": f"#{r['session_id']} {r['job_role']}",
                "short_label": f"#{r['session_id']}",
                "role": r['job_role'],
                "date": date_str,
                "overall_score": r['overall_score'],
                "technical_score": r['technical_score'],
                "communication_score": r['communication_score'],
                "is_current": (r['session_id'] == session_id)
            })

        has_progress_history = len(progress_chart_data) >= 2

    return render_template(
        'student/interview_results.html',
        user=user,
        interview_session=interview_session,
        report=report,
        question_feedback=question_feedback,
        current_chart_data=current_chart_data,
        progress_chart_data=progress_chart_data,
        has_progress_history=has_progress_history
    )


@student_bp.route('/weak-topics', methods=['GET'])
@login_required
def get_weak_topics():
    """
    API endpoint returning aggregated weak topics and historical mistakes for the candidate.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    weak_topics = QuestionFeedback.get_weak_topics_by_user(user.id)
    return jsonify({
        "success": True,
        "count": len(weak_topics),
        "weak_topics": weak_topics
    }), 200



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
# Interview History & Performance Log Routes (Module 14)
# ---------------------------------------------------------

@student_bp.route('/interviews/history', methods=['GET'])
@login_required
def interview_history():
    """
    Interview History view (Module 14).
    Displays two separated tabs:
      - Full Interviews: standard 4-stage AI mock sessions.
      - Practice Sessions: quick single-topic practice drills.
    Each tab has its own statistics and weak-topic aggregation.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User profile not found. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    # --- Full interview sessions with reports ---
    full_sessions_data = InterviewSession.get_sessions_with_reports_by_user(
        user.id, session_type='full_interview'
    )
    full_completed = sum(1 for s in full_sessions_data if s['status'] == 'completed')
    full_in_progress = sum(1 for s in full_sessions_data if s['status'] in ('in_progress', 'setup'))
    full_evaluated = [
        s for s in full_sessions_data
        if s['has_report'] and s['analysis_available'] and s['overall_score'] is not None
    ]
    full_avg_score = round(
        sum(s['overall_score'] for s in full_evaluated) / len(full_evaluated)
    ) if full_evaluated else None

    full_metrics = {
        "total_sessions": len(full_sessions_data),
        "completed_sessions": full_completed,
        "in_progress_sessions": full_in_progress,
        "avg_score": full_avg_score,
        "has_evaluated": len(full_evaluated) > 0
    }

    # --- Practice sessions with reports ---
    practice_sessions_data = InterviewSession.get_sessions_with_reports_by_user(
        user.id, session_type='practice'
    )
    practice_completed = sum(1 for s in practice_sessions_data if s['status'] == 'completed')
    practice_in_progress = sum(
        1 for s in practice_sessions_data if s['status'] in ('in_progress', 'setup')
    )
    practice_evaluated = [
        s for s in practice_sessions_data
        if s['has_report'] and s['analysis_available'] and s['overall_score'] is not None
    ]
    practice_avg_score = round(
        sum(s['overall_score'] for s in practice_evaluated) / len(practice_evaluated)
    ) if practice_evaluated else None

    practice_metrics = {
        "total_sessions": len(practice_sessions_data),
        "completed_sessions": practice_completed,
        "in_progress_sessions": practice_in_progress,
        "avg_score": practice_avg_score,
        "has_evaluated": len(practice_evaluated) > 0
    }

    # Practice weak topics (isolated — never merged with full interview topics)
    practice_weak_topics = QuestionFeedback.get_practice_weak_topics_by_user(user.id)

    # Determine which tab to show by default
    active_tab = request.args.get('tab', 'full')  # 'full' or 'practice'

    return render_template(
        'student/interview_history.html',
        user=user,
        full_sessions=full_sessions_data,
        full_metrics=full_metrics,
        practice_sessions=practice_sessions_data,
        practice_metrics=practice_metrics,
        practice_weak_topics=practice_weak_topics,
        active_tab=active_tab,
    )


# ---------------------------------------------------------
# Quick Practice Routes
# ---------------------------------------------------------

@student_bp.route('/practice/new', methods=['GET', 'POST'])
@login_required
def practice_setup():
    """
    Quick Practice Setup page.
    GET:  Render the topic picker form (resume skills + custom free-text).
    POST: Validate the topic, create a practice session, redirect to practice room.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)

    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    resume_skills = user.get_skills()  # pre-populated dropdown options

    if request.method == 'POST':
        topic_choice = request.form.get('topic', '').strip()
        custom_topic = request.form.get('custom_topic', '').strip()

        # Resolve the final topic string
        if topic_choice == '__custom__':
            resolved_topic = custom_topic
        else:
            resolved_topic = topic_choice

        errors = []
        if not resolved_topic:
            errors.append("Please select a topic or enter a custom one.")
        elif len(resolved_topic) > 80:
            errors.append("Topic must be 80 characters or fewer.")

        if errors:
            for msg in errors:
                flash(msg, "error")
            return render_template(
                'student/practice_setup.html',
                user=user,
                resume_skills=resume_skills,
                form_data=request.form
            ), 422

        # Create practice session (topic stored in job_role column)
        practice_session = InterviewSession.create_practice(
            user_id=user.id,
            topic=resolved_topic
        )

        flash(f"Practice session on \'{resolved_topic}\' started!", "success")
        return redirect(url_for('student.practice_room', session_id=practice_session.id))

    return render_template(
        'student/practice_setup.html',
        user=user,
        resume_skills=resume_skills,
        form_data={}
    )


@student_bp.route('/practice/<int:session_id>/room', methods=['GET'])
@login_required
def practice_room(session_id: int):
    """
    Quick Practice Room interface.
    Renders the practice chat UI for a single-topic focused session.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    practice_session = InterviewSession.get_by_id(session_id)
    if not practice_session:
        flash(f"Practice session #{session_id} not found.", "error")
        return redirect(url_for('student.dashboard'))

    if practice_session.user_id != user.id:
        flash("You do not have permission to access this practice session.", "error")
        return redirect(url_for('student.dashboard'))

    if practice_session.session_type != 'practice':
        flash("This is not a practice session.", "error")
        return redirect(url_for('student.interview_room', session_id=session_id))

    messages = InterviewMessage.get_by_session(session_id)

    return render_template(
        'student/practice_room.html',
        user=user,
        practice_session=practice_session,
        messages=messages,
        topic=practice_session.job_role
    )


@student_bp.route('/practice/<int:session_id>/chat', methods=['POST'])
@login_required
def practice_chat(session_id: int):
    """
    Practice Chat API endpoint.
    Dispatches to the practice conversation engine instead of the full-interview engine.
    Accepts JSON: {"answer": "candidate answer text"}
    Returns the same JSON shape as /interviews/<id>/chat for frontend compatibility.
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "Unauthorized session."}), 401

    practice_session = InterviewSession.get_by_id(session_id)
    if not practice_session:
        return jsonify({"success": False, "error": f"Practice session {session_id} not found."}), 404

    if practice_session.user_id != user.id:
        return jsonify({
            "success": False,
            "error": "Forbidden: You do not have permission to access this session."
        }), 403

    if practice_session.session_type != 'practice':
        return jsonify({"success": False, "error": "Not a practice session."}), 400

    data = request.get_json(silent=True) or {}
    student_answer = data.get('answer') if data.get('answer') is not None else request.form.get('answer')

    result = get_practice_question(session_id=session_id, student_answer=student_answer)
    status_code = 200 if result.get("success") or result.get("fallback_used") else 500
    return jsonify(result), status_code


@student_bp.route('/practice/<int:session_id>/end', methods=['POST'])
@login_required
def end_practice(session_id: int):
    """
    End an active practice session.
    Runs AI analysis on the practice transcript, saves the report,
    marks the session completed, and redirects to the interview results page
    (which is generic and renders correctly for both session types).
    """
    user_id = session.get('student_id') or session.get('user_id')
    user = User.get_by_id(user_id)
    if not user:
        flash("User session invalid. Please log in again.", "error")
        return redirect(url_for('auth.logout'))

    practice_session = InterviewSession.get_by_id(session_id)
    if not practice_session:
        flash(f"Practice session #{session_id} not found.", "error")
        return redirect(url_for('student.dashboard'))

    if practice_session.user_id != user.id:
        flash("You do not have permission to modify this session.", "error")
        return redirect(url_for('student.dashboard'))

    messages = InterviewMessage.get_by_session(session_id)

    # Reuse existing analysis service — it's topic-agnostic
    try:
        analysis = generate_interview_analysis(practice_session, messages)
    except Exception as exc:
        current_app.logger.error(
            f"[EndPractice] Unexpected error during analysis for session #{session_id}: {exc}"
        )
        analysis = None

    if analysis:
        from models.interview_report import InterviewReport
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
        if analysis.get('question_breakdown'):
            try:
                QuestionFeedback.create_batch(session_id, analysis['question_breakdown'])
            except Exception as q_err:
                current_app.logger.warning(
                    f"[EndPractice] Failed saving question breakdown for session #{session_id}: {q_err}"
                )
    else:
        from models.interview_report import InterviewReport
        InterviewReport.create_unavailable(session_id)

    practice_session.complete()
    return redirect(url_for('student.interview_results', session_id=session_id))

