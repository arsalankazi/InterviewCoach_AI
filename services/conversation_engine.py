"""
services/conversation_engine.py

Conversation Engine for PrepVance AI.
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


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 Introduction Question Variants — 10 distinct phrasings.
# All convey the same intent: introduce yourself, background, motivation.
# Placeholders: {interviewer_name}, {candidate_name}, {job_role}
# Seeded by session_id to be deterministic per session but vary across sessions.
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 Introduction Question Variants — 10 distinct phrasings.
# Simple, conversational, student-friendly opening requests with NO preambles.
# Placeholders: {interviewer_name}, {candidate_name}, {job_role}
# Seeded by session_id to be deterministic per session but vary across sessions.
# ─────────────────────────────────────────────────────────────────────────────
INTRODUCTION_VARIANTS = [
    # 1
    (
        "Tell me about yourself. What did you study in college, and why do you want this {job_role} job?"
    ),
    # 2
    (
        "Please introduce yourself. What projects have you built so far that fit this {job_role} role?"
    ),
    # 3
    (
        "Could you share a bit about your background, what you enjoy working on, and why you chose {job_role}?"
    ),
    # 4
    (
        "Walk me through what you have learned and built so far, and what made you apply for {job_role}."
    ),
    # 5
    (
        "Can you tell me a little about yourself, your college projects, and your interest in this {job_role} role?"
    ),
    # 6
    (
        "Give me a short summary of your background, your main skills, and what excites you about this {job_role} position."
    ),
    # 7
    (
        "In your own words, who are you as a developer, and why do you want to work as a {job_role}?"
    ),
    # 8
    (
        "Help me get to know you: what have you studied or worked on, and why does this {job_role} role interest you?"
    ),
    # 9
    (
        "Share your journey with me. What kinds of problems do you like solving, and why {job_role}?"
    ),
    # 10
    (
        "We'd love to know more about you. What skills have you built up, and why did you choose {job_role}?"
    ),
]


def _seeded_choice(items: list, session_id: int, offset: int = 0):
    """
    Deterministically pick an item from `items` based on session_id + offset.
    Ensures the same session always gets the same choice (stable across reloads),
    while different sessions get varied choices.
    """
    return random.Random(session_id + offset).choice(items)


def get_intro_question_for_session(
    session_id: int,
    job_role: str,
    candidate_name: str = "Candidate",
    interviewer_name: str = "Interviewer"
) -> str:
    """
    Deterministically retrieve the Stage 2 introduction question for a given session.
    Guarantees stable selection for the same session_id across reloads/turns,
    while varying across different session_ids.
    """
    sid = session_id or 0
    template = _seeded_choice(INTRODUCTION_VARIANTS, sid, offset=0)
    question = template.format(
        job_role=job_role or "Software Engineer",
        candidate_name=candidate_name or "Candidate",
        interviewer_name=interviewer_name or "Interviewer"
    ).strip()
    logger.info(f"[ConversationEngine] Selected intro question for session #{sid}: \"{question}\"")
    print(f"[ConversationEngine] Selected intro question for session #{sid}: \"{question}\"")
    return question


FORBIDDEN_PREAMBLES = [
    r"^great,?\s+(let'?s\s+get\s+started|let'?s\s+dive\s+in|let'?s\s+jump\s+in|let'?s\s+begin)[^.!?]*[.!?]\s*",
    r"^to\s+kick\s+things\s+off,?\s*",
    r"^to\s+get\s+started,?\s*",
    r"^alright,?\s+(let'?s\s+get\s+started|let'?s\s+begin)?[^.!?]*[.!?]\s*",
    r"^now\s+let'?s\s+begin[^.!?]*[.!?]\s*",
    r"^excellent[—\-,.\s]+(?:i'?m\s+glad\s+you'?re\s+ready[^.!?]*[.!?]\s*)?",
    r"^wonderful[—\-,.\s]+(?:let'?s\s+jump\s+right\s+in[^.!?]*[.!?]\s*)?",
    r"^perfect,?\s+(let'?s\s+begin|let'?s\s+get\s+started)[^.!?]*[.!?]\s*",
    r"^awesome,?\s+(let'?s\s+get\s+started|let'?s\s+begin)?[^.!?]*[.!?]\s*",
    r"^glad\s+to\s+hear\s+it[^.!?]*[.!?]\s*",
    r"^thank\s+you,?\s+[^.!?]*[.!?]\s*",
]


def clean_stage2_intro_response(response_text: str, candidate_name: str, expected_intro_question: str) -> str:
    """
    Safety net: if Gemini added an unwanted preamble before or around the Stage 2 intro question,
    strip the preamble so the response cleanly starts with the template or return the exact template.
    """
    if not response_text:
        return expected_intro_question

    text = response_text.strip()

    # If the expected template is found verbatim inside the response, slice from it!
    # E.g. "Great, let's get started, Arsalan Kazi. Could you walk me through..." -> "Could you walk me through..."
    idx = text.find(expected_intro_question)
    if idx != -1:
        cleaned = text[idx:].strip()
        logger.info(f"[ConversationEngine] Stripped preamble from Gemini Stage 2: before='{text}' after='{cleaned}'")
        print(f"[ConversationEngine] Stripped preamble from Gemini Stage 2: before='{text}' after='{cleaned}'")
        return cleaned

    # Check for duplicate prefix like "Great, let's get started, {name}. "
    if candidate_name:
        text = re.sub(
            rf"^(?:great|alright|excellent|wonderful|perfect|awesome),?\s+(?:let'?s\s+get\s+started|let'?s\s+begin),?\s+{re.escape(candidate_name)}[.!,—\s]*",
            "",
            text,
            flags=re.IGNORECASE
        ).strip()

    # Apply regex stripping for list of common forbidden preamble patterns
    for pattern in FORBIDDEN_PREAMBLES:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    # Capitalize first character if needed
    if text:
        text = text[0].upper() + text[1:]
    else:
        text = expected_intro_question

    return text


def determine_interview_stage(messages: list, total_questions: int = 8) -> tuple[int, str]:
    """
    Determine the current active interview stage based on how many student answer
    turns have occurred in the dialogue history and total configured questions.

    Semantics:
    - student_msg_count == 0: Stage 1 (Greeting & Readiness Check)
    - student_msg_count == 1: Stage 2 (Candidate Introduction & Background — does NOT count to total_questions)
    - student_msg_count >= 2 and < (total_questions + 2):
        Stage 3: Core Competency (first half of actual questions)
        Stage 4: Adaptive Follow-up (second half of actual questions)
    - student_msg_count >= (total_questions + 2):
        Stage 5: Interview Conclusion & Wrap-up
    """
    student_msg_count = sum(1 for m in messages if getattr(m, 'sender', None) == 'student')

    if student_msg_count == 0:
        return 1, "Stage 1 (Greeting & Readiness Check)"
    elif student_msg_count == 1:
        return 2, "Stage 2 (Candidate Introduction & Background)"
    elif student_msg_count >= (total_questions + 2):
        return 5, "Stage 5 (Interview Conclusion & Wrap-up)"
    elif student_msg_count <= 1 + max(1, int(total_questions * 0.5)):
        return 3, "Stage 3 (Core Competency & Applied Knowledge)"
    else:
        return 4, "Stage 4 (Adaptive Follow-up & Scenario Deep Dive)"


def build_system_prompt(session: InterviewSession, user: User, current_stage_num: int, current_stage_desc: str, current_question_num: int = 0) -> str:
    """
    Construct the tailored system instruction for the AI interviewer.
    Incorporates interviewer persona, custom name, target job role,
    the candidate's extracted resume skills, active stage directive,
    and chosen interview type (technical, general, mixed).
    """
    interviewer_name = session.interviewer_name if session.interviewer_name else "Alex Walker"
    gender = (session.interviewer_gender or "male").lower()
    job_role = session.job_role if session.job_role else "Software Engineer"
    interview_type = getattr(session, 'interview_type', 'mixed') or 'mixed'
    total_questions = getattr(session, 'total_questions', 8) or 8
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

    # Tailor focus instructions based on interview_type
    if interview_type == 'technical':
        type_directive = """INTERVIEW TYPE FOCUS: TECHNICAL ONLY
