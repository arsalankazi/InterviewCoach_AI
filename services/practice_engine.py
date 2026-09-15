"""
services/practice_engine.py

Practice Conversation Engine for PrepVance AI — Quick Practice Mode.

Key differences from conversation_engine.py (full interview):
  - No 4-stage progression — jumps directly to questions on the chosen topic.
  - No interviewer persona or greeting phase.
  - System prompt constrains the AI to the single selected topic only.
  - Difficulty level shapes question complexity: easy / medium / hard / adaptive.
  - Uses the same GeminiService multi-turn API for context-aware follow-ups.
  - Includes a focused fallback question bank per difficulty level.
"""

import logging
from models.interview_session import InterviewSession
from models.interview_message import InterviewMessage
from models.user import User
from services.gemini_service import gemini_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Practice fallback question pools — keyed by difficulty level.
# Each pool has 5+ variants to ensure variety even when Gemini is unavailable.
# ---------------------------------------------------------------------------

_FALLBACK_QUESTIONS: dict[str, list[str]] = {
    'easy': [
        "Can you tell me in simple words what {topic} is, and why developers use it?",
        "What does {topic} do? Give me a one-line answer in your own words.",
        "Can you name two or three basic things you can do with {topic}?",
        "Have you ever seen {topic} used in a project or tutorial? What was it doing?",
        "How would you explain {topic} to a classmate who has never heard of it?",
        "What is one simple example of {topic} in real life or in code?",
    ],
    'medium': [
        "Can you share a college project or assignment where you used {topic}?",
        "If your code using {topic} throws an error, how do you find and fix the bug?",
        "How would you use {topic} to solve a real problem in a project?",
        "What is something you find tricky when working with {topic}, and how do you handle it?",
        "If a teammate asks you to review their code that uses {topic}, what do you look for?",
        "What is one best practice you follow when writing code with {topic}?",
    ],
    'hard': [
        "What are the trade-offs between using {topic} and a simpler alternative?",
        "How would {topic} behave under very high load or with millions of records?",
        "Can you think of an edge case or a tricky situation where {topic} might fail or give wrong results?",
        "If you had to design a system that uses {topic} at scale, what problems would you watch out for?",
        "What are the performance or memory costs of using {topic}, and how do you reduce them?",
        "When is {topic} a bad choice? What would you use instead, and why?",
    ],
    'adaptive': [
        "Can you tell me in simple words what {topic} is, and why developers use it?",
        "Can you share a project where you used {topic}? What problem did it solve?",
        "What happens if you use {topic} in a situation it was not designed for?",
        "What are the trade-offs or downsides of using {topic}?",
        "How would {topic} perform under very high load or large datasets?",
        "Can you think of an edge case where {topic} might behave unexpectedly?",
    ],
}


def _difficulty_directive(difficulty_level: str) -> str:
    """
    Return the difficulty-specific instruction to inject into the system prompt.

    Args:
        difficulty_level: 'easy', 'medium', 'hard', or 'adaptive'.

    Returns:
        A multi-line directive string describing question style and complexity.
    """
    directives = {
        'easy': """DIFFICULTY LEVEL — EASY:
Ask basic, definition-level questions only.
- Use simple "What is X?", "What does X do?", or "Can you give an example of X?" phrasing.
- Avoid scenarios, trade-offs, or edge cases.
- Goal: test whether the student knows what the topic is and can describe it simply.
- Keep questions short — one sentence if possible.""",

        'medium': """DIFFICULTY LEVEL — MEDIUM:
Ask scenario-based and applied questions.
- Use "How would you use X to solve Y?" or "Imagine you are building a project with X — what steps would you take?"
- Test applied knowledge, not just definitions.
- Include a mix of conceptual, debugging, and practical usage questions.
- Avoid very deep trade-offs or system-design level questions.""",

        'hard': """DIFFICULTY LEVEL — HARD:
Ask challenging, deep-understanding questions.
- Include "What are the trade-offs of X?", "When would X fail?", and edge-case scenarios.
- Push the candidate to think about production realities, performance, and failure modes.
- Ask "why" and "what would go wrong" rather than just "what is" or "how do you use".
- These questions should make a student who only knows basics struggle.""",

        'adaptive': """DIFFICULTY LEVEL — ADAPTIVE:
Start with a medium-difficulty question.
After each candidate answer, internally assess their response:
- If the answer is strong, detailed, and correct → next question should be HARDER (trade-offs, edge cases, scale).
- If the answer is weak, vague, or missing key points → next question should be EASIER (definition, simple example).
- If the answer is okay but not exceptional → keep the same difficulty level.
Track the candidate's overall level internally and adjust each question accordingly.
Do NOT tell the candidate their level or mention that you are adjusting — just ask the next question naturally.""",
    }
    return directives.get(difficulty_level, directives['medium'])


