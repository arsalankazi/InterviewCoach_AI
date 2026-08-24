"""
services/conversation_engine.py

Conversation Engine for InterviewCoach AI.
Orchestrates interview state, system prompt generation, 4-stage interview progression,
message persistence, and AI response generation via GeminiService (with intelligent stage progression fallback).
"""

import logging
import random
from models.interview_session import InterviewSession
from models.interview_message import InterviewMessage
from models.user import User
from services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 Greeting Variants — randomised so each session opens differently.
# Placeholders: {interviewer_name}, {candidate_name}, {job_role}
# ─────────────────────────────────────────────────────────────────────────────
GREETING_VARIANTS = [
    # 1. Classic warm welcome
    (
        "Hello {candidate_name}, welcome! I'm {interviewer_name}, your interviewer today "
        "for the {job_role} position. It's great to have you here — are you comfortable "
        "and ready to get started?"
    ),
    # 2. Energetic, role-focused opener
    (
        "Hi {candidate_name}! I'm {interviewer_name}. We have an exciting session ahead "
        "exploring your fit for the {job_role} role. Before we dive in, I just want to "
        "check — are you all set and ready to begin?"
    ),
    # 3. Professional / formal
    (
        "Good day, {candidate_name}. I'm {interviewer_name}, conducting today's interview "
        "for the {job_role} position. I appreciate you taking the time. "
        "Are you comfortable and ready to proceed?"
    ),
    # 4. Conversational / relaxed
    (
        "Hey {candidate_name}, glad you could join! I'm {interviewer_name}. "
        "We'll be having a conversation today around the {job_role} role — "
        "nothing too formal, just a focused discussion. Ready to kick things off?"
    ),
    # 5. Context-leading opener
    (
        "Welcome, {candidate_name}. I'm {interviewer_name}, and I'll be walking you "
        "through today's interview for the {job_role} position. "
        "Let's make this a productive session — shall we begin?"
    ),
]


def determine_interview_stage(messages: list) -> tuple[int, str]:
    """
    Determine the current active interview stage based on how many student answer
    turns have occurred in the dialogue history.

    Returns:
        tuple[int, str]: (stage_number, stage_description)
    """
    student_msg_count = sum(1 for m in messages if getattr(m, 'sender', None) == 'student')

    if student_msg_count == 0:
        return 1, "Stage 1 (Greeting & Readiness Check)"
    elif student_msg_count == 1:
        return 2, "Stage 2 (Candidate Introduction & Background)"
    elif student_msg_count == 2:
        return 3, "Stage 3 (Core Technical & Conceptual Competency)"
    elif student_msg_count == 3:
        return 3, "Stage 3 (Practical Implementation & Applied Architecture)"
    elif student_msg_count == 4:
        return 4, "Stage 4 (Adaptive Follow-up & Scenario Deep Dive)"
    else:
        return 4, "Stage 4 (System Trade-offs, Edge Cases & Synthesis)"