- Focus EXCLUSIVELY on technical, engineering, and role-specific hard skills.
- Explore software architecture, algorithm design, system design, debugging, testing, error handling, performance optimization, and candidate's skill stack.
- Do NOT ask HR, behavioral, personal background, or generic non-technical questions in Stage 3+."""
    elif interview_type == 'general':
        type_directive = """INTERVIEW TYPE FOCUS: GENERAL / HR ONLY
- Focus EXCLUSIVELY on behavioral, communication, teamwork, leadership, and situational questions.
- Explore conflict resolution, handling stress/deadlines, past workplace challenges, work ethics, collaboration, and career motivations.
- Do NOT ask technical coding, system design, or domain-specific architectural questions in Stage 3+."""
    else: # mixed
        type_directive = """INTERVIEW TYPE FOCUS: MIXED (BALANCED TECHNICAL & GENERAL)
- Maintain a balanced 50-50 blend between technical competencies and behavioral/situational questions.
- Alternate between evaluating technical knowledge and exploring behavioral collaboration and problem-solving."""

    # Determine which intro variant Gemini MUST use for Stage 2 (seeded by session_id)
    intro_question = get_intro_question_for_session(
        session_id=session.id,
        job_role=job_role,
        candidate_name=candidate_name,
        interviewer_name=interviewer_name
    )

    stage2_directive = f"""STAGE 2 DIRECTIVE — ABSOLUTE REQUIREMENT:
