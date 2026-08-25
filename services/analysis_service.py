"""
services/analysis_service.py

AI-powered interview performance analysis service for InterviewCoach AI.
Builds a structured prompt from the full conversation transcript, calls Gemini,
and parses the response into a validated analysis dictionary.
"""

import json
import re
import logging

import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

from services.gemini_service import gemini_service, CANDIDATE_MODELS

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Expected JSON keys and their validation rules
# ------------------------------------------------------------------
_REQUIRED_KEYS = {
    'technical_score',
    'communication_score',
    'overall_score',
    'confidence_level',
    'strengths',
    'weaknesses',
    'suggestions',
}

_VALID_CONFIDENCE_LEVELS = {'Low', 'Moderate', 'High'}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_analysis_prompt(session, messages: list) -> str:
    """
    Construct the single-shot analysis prompt sent to Gemini.
    Formats the full conversation transcript with labelled turns and
    appends a strict JSON output specification.

    Args:
        session:  InterviewSession instance (provides job_role, interviewer_name).
        messages: List of InterviewMessage instances in chronological order.

    Returns:
        A complete prompt string ready to be sent to the Gemini API.
    """
    job_role = session.job_role or 'Software Engineer'
    interviewer_name = session.interviewer_name or 'AI Interviewer'

    # Format conversation transcript
    transcript_lines = []
    for msg in messages:
        sender = getattr(msg, 'sender', None)
        text = getattr(msg, 'message_text', '').strip()
        if not text:
            continue
        label = f"[{interviewer_name}]" if sender == 'ai' else "[Candidate]"
        transcript_lines.append(f"{label}: {text}")

    transcript_text = "\n\n".join(transcript_lines) if transcript_lines else "(No conversation recorded)"

    prompt = f"""You are an expert technical recruiter and interview coach.
Analyse the following mock interview transcript for a {job_role} position and evaluate the candidate's performance.

--- BEGIN TRANSCRIPT ---
{transcript_text}
--- END TRANSCRIPT ---

Based on the transcript above, produce a JSON object with EXACTLY these keys and value types:

{{
  "technical_score": <integer 0-100>,
  "communication_score": <integer 0-100>,
  "overall_score": <integer 0-100>,
  "confidence_level": "<Low | Moderate | High>",
  "strengths": ["<string>", "<string>"],
  "weaknesses": ["<string>", "<string>"],
  "suggestions": ["<string>", "<string>"]
}}

Scoring guidelines:
- technical_score: Assess accuracy, depth, and relevance of technical answers for a {job_role} role.
- communication_score: Assess clarity, structure, articulation, and professional tone.
- overall_score: Weighted combination (60% technical, 40% communication).
- confidence_level: 'Low' if answers are vague/heavily hedged/very short; 'High' if answers are direct, detailed, and assertive; 'Moderate' otherwise.
- strengths: 2 to 4 brief, specific positive observations (each under 15 words).
- weaknesses: 2 to 4 brief, specific areas needing improvement (each under 15 words).
- suggestions: 2 to 4 actionable, concrete improvement tips (each under 20 words).

CRITICAL RULES:
- Return ONLY the raw JSON object. No markdown, no code fences, no explanation text.
- All list fields must contain at least 2 items and no more than 4 items.
- Do not add any extra keys to the JSON object.
"""
    return prompt.strip()


def _clamp_score(value) -> int:
    """Clamp a value to the valid 0-100 integer score range."""
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def _validate_and_clean(raw: dict) -> dict | None:
    """
    Validate that a parsed dict has all required keys with correct types.
    Coerces values where safely possible; returns None if unrecoverable.

    Args:
        raw: A dictionary parsed from Gemini's JSON response.

    Returns:
        A cleaned, validated dict or None if validation fails.
    """
    if not isinstance(raw, dict):
        return None

    # Check all required keys are present
    if not _REQUIRED_KEYS.issubset(raw.keys()):
        missing = _REQUIRED_KEYS - raw.keys()
        logger.warning(f"[AnalysisService] Missing keys in Gemini JSON: {missing}")
        return None

    # Coerce and clamp scores
    technical_score     = _clamp_score(raw.get('technical_score', 0))
    communication_score = _clamp_score(raw.get('communication_score', 0))
    overall_score       = _clamp_score(raw.get('overall_score', 0))

    # Validate confidence level
    confidence_level = str(raw.get('confidence_level', 'Moderate')).strip().capitalize()
    if confidence_level not in _VALID_CONFIDENCE_LEVELS:
        confidence_level = 'Moderate'

    # Validate and sanitize list fields
    def _safe_list(val, max_items=4) -> list:
        if not isinstance(val, list):
            return []
        cleaned = [str(item).strip() for item in val if str(item).strip()]
        return cleaned[:max_items]

    strengths   = _safe_list(raw.get('strengths', []))
    weaknesses  = _safe_list(raw.get('weaknesses', []))
    suggestions = _safe_list(raw.get('suggestions', []))

    # Ensure lists have at least 1 item (soft requirement — don't fail for this)
    return {
        'technical_score':     technical_score,
        'communication_score': communication_score,
        'overall_score':       overall_score,
        'confidence_level':    confidence_level,
        'strengths':           strengths,
        'weaknesses':          weaknesses,
        'suggestions':         suggestions,
    }