def build_system_prompt(session: InterviewSession, user: User, current_stage_num: int, current_stage_desc: str) -> str:
    """
    Construct the tailored system instruction for the AI interviewer.
    Incorporates interviewer persona, custom name, target job role,
    the candidate's extracted resume skills, and active stage directive.
    """
    interviewer_name = session.interviewer_name if session.interviewer_name else "Alex Walker"
    gender = (session.interviewer_gender or "male").lower()
    job_role = session.job_role if session.job_role else "Software Engineer"
    skills = user.get_skills() if user else []
    skills_str = ", ".join(skills) if skills else "General technical, analytical & problem-solving skills"
    candidate_name = user.name if user and user.name else "Candidate"

    if gender == 'female':
        tone_description = (
            "perceptive, scenario-driven, and insightful. "
            "You focus on practical system trade-offs, clear communication, and contextual problem-solving."
        )
    else:
        tone_description = (
            "direct, analytical, and structured. "
            "You focus on core engineering principles, logical reasoning, and precision."
        )

    system_instruction = f"""You are {interviewer_name}, an expert AI Technical Interviewer conducting a realistic mock interview for the position of "{job_role}".

CANDIDATE CONTEXT:
- Candidate Name: {candidate_name}
- Target Job Role: {job_role}
- Candidate Extracted Skills: {skills_str}

INTERVIEWER PERSONA & TONE:
- Name: {interviewer_name}
- Style: {tone_description}

CURRENT ACTIVE INTERVIEW STAGE:
- Stage {current_stage_num}: {current_stage_desc}

4-STAGE INTERVIEW FLOW & PROGRESSION:
1. Stage 1 (Readiness & Greeting):
   - Welcome {candidate_name} naturally and warmly — vary your phrasing each session, do not use a fixed script.
   - Introduce yourself briefly as {interviewer_name} and mention the {job_role} role.
   - Close with a friendly readiness check (e.g., 'Are you ready to begin?' or 'Shall we get started?').
2. Stage 2 (Candidate Introduction):
   - Once the candidate confirms readiness, invite them to introduce themselves, share their background, and explain what excites them about the {job_role} role.
3. Stage 3 (Core Role & Technical Questions):
   - Ask questions directly relevant to {job_role} and their skill stack ({skills_str}).
   - Explore both conceptual depth and practical application.
4. Stage 4 (Adaptive Follow-ups & Scenario Deep-Dive):
   - Critically evaluate the candidate's previous response.
   - Ask adaptive follow-up questions challenging assumptions, exploring edge cases, system bottlenecks, or trade-offs.

CRITICAL INSTRUCTIONS FOR THIS TURN:
- You must advance the conversation into {current_stage_desc}.
- Ask EXACTLY ONE question at a time. Never ask multiple questions in a single turn.
- Keep your turn concise and conversational (1 to 3 sentences maximum), matching a realistic video/voice interview dialogue.
- Acknowledge what the candidate said naturally before asking your question.
- Stay strictly in character as {interviewer_name} at all times. Do not output meta explanations.
"""
    return system_instruction.strip()


def format_gemini_history(messages: list) -> list[dict]:
    """
    Format stored database message turns into dictionary structure
    expected by GeminiService.
    'student' -> role 'user'
    'ai'      -> role 'model'
    """
    history = []
    for msg in messages:
        role = "user" if getattr(msg, 'sender', None) == "student" else "model"
        text = getattr(msg, 'message_text', '')
        if text:
            history.append({
                "role": role,
                "parts": [text]
            })
    return history


def generate_stage_progression_fallback(
    session: InterviewSession,
    user: User,
    stage_num: int,
    student_answer: str | None,
    student_msg_count: int
) -> str:
    """
    Dynamic stage-aware response generator used when the Gemini API key is not configured
    or during API outages. Ensures the mock interview smoothly advances through all 4 stages
    with varied, role-specific questions rather than repeating a static string.
    """
    interviewer_name = session.interviewer_name or "Alex Walker"
    candidate_name = user.name or "Candidate"
    job_role = session.job_role or "Software Engineer"
    skills = user.get_skills() if user else []
    primary_skill = skills[0] if skills else "modern architecture"
    secondary_skill = skills[1] if len(skills) > 1 else "clean code practices"

    if student_msg_count == 0:
        # Stage 1: Greeting & Readiness — randomise across 5 variants
        template = random.choice(GREETING_VARIANTS)
        return template.format(
            interviewer_name=interviewer_name,
            candidate_name=candidate_name,
            job_role=job_role
        )
    elif student_msg_count == 1:
        # Stage 2: Candidate Introduction
        return (
            f"Glad to hear that, {candidate_name}. To get started, could you briefly introduce yourself, "
            f"highlight your core technical background, and share what interests you most about this {job_role} role?"
        )
    elif student_msg_count == 2:
        # Stage 3 Turn 1: Core Technical Competency
        return (
            f"Thank you for sharing your background. Given your target role as a {job_role}, could you walk me through "
            f"how you typically leverage {primary_skill} when designing robust, scalable solutions?"
        )
    elif student_msg_count == 3:
        # Stage 3 Turn 2: Applied Implementation / Architecture
        return (
            f"That's a very clear approach. In a production environment involving {secondary_skill}, how do you ensure "
            "reliability, error resilience, and high performance under high concurrency or data volume?"
        )
    elif student_msg_count == 4:
        # Stage 4 Turn 1: Adaptive Scenario & Edge Case Deep-Dive
        return (
            f"Let's explore a scenario: Suppose your system experiences unexpected latency spikes and partial component failure in production. "
            "What diagnostic steps and trade-offs would you make to mitigate the impact quickly?"
        )
    else:
        # Stage 4 Turn 2+: Wrap-up and Reflection
        return (
            f"Excellent analysis. We've covered your background, core technical fundamentals, and system design approach for the {job_role} position. "
            "Do you have any final thoughts on your approach, or are you ready to wrap up the session?"
        )


