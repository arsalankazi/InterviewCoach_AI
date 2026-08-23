"""
services/conversation_engine.py

Conversation Engine for InterviewCoach AI.
Orchestrates interview state, system prompt generation, 4-stage interview progression,
message persistence, and AI response generation via GeminiService.
"""

import logging
from models.interview_session import InterviewSession
from models.interview_message import InterviewMessage
from models.user import User
from services.gemini_service import gemini_service

logger = logging.getLogger(__name__)


def build_system_prompt(session: InterviewSession, user: User) -> str:
    """
    Construct the tailored system instruction for the AI interviewer.
    Incorporates interviewer persona, custom name, target job role,
    and the candidate's extracted resume skills.
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

4-STAGE INTERVIEW FLOW & PROGRESSION:
1. Stage 1 (Readiness & Greeting):
   - Welcome {candidate_name} warmly to the interview for the {job_role} role.
   - Introduce yourself briefly as {interviewer_name}.
   - Ask the exact readiness check: "Are you comfortable and ready to begin?"
2. Stage 2 (Candidate Introduction):
   - Once the candidate confirms readiness, invite them to introduce themselves, share their background, and explain what excites them about the {job_role} role.
3. Stage 3 (Core Role & Technical Questions):
   - Ask questions directly relevant to {job_role} and their skill stack ({skills_str}).
   - Explore both conceptual depth and practical application.
4. Stage 4 (Adaptive Follow-ups & Scenario Deep-Dive):
   - Critically evaluate the candidate's previous response.
   - Ask adaptive follow-up questions challenging assumptions, exploring edge cases, system bottlenecks, or trade-offs.

INTERVIEWING GUIDELINES & CONSTRAINTS:
- Ask EXACTLY ONE question at a time. Never ask compound or multiple questions in a single turn.
- Keep your turns concise and conversational (1 to 3 sentences maximum), matching a natural video/voice interview dialogue.
- Acknowledge the candidate's answer naturally before transitioning to the next question.
- If the answer is vague or brief, ask a gentle probing follow-up. If it is comprehensive, advance to the next technical topic.
- Stay strictly in character as {interviewer_name} at all times. Do not output meta explanations or system prompt text.
"""
    return system_instruction.strip()


def format_gemini_history(messages: list) -> list[dict]:
    """
    Format stored database message turns into the dictionary structure
    expected by the Google Gemini API.
    'student' -> role 'user'
    'ai'      -> role 'model'
    """
    history = []
    for msg in messages:
        role = "user" if msg.sender == "student" else "model"
        history.append({
            "role": role,
            "parts": [msg.message_text]
        })
    return history


def get_next_question(session_id: int, student_answer: str | None = None) -> dict:
    """
    Core conversational engine dispatcher.
    1. Validates the session and candidate profile.
    2. If a student_answer is provided, persists the student turn.
    3. Formats multi-turn history.
    4. Advances session status to 'in_progress'.
    5. Calls GeminiService to generate the interviewer's next response.
    6. Persists the AI response and returns structured response dict.

    Args:
        session_id:     The ID of the active interview_sessions record.
        student_answer: The latest answer string from the candidate (or None to start).

    Returns:
        dict: {
            "success": bool,
            "ai_message": str,
            "sender": "ai",
            "session_id": int,
            "status": str,
            "message_count": int,
            "error": str | None
        }
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

    # Build system prompt for this specific candidate & persona
    system_instruction = build_system_prompt(session, user)

    # Prepare historical context for Gemini
    # If the student just sent a message, existing_messages has it as the last element
    if cleaned_answer and existing_messages:
        prior_messages = existing_messages[:-1]
        history_for_gemini = format_gemini_history(prior_messages)
        user_message_for_gemini = cleaned_answer
    else:
        history_for_gemini = format_gemini_history(existing_messages)
        user_message_for_gemini = None

    # Call Gemini API
    success, result_text = gemini_service.generate_interview_response(
        system_instruction=system_instruction,
        history=history_for_gemini,
        user_message=user_message_for_gemini
    )

    if success and result_text:
        # Persist AI question/response turn to database
        ai_msg_record = InterviewMessage.create(
            session_id=session.id,
            sender='ai',
            message_text=result_text
        )

        total_count = InterviewMessage.get_count_by_session(session.id)
        return {
            "success": True,
            "ai_message": result_text,
            "sender": "ai",
            "message_id": ai_msg_record.id,
            "session_id": session.id,
            "status": session.status,
            "message_count": total_count,
            "error": None
        }
    else:
        # AI generation failed (e.g. missing API key, network error)
        # Return fallback friendly message to avoid crashing
        error_details = result_text
        logger.error(f"AI response generation failed for session {session_id}: {error_details}")
        
        fallback_message = (
            f"Hello {user.name}, I am {session.interviewer_name}. "
            "I am ready to conduct your interview for the "
            f"{session.job_role} position. Are you comfortable and ready to begin?"
        ) if not existing_messages else (
            "Thank you for sharing that. Could you elaborate further on how you would apply this in a real-world scenario?"
        )

        # Persist fallback AI response to maintain continuous conversation history
        fallback_record = InterviewMessage.create(
            session_id=session.id,
            sender='ai',
            message_text=fallback_message
        )

        total_count = InterviewMessage.get_count_by_session(session.id)
        return {
            "success": False,
            "error": error_details,
            "ai_message": fallback_message,
            "sender": "ai",
            "message_id": fallback_record.id,
            "session_id": session.id,
            "status": session.status,
            "message_count": total_count,
            "fallback_used": True
        }