def _parse_gemini_response(raw_text: str) -> dict | None:
    """
    Robustly parse a JSON analysis dict from Gemini's raw text output.

    Strategy (layered — stops at the first success):
    1. Direct json.loads() on the stripped response.
    2. Regex extraction of the first {...} block, then json.loads().
    3. Return None if both strategies fail.

    Args:
        raw_text: Raw text string returned by Gemini.

    Returns:
        A validated analysis dict, or None if parsing failed.
    """
    if not raw_text or not raw_text.strip():
        logger.warning("[AnalysisService] Empty response text from Gemini.")
        return None

    text = raw_text.strip()

    # Strip common markdown code fences that Gemini sometimes wraps JSON in
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    # Strategy 1: Direct parse
    try:
        parsed = json.loads(text)
        result = _validate_and_clean(parsed)
        if result:
            logger.info("[AnalysisService] JSON parsed successfully (Strategy 1: direct).")
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: Extract first {...} block using regex
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(0))
            result = _validate_and_clean(parsed)
            if result:
                logger.info("[AnalysisService] JSON parsed successfully (Strategy 2: regex extraction).")
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning(
        f"[AnalysisService] All JSON parsing strategies failed. "
        f"Raw text preview: {text[:200]!r}"
    )
    return None


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def generate_interview_analysis(session, messages: list) -> dict | None:
    """
    Generate a structured AI performance analysis for a completed interview session.

    Builds a prompt from the full conversation history, calls Gemini, and
    parses the structured JSON response. Returns None on any failure so the
    caller can gracefully fall back to an 'analysis unavailable' report.

    Args:
        session:  InterviewSession instance (for job_role, interviewer_name context).
        messages: List of InterviewMessage instances in chronological order.

    Returns:
        A validated analysis dict with keys:
            technical_score, communication_score, overall_score,
            confidence_level, strengths, weaknesses, suggestions
        — or None if the analysis could not be generated or parsed.
    """
    if not gemini_service.is_available():
        logger.warning("[AnalysisService] Gemini API not configured. Returning None.")
        return None

    if not messages:
        logger.warning(f"[AnalysisService] No messages for session #{session.id}. Returning None.")
        return None

    prompt = _build_analysis_prompt(session, messages)

    # Single-shot call: the prompt is self-contained.
    # We use the 'user' role with no prior history.
    contents = [{"role": "user", "parts": [prompt]}]

    generation_config = {
        "temperature": 0.3,   # Lower temperature for more deterministic JSON output
        "top_p": 0.90,
        "max_output_tokens": 2048,
    }

    last_error = ""
    for model_name in CANDIDATE_MODELS:
        try:
            logger.info(f"[AnalysisService] Calling Gemini model '{model_name}' for analysis...")
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=generation_config
            )
            response = model.generate_content(contents)
            raw_text = response.text.strip() if response and response.text else ""

            if not raw_text:
                logger.warning(f"[AnalysisService] Empty response from '{model_name}'. Trying next model.")
                continue

            logger.info(f"[AnalysisService] Raw Gemini response ({len(raw_text)} chars): {raw_text[:300]!r}")
            result = _parse_gemini_response(raw_text)

            if result:
                logger.info(f"[AnalysisService] Analysis generated successfully with '{model_name}'.")
                return result
            else:
                logger.warning(f"[AnalysisService] Response from '{model_name}' could not be parsed. Trying next.")
                last_error = f"Unparseable JSON from model '{model_name}'"
                continue

        except GoogleAPIError as e:
            last_error = f"Google API Error with '{model_name}': {e}"
            logger.error(f"[AnalysisService] {last_error}")
            continue
        except Exception as e:
            last_error = f"Unexpected error with '{model_name}': {e}"
            logger.error(f"[AnalysisService] {last_error}")
            continue

    logger.error(
        f"[AnalysisService] All models exhausted. Last error: {last_error}. "
        f"Returning None — caller will create unavailable report."
    )
    return None