def get_next_question(session_id: int, student_answer: str | None = None) -> dict:
    """
    Core conversational engine dispatcher.
    1. Validates the session and candidate profile.
    2. If a student_answer is provided, persists the student turn.
    3. Calculates current interview stage (1 to 4).
    4. Formats multi-turn history.
    5. Advances session status to 'in_progress'.
    6. Calls GeminiService to generate the interviewer's next response.
    7. If Gemini is unavailable, uses the intelligent stage-progression engine.
    8. Persists the AI response and returns structured response dict.
    """
    session = InterviewSession.get_by_id(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Interview session with ID {session_id} not found.",
            "ai_message": None,
            "session_id": session_id,
            "status": "error",
            "message_count": 0
        }

    user = User.get_by_id(session.user_id)
    if not user:
        return {
            "success": False,
            "error": "Associated student profile not found.",
            "ai_message": None,
            "session_id": session_id,
            "status": "error",
            "message_count": 0
        }

    # If student provided an answer, save their message turn
    cleaned_answer = student_answer.strip() if (student_answer and student_answer.strip()) else None
    if cleaned_answer:
        InterviewMessage.create(
            session_id=session.id,
            sender='student',
            message_text=cleaned_answer
        )

    # Transition session status from 'setup' to 'in_progress'
    if session.status == 'setup':
        session.update_status('in_progress')

    # Load complete message history for this session
    existing_messages = InterviewMessage.get_by_session(session.id)
    student_msg_count = sum(1 for m in existing_messages if m.sender == 'student')

    # Determine stage
    stage_num, stage_desc = determine_interview_stage(existing_messages)

    print(f"\n[ConversationEngine] === DISPATCHING TURN FOR SESSION #{session.id} ===")
    print(f"[ConversationEngine] Candidate: {user.name} | Target Role: {session.job_role}")
    print(f"[ConversationEngine] Student Turns Recorded: {student_msg_count} | Active Stage: {stage_num} ({stage_desc})")
    if cleaned_answer:
        print(f"[ConversationEngine] Candidate Input Text: \"{cleaned_answer}\"")

    # Build stage-aware system prompt
    system_instruction = build_system_prompt(session, user, stage_num, stage_desc)

    # Prepare historical context for Gemini
    if cleaned_answer and existing_messages:
        prior_messages = existing_messages[:-1]
        history_for_gemini = format_gemini_history(prior_messages)
        user_message_for_gemini = cleaned_answer
    else:
        history_for_gemini = format_gemini_history(existing_messages)
        user_message_for_gemini = None

    # Call Gemini API
    print(f"[ConversationEngine] Calling GeminiService (Model preference: {gemini_service.model_name})...")
    success, result_text = gemini_service.generate_interview_response(
        system_instruction=system_instruction,
        history=history_for_gemini,
        user_message=user_message_for_gemini
    )

    if success and result_text:
        ai_response_text = result_text
        is_fallback = False
        print(f"[ConversationEngine] Result: SUCCESS from real Gemini AI ({gemini_service.model_name})")
        print(f"[ConversationEngine] AI Output -> \"{ai_response_text}\"")
    else:
        print(f"[ConversationEngine] Result: Gemini unavailable or call failed. (Details: {result_text})")
        print("[ConversationEngine] Action: Engaging Stage Progression Fallback Engine.")
        ai_response_text = generate_stage_progression_fallback(
            session=session,
            user=user,
            stage_num=stage_num,
            student_answer=cleaned_answer,
            student_msg_count=student_msg_count
        )
        is_fallback = True
        print(f"[ConversationEngine] Fallback Output -> \"{ai_response_text}\"")


    # Persist AI question/response turn to database
    ai_msg_record = InterviewMessage.create(
        session_id=session.id,
        sender='ai',
        message_text=ai_response_text
    )

    total_count = InterviewMessage.get_count_by_session(session.id)
    return {
        "success": True,
        "ai_message": ai_response_text,
        "sender": "ai",
        "message_id": ai_msg_record.id,
        "session_id": session.id,
        "status": session.status,
        "stage": stage_num,
        "stage_name": stage_desc,
        "message_count": total_count,
        "fallback_used": is_fallback,
        "error": None if not is_fallback else result_text
    }

