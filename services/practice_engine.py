"""
services/practice_engine.py

Practice Conversation Engine for InterviewCoach AI — Quick Practice Mode.

Key differences from conversation_engine.py (full interview):
  - No 4-stage progression — jumps directly to questions on the chosen topic.
  - No interviewer persona or greeting phase.
  - System prompt constrains the AI to the single selected topic only.
  - Uses the same GeminiService multi-turn API for context-aware follow-ups.
  - Includes a focused fallback question bank per topic if Gemini is unavailable.
"""

import logging
from models.interview_session import InterviewSession
from models.interview_message import InterviewMessage
from models.user import User
from services.gemini_service import gemini_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Practice fallback question pool — topic-agnostic progressive questions
# used when Gemini is unavailable.
# ---------------------------------------------------------------------------
_FALLBACK_QUESTIONS = [
    "Can you explain the core concept behind {topic} and why it matters in a production context?",
    "Walk me through a time you applied {topic} to solve a real engineering or technical challenge.",
    "What are the key trade-offs or limitations you've encountered when using {topic}?",
    "How would you debug or troubleshoot a failure related to {topic} in a live system?",
    "Compare {topic} to an alternative approach — when would you choose one over the other?",
    "How does {topic} scale under high load or large data volumes? What would you optimize first?",
]


def build_practice_prompt(topic: str, user: User) -> str:
    """
    Construct the system instruction for a focused single-topic practice session.

    The prompt explicitly:
      - Constrains the AI to the specified topic only.
      - Skips all greetings, introductions, and stage progressions.
      - Instructs the AI to ask exactly one question per turn.
      - Targets a concise ~5-minute drill of 4–6 quality questions.

    Args:
        topic: The skill or subject the student has chosen to practice.
        user:  The User model instance (for skills context).

    Returns:
        A complete system instruction string.
    """
    skills = user.get_skills() if user else []
    skills_str = ", ".join(skills) if skills else "General technical skills"
    candidate_name = user.name if user and user.name else "Candidate"

    return f"""You are an AI Practice Coach specialising in technical interview preparation.

PRACTICE SESSION CONFIGURATION:
- Candidate Name: {candidate_name}
- Chosen Practice Topic: "{topic}"
- Candidate's broader skill context: {skills_str}

SESSION RULES (non-negotiable):
1. Ask questions about "{topic}" ONLY. Do not deviate to unrelated topics.
2. Ask EXACTLY ONE question per turn — never multiple.
3. Do NOT greet the candidate, introduce yourself, or ask if they are ready.
   Go directly to a technical question on "{topic}" from your very first message.
4. Vary question types across the session:
   - Conceptual (what/why/how it works)
   - Applied (real-world usage, architecture decisions)
   - Debugging / troubleshooting scenarios
   - Trade-off and comparative analysis
5. Acknowledge the candidate's previous answer naturally in 1 sentence, then ask the next question.
6. Keep each question concise — 1 to 3 sentences maximum.
7. Target 4–6 high-quality questions total. This is a focused ~5-minute drill, not a full interview.
8. Stay strictly in character as the Practice Coach. Do not output meta-commentary or stage labels.
""".strip()


def format_practice_history(messages: list) -> list[dict]:
    """
    Format stored practice session messages for GeminiService.
    Identical mapping to conversation_engine.format_gemini_history().
    """
    history = []
    for msg in messages:
        role = "user" if getattr(msg, 'sender', None) == "student" else "model"
        text = getattr(msg, 'message_text', '')
        if text:
            history.append({"role": role, "parts": [text]})
    return history


def generate_practice_fallback(topic: str, student_msg_count: int) -> str:
    """
    Dynamic fallback question generator for practice sessions when Gemini is unavailable.
    Cycles through the fallback question pool so students never see the same question twice
    within a session.

    Args:
        topic:             The practice topic selected by the student.
        student_msg_count: Number of student turns so far (0-indexed).

    Returns:
        A fallback question string with {topic} substituted.
    """
    idx = student_msg_count % len(_FALLBACK_QUESTIONS)
    return _FALLBACK_QUESTIONS[idx].format(topic=topic)


def get_practice_question(session_id: int, student_answer: str | None = None) -> dict:
    """
    Core practice conversation dispatcher.

    Workflow:
      1. Load and validate the practice session + candidate profile.
      2. Persist the student's answer turn if provided.
      3. Advance session status to 'in_progress' if still 'setup'.
      4. Build the topic-focused system prompt.
      5. Format multi-turn conversation history.
      6. Call GeminiService for the next question.
      7. Fall back to the topic-question bank if Gemini is unavailable.
      8. Persist the AI question turn and return the structured response dict.

    Returns the same dict shape as conversation_engine.get_next_question() so the
    existing interview_room JavaScript and API consumers work without modification.
    """
    session = InterviewSession.get_by_id(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Practice session with ID {session_id} not found.",
            "ai_message": None,
            "session_id": session_id,
            "status": "error",
            "message_count": 0
        }

    if session.session_type != 'practice':
        return {
            "success": False,
            "error": f"Session {session_id} is not a practice session.",
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

    topic = session.job_role  # topic is stored in job_role for practice sessions

    # Persist student answer if provided
    cleaned_answer = student_answer.strip() if (student_answer and student_answer.strip()) else None
    if cleaned_answer:
        InterviewMessage.create(
            session_id=session.id,
            sender='student',
            message_text=cleaned_answer
        )

    # Transition to in_progress
    if session.status == 'setup':
        session.update_status('in_progress')

    # Load full message history
    existing_messages = InterviewMessage.get_by_session(session.id)
    student_msg_count = sum(1 for m in existing_messages if m.sender == 'student')

    print(f"\n[PracticeEngine] === DISPATCHING PRACTICE TURN FOR SESSION #{session.id} ===")
    print(f"[PracticeEngine] Candidate: {user.name} | Topic: {topic}")
    print(f"[PracticeEngine] Student Turns: {student_msg_count}")
    if cleaned_answer:
        print(f"[PracticeEngine] Candidate Input: \"{cleaned_answer}\"")

    # Build practice system prompt
    system_instruction = build_practice_prompt(topic, user)

    # Format history for Gemini
    if cleaned_answer and existing_messages:
        prior_messages = existing_messages[:-1]
        history_for_gemini = format_practice_history(prior_messages)
        user_message_for_gemini = cleaned_answer
    else:
        history_for_gemini = format_practice_history(existing_messages)
        user_message_for_gemini = None

    # Call Gemini API
    print(f"[PracticeEngine] Calling GeminiService (model: {gemini_service.model_name})...")
    success, result_text = gemini_service.generate_interview_response(
        system_instruction=system_instruction,
        history=history_for_gemini,
        user_message=user_message_for_gemini
    )

    if success and result_text:
        ai_response_text = result_text
        is_fallback = False
        print(f"[PracticeEngine] Result: SUCCESS from Gemini AI")
        print(f"[PracticeEngine] AI Output -> \"{ai_response_text}\"")
    else:
        print(f"[PracticeEngine] Gemini unavailable ({result_text}). Using fallback.")
        ai_response_text = generate_practice_fallback(topic, student_msg_count)
        is_fallback = True
        print(f"[PracticeEngine] Fallback Output -> \"{ai_response_text}\"")

    # Persist AI response
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
        "session_type": "practice",
        "topic": topic,
        "message_count": total_count,
        "fallback_used": is_fallback,
        "error": None if not is_fallback else result_text
    }