def build_practice_prompt(topic: str, user: User, difficulty_level: str = 'medium') -> str:
    """
    Construct the system instruction for a focused single-topic practice session.

    The prompt explicitly:
      - Constrains the AI to the specified topic only.
      - Skips all greetings, introductions, and stage progressions.
      - Enforces strict simple English (max 15-20 words/sentence, friendly mentor tone).
      - Injects a difficulty-specific directive to shape question complexity.
      - Instructs the AI to ask exactly one question per turn.
      - Targets a concise ~5-minute drill of 4–6 quality questions.

    Args:
        topic:            The skill or subject the student has chosen to practice.
        user:             The User model instance (for skills context).
        difficulty_level: 'easy', 'medium', 'hard', or 'adaptive'.

    Returns:
        A complete system instruction string.
    """
    if difficulty_level not in ('easy', 'medium', 'hard', 'adaptive'):
        difficulty_level = 'medium'

    skills = user.get_skills() if user else []
    skills_str = ", ".join(skills) if skills else "General technical skills"
    candidate_name = user.name if user and user.name else "Candidate"

    plain_english_directive = """LANGUAGE & COMMUNICATION STYLE — STRICT REQUIREMENT:
Use SIMPLE, everyday English in all your questions — the kind a college student understands easily in a friendly chat.
Rules:
- Keep sentences SHORT (maximum 15 to 20 words each).
- Use common, simple words:
  * Say 'use', NOT 'leverage' or 'utilize'
  * Say 'show', NOT 'demonstrate'
  * Say 'make sure', NOT 'ensure'
  * Say 'help', NOT 'facilitate'
  * Say 'start', NOT 'initiate' or 'kick off'
  * Say 'fix', NOT 'mitigate' or 'remediate'
  * Say 'talk about' or 'tell me', NOT 'articulate' or 'elaborate'
- NO idioms, NO fancy metaphors, NO corporate buzzwords or academic jargon.
- Technical terms (like SQL, JOIN, Python, index, cache, API) are fine, but explain them simply or ask about them in plain words.
- Ask EXACTLY ONE question at a time. Never combine multiple sub-questions.
- Tone: Friendly, supportive senior college mentor who wants the student to learn and succeed."""

    difficulty_section = _difficulty_directive(difficulty_level)

    return f"""You are a friendly AI Practice Coach helping a college student practice "{topic}".

CANDIDATE CONTEXT:
- Candidate Name: {candidate_name}
- Chosen Practice Topic: "{topic}"
- Candidate's broader skill context: {skills_str}

COACH PERSONA & STYLE:
- You are a friendly, encouraging senior college mentor.
- You want {candidate_name} to feel confident and learn without feeling stressed or intimidated.

{plain_english_directive}

{difficulty_section}

SESSION RULES (non-negotiable):
1. Ask questions about "{topic}" ONLY. Do not deviate to unrelated topics.
2. Ask EXACTLY ONE question per turn — never ask two questions at once.
3. Do NOT greet the candidate, introduce yourself, or ask if they are ready.
   Go directly to a question on "{topic}" from your very first message.
4. Acknowledge the candidate's previous answer in 1 short, encouraging sentence, then ask the next question.
5. Keep each question SHORT and simple — 1 to 2 short sentences (max 15-20 words per sentence).
6. Target 4–6 questions total for this quick practice drill.
7. Stay strictly in character as the Practice Coach. Do not output meta explanations or stage labels.
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


def generate_practice_fallback(topic: str, student_msg_count: int, difficulty_level: str = 'medium') -> str:
    """
    Dynamic fallback question generator for practice sessions when Gemini is unavailable.
    Cycles through the difficulty-specific fallback question pool so students never see
    the same question twice within a session.

    Args:
        topic:             The practice topic selected by the student.
        student_msg_count: Number of student turns so far (0-indexed).
        difficulty_level:  'easy', 'medium', 'hard', or 'adaptive'.

    Returns:
        A fallback question string with {topic} substituted.
    """
    if difficulty_level not in _FALLBACK_QUESTIONS:
        difficulty_level = 'medium'
    pool = _FALLBACK_QUESTIONS[difficulty_level]
    idx = student_msg_count % len(pool)
    return pool[idx].format(topic=topic)


def get_practice_question(session_id: int, student_answer: str | None = None) -> dict:
    """
    Core practice conversation dispatcher.

    Workflow:
      1. Load and validate the practice session + candidate profile.
      2. Persist the student's answer turn if provided.
      3. Advance session status to 'in_progress' if still 'setup'.
      4. Build the topic-focused system prompt (with difficulty directive).
      5. Format multi-turn conversation history.
      6. Call GeminiService for the next question.
      7. Fall back to the difficulty-specific question bank if Gemini is unavailable.
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
    difficulty_level = getattr(session, 'difficulty_level', 'medium') or 'medium'
    total_questions = getattr(session, 'total_questions', 5) or 5

    # Check existing message history before accepting new student answer
    existing_messages = InterviewMessage.get_by_session(session.id)
    prev_student_msg_count = sum(1 for m in existing_messages if m.sender == 'student')

    # Guard: if session is completed OR already reached total_questions, reject further messages without calling Gemini
    if session.status == 'completed' or prev_student_msg_count >= total_questions:
        print(f"[PracticeEngine] Session #{session.id} has concluded ({prev_student_msg_count}/{total_questions} answers). Returning wrap-up without calling Gemini.")
        return {
            "success": True,
            "ai_message": f"This practice drill on {topic} has ended. Generating your feedback report...",
            "sender": "ai",
            "message_id": None,
            "session_id": session.id,
            "status": session.status,
            "session_type": "practice",
            "topic": topic,
            "difficulty_level": difficulty_level,
            "current_question_number": total_questions,
            "total_questions": total_questions,
            "is_wrap_up": True,
            "message_count": len(existing_messages),
            "fallback_used": False,
            "error": None
        }

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

    # Re-fetch full message history
    existing_messages = InterviewMessage.get_by_session(session.id)
    student_msg_count = sum(1 for m in existing_messages if m.sender == 'student')
    is_wrap_up = (student_msg_count >= total_questions)
    current_question_number = total_questions if is_wrap_up else (student_msg_count + 1)

    print(f"\n[PracticeEngine] === DISPATCHING PRACTICE TURN FOR SESSION #{session.id} ===")
    print(f"[PracticeEngine] Candidate: {user.name} | Topic: {topic} | Difficulty: {difficulty_level}")
    print(f"[PracticeEngine] Progress: Q{current_question_number}/{total_questions} | Wrap-Up Active: {is_wrap_up}")
    print(f"[PracticeEngine] Student Turns: {student_msg_count}")
    if cleaned_answer:
        print(f"[PracticeEngine] Candidate Input: \"{cleaned_answer}\"")

    # Format history for Gemini
    if cleaned_answer and existing_messages:
        prior_messages = existing_messages[:-1]
        history_for_gemini = format_practice_history(prior_messages)
        user_message_for_gemini = cleaned_answer
    else:
        history_for_gemini = format_practice_history(existing_messages)
        user_message_for_gemini = None

    if is_wrap_up:
        # Wrap-up prompt: acknowledge last answer and conclude
        system_instruction = (
            f"You are a friendly AI Practice Coach helping a college student practice '{topic}'. "
            f"The practice drill has concluded. The candidate just provided their final answer. "
            f"Acknowledge the candidate's final response naturally in 1 short, encouraging sentence (maximum 15 words). "
            f"Then deliver the exact wrap-up conclusion: "
            f"'That brings us to the end of our practice drill on {topic}. Let\\'s generate your feedback report!' "
            f"Do NOT ask any more questions."
        )
        wrap_up_fallback = f"Great effort on that question! That brings us to the end of our practice drill on {topic}. Let's see your feedback report!"
    else:
        # Build standard practice system prompt (difficulty-aware)
        system_instruction = build_practice_prompt(topic, user, difficulty_level)
        wrap_up_fallback = None

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
        if is_wrap_up:
            ai_response_text = wrap_up_fallback
        else:
            ai_response_text = generate_practice_fallback(topic, student_msg_count, difficulty_level)
        is_fallback = True
        print(f"[PracticeEngine] Gemini unavailable ({result_text}). Using fallback: \"{ai_response_text}\"")

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
        "difficulty_level": difficulty_level,
        "current_question_number": current_question_number,
        "total_questions": total_questions,
        "is_wrap_up": is_wrap_up,
        "message_count": total_count,
        "fallback_used": is_fallback,
        "error": None if not is_fallback else result_text
    }