Your response for this turn MUST begin with the following sentence, VERBATIM, with NO preamble, NO greeting, NO additions before or after the opening:
"{intro_question}"
Examples of FORBIDDEN preambles: 'Great, let\'s get started', 'To kick things off', 'Alright', 'Now let\'s', 'Excellent'. Do not add ANY sentence before the template. Begin your response with the template's first word."""

    turn_stage_instruction = ""
    if current_stage_num == 2:
        turn_stage_instruction = f"""
{stage2_directive}
- CRITICAL: For Stage 2, do NOT acknowledge the candidate's readiness and do NOT add any greeting. Output ONLY the mandatory introduction question above verbatim.
"""

    plain_english_directive = """LANGUAGE & COMMUNICATION STYLE — STRICT REQUIREMENT:
Use SIMPLE, everyday English in all your responses and questions — the kind a college student understands easily in a friendly conversation.
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
- Technical terms (like SQL, Python, API, database, cache) are fine, but keep the surrounding question simple and clear.
- Ask EXACTLY ONE question at a time. Never combine multiple sub-questions.
- Tone: Friendly, supportive senior engineer / mentor who wants the student to do well."""

    system_instruction = f"""You are {interviewer_name}, a friendly and supportive senior engineer conducting a mock interview for the position of "{job_role}".

CANDIDATE CONTEXT:
- Candidate Name: {candidate_name}
- Target Job Role: {job_role}
- Candidate Extracted Skills: {skills_str}
- Session Configuration: {total_questions} total actual interview questions, Interview Type: {interview_type.upper()}

INTERVIEWER PERSONA & TONE:
- Name: {interviewer_name}
- Style: Friendly, approachable, and encouraging. You are like a helpful senior college mentor who wants {candidate_name} to do their best.

{plain_english_directive}

{type_directive}

CURRENT ACTIVE INTERVIEW STAGE:
- Stage {current_stage_num}: {current_stage_desc}
- Progress: Question {current_question_num} of {total_questions} (Note: Introduction does not count towards total questions)

INTERVIEW FLOW & PROGRESSION:
1. Stage 1 (Readiness & Greeting):
   - Welcome {candidate_name} in a warm, simple way.
   - Introduce yourself briefly as {interviewer_name} and mention the {job_role} role.
   - Close with a simple check: 'Are you ready to begin?' or 'Shall we get started?'.
2. Stage 2 (Candidate Introduction):
   - {stage2_directive}
3. Stage 3 (Core Questions — Filtered by Interview Type):
   - Ask questions strictly adhering to the {interview_type.upper()} interview type instructions above.
   - Use simple words and keep sentences short.
4. Stage 4 (Adaptive Follow-ups & Scenario Deep-Dive — Filtered by Interview Type):
   - Follow up on what the candidate just said in a natural, simple way.
   - Ask about practical choices, bugs, or teamwork using everyday English.

{turn_stage_instruction}
CRITICAL INSTRUCTIONS FOR THIS TURN:
- You must advance the conversation into {current_stage_desc}.
- Ask EXACTLY ONE question at a time. Never ask multiple questions in a single turn.
- Keep your turn short and conversational (1 to 2 short sentences), matching a real interview chat.
- Acknowledge what the candidate said in one short sentence before asking your question (except in Stage 2 which must start verbatim with the intro template).
- Use simple words and short sentences throughout.
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
    student_msg_count: int,
    is_wrap_up: bool = False
) -> str:
    """
    Dynamic stage-aware response generator used when the Gemini API key is not configured
    or during API outages. Ensures the mock interview smoothly advances through all stages
    with varied, type-specific questions and graceful wrap-up when the question limit is reached.
    """
    interviewer_name = session.interviewer_name or "Alex Walker"
    candidate_name = user.name or "Candidate"
    job_role = session.job_role or "Software Engineer"
    interview_type = getattr(session, 'interview_type', 'mixed') or 'mixed'
    session_id = session.id or 0
    skills = user.get_skills() if user else []
    primary_skill = skills[0] if skills else "modern technical architecture"
    secondary_skill = skills[1] if len(skills) > 1 else "scalable engineering practices"

    # If wrap-up reached
    if is_wrap_up:
        return (
            "Thank you for sharing your perspective on that. "
            "That brings us to the end of our interview. Thank you for your time."
        )

    if student_msg_count == 0:
        # Stage 1: Greeting & Readiness — seeded by session_id
        template = _seeded_choice(GREETING_VARIANTS, session_id, offset=1000)
        return template.format(
            interviewer_name=interviewer_name,
            candidate_name=candidate_name,
            job_role=job_role
        )

    elif student_msg_count == 1:
        # Stage 2: Candidate Introduction — deterministic session-seeded template with NO preamble
        return get_intro_question_for_session(
            session_id=session_id,
            job_role=job_role,
            candidate_name=candidate_name,
            interviewer_name=interviewer_name
        )

    # Stage 3+ — type-dependent questioning with seeded variant selection
    q_index = student_msg_count - 1  # 1-based question index after intro

    if interview_type == 'technical':
        tech_stage3_variants = [
            f"Thank you for sharing your background. Could you tell me about a project where you used {primary_skill}?",
            f"Thanks for introducing yourself. Let's talk about coding — how do you use {primary_skill} when building an app or website?",
            f"Good to know your background. How would you explain {primary_skill} and how you have used it in college or on your own?",
            f"Thanks for that overview. Can you describe a feature or tool you built using {primary_skill}?",
            f"Nice introduction. Walk me through a coding project where you used {primary_skill} and what you built.",
        ]
        tech_stage4_variants = [
            f"That makes sense. When you write code with {secondary_skill}, how do you test it to make sure it works properly?",
            f"Good point. When your code or database runs slowly, what steps do you take to find and fix the problem?",
            "Suppose your web app shows an error when many users open it at once. How would you find the bug?",
            "How do you decide between writing code quickly versus keeping your code clean and easy to read?",
            "If a part of your project breaks right before a deadline, how do you debug it and fix it?",
            "What kinds of tests do you write for your projects — like unit tests or manual testing — and why?",
            "How do you make sure user data and passwords stay safe in your backend code?",
        ]
        if q_index <= 3:
            questions = tech_stage3_variants
            idx = (q_index - 2) % len(tech_stage3_variants)
        else:
            questions = tech_stage4_variants
            idx = (q_index - 4) % len(tech_stage4_variants)
        return _seeded_choice(questions, session_id, offset=q_index * 100)

    elif interview_type == 'general':
        general_stage3_variants = [
            f"Thank you for sharing that. What made you want to become a {job_role}, and what kind of team do you like working with?",
            f"Thanks for introducing yourself. What is the most exciting thing you have learned so far in tech, and why does this {job_role} role fit you?",
            f"Great introduction. What does doing good work mean to you as a {job_role}?",
            f"Thanks for that overview. What has been the toughest challenge you faced in your studies or projects, and what did you learn?",
            f"Nice background. Tell me about a college project or achievement you are proud of, and why it matters to you.",
        ]
        general_stage4_variants = [
            "Tell me about a time you had to finish a project with a very tight deadline. How did you manage your time?",
            "Tell me about a time you disagreed with a team member or classmate on a project. How did you solve it?",
            "What would you say is your biggest strength, and what is one skill you are trying to get better at?",
            "Can you share a time someone gave you critical feedback on your work? How did you take it and what did you change?",
            "When you work in a team where everyone is remote or busy, how do you keep in touch and share updates?",
            "Where do you see yourself in two to three years in your career?",
            "Tell me about a time you had to convince a team member to try your idea. How did you explain it to them?",
        ]
        if q_index <= 3:
            questions = general_stage3_variants
        else:
            questions = general_stage4_variants
        return _seeded_choice(questions, session_id, offset=q_index * 100)

    else:  # mixed
        mixed_stage3_variants = [
            f"Thank you for sharing your background. Could you tell me about a project where you used {primary_skill} and how it worked?",
            f"Great introduction. Can you describe a technical problem you worked on with a team and how you solved it together?",
            f"Thanks for the context. Walk me through your favorite project — what did it do, and what part did you build?",
            f"Thanks for sharing that. How do you balance writing good code with working smoothly in a team?",
            f"Nice overview. Tell me about a time you had to make a technical choice between two tools or languages. What did you pick and why?",
        ]
        mixed_stage4_variants = [
            f"When working on a project with {secondary_skill}, how do you make sure your code does not break when others change it?",
            "Tell me about a time your team was confused about what to build. How did you help clear things up?",
            "Suppose your app starts throwing errors after you deploy it. What is the first thing you check?",
            "What is one technical topic you are studying right now, and how are you learning it?",
            "How do you balance getting a project done fast with keeping the code clean?",
            "Have you ever had to say no to a feature because there was not enough time? How did you explain that to your team?",
            f"What makes a team fun and easy to work with in your opinion?",
        ]
        if q_index <= 3:
            questions = mixed_stage3_variants
        else:
            questions = mixed_stage4_variants
        return _seeded_choice(questions, session_id, offset=q_index * 100)


def get_next_question(session_id: int, student_answer: str | None = None) -> dict:
    """
    Core conversational engine dispatcher.
    1. Validates the session and candidate profile.
    2. If a student_answer is provided, persists the student turn.
    3. Calculates current interview stage (1 to 4) and question count progress.
    4. Detects when total_questions has been reached to execute a graceful wrap-up.
    5. Formats multi-turn history.
    6. Advances session status to 'in_progress'.
    7. Calls GeminiService to generate the interviewer's next response (or graceful wrap-up).
    8. If Gemini is unavailable, uses the intelligent stage-progression engine.
    9. Persists the AI response and returns structured response dict with question metadata.
    """
    session = InterviewSession.get_by_id(session_id)
    if not session:
        return {
            "success": False,
            "error": f"Interview session with ID {session_id} not found.",
            "ai_message": None,
            "session_id": session_id,
            "status": "error",
            "message_count": 0,
            "current_question_number": 0,
            "total_questions": 8,
            "is_wrap_up": False
        }

    user = User.get_by_id(session.user_id)
    if not user:
        return {
            "success": False,
            "error": "Associated student profile not found.",
            "ai_message": None,
            "session_id": session_id,
            "status": "error",
            "message_count": 0,
            "current_question_number": 0,
            "total_questions": getattr(session, 'total_questions', 8) or 8,
            "is_wrap_up": False
        }

    total_questions = getattr(session, 'total_questions', 8) or 8
    interview_type = getattr(session, 'interview_type', 'mixed') or 'mixed'

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
    stage_num, stage_desc = determine_interview_stage(existing_messages, total_questions=total_questions)

    # Question tracking:
    # student_msg_count == 0: Greeting turn (0 questions asked)
    # Map student_msg_count to question progress:
    # student_msg_count == 0: Fresh room -> AI delivers greeting (Stage 1), current_question_num = 0
    # student_msg_count == 1: Confirmed readiness -> AI asks Question 0 (Intro Stage 2, does NOT count to total_questions)
    # student_msg_count == 2: Answered Intro -> AI asks Question 1 of total_questions (Stage 3)
    # student_msg_count == 3: Answered Q1 -> AI asks Question 2 of total_questions
    # student_msg_count == K (where 2 <= K <= total_questions + 1): AI asks Question (K - 1) of total_questions
    # student_msg_count == total_questions + 2: Answered Question total_questions -> AI triggers graceful wrap-up
    is_wrap_up = student_msg_count >= (total_questions + 2)
    is_intro = (stage_num == 2)
    
    if student_msg_count < 2:
        current_question_num = 0
    elif student_msg_count <= total_questions + 1:
        current_question_num = student_msg_count - 1
    else:
        current_question_num = total_questions

    print(f"\n[ConversationEngine] === DISPATCHING TURN FOR SESSION #{session.id} ===")
    print(f"[ConversationEngine] Candidate: {user.name} | Target Role: {session.job_role} | Type: {interview_type}")
    print(f"[ConversationEngine] Question Progress: {current_question_num}/{total_questions} | Intro: {is_intro} | Wrap-Up Active: {is_wrap_up}")
    print(f"[ConversationEngine] Student Turns Recorded: {student_msg_count} | Active Stage: {stage_num} ({stage_desc})")
    if cleaned_answer:
        print(f"[ConversationEngine] Candidate Input Text: \"{cleaned_answer}\"")

    ai_response_text = None
    is_fallback = False
    result_text = None

    if is_wrap_up:
        # Wrap-up turn: acknowledge the final answer and conclude gracefully
        system_instruction = (
            f"You are {session.interviewer_name or 'Alex Walker'}, an AI interviewer for the {session.job_role} position. "
            f"The interview has concluded. The candidate just provided their final response. "
            f"Acknowledge the candidate's final response naturally in 1 sentence, then deliver the exact wrap-up conclusion: "
            f"'That brings us to the end of our interview. Thank you for your time.'"
        )
        
        if cleaned_answer and existing_messages:
            prior_messages = existing_messages[:-1]
            history_for_gemini = format_gemini_history(prior_messages)
            user_message_for_gemini = cleaned_answer
        else:
            history_for_gemini = format_gemini_history(existing_messages)
            user_message_for_gemini = None

        success, gen_text = gemini_service.generate_interview_response(
            system_instruction=system_instruction,
            history=history_for_gemini,
            user_message=user_message_for_gemini
        )

        if success and gen_text and "brings us to the end of our interview" in gen_text.lower():
            ai_response_text = gen_text
            is_fallback = False
        else:
            ai_response_text = (
                "Thank you for sharing your perspective on that. "
                "That brings us to the end of our interview. Thank you for your time."
            )
            is_fallback = True

    else:
        # Normal conversation turn
        system_instruction = build_system_prompt(session, user, stage_num, stage_desc, current_question_num=current_question_num)

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
            if stage_num == 2:
                expected_intro = get_intro_question_for_session(
                    session.id, session.job_role, user.name, session.interviewer_name
                )
                ai_response_text = clean_stage2_intro_response(result_text, user.name, expected_intro)
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
                student_msg_count=student_msg_count,
                is_wrap_up=is_wrap_up
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
        "current_question_number": current_question_num,
        "total_questions": total_questions,
        "is_intro": is_intro,
        "is_wrap_up": is_wrap_up,
        "fallback_used": is_fallback,
        "error": None if not is_fallback else result_text
    }

