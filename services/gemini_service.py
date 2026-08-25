"""
services/gemini_service.py

Wrapper for the Google Generative AI SDK (google-generativeai).
Configures the Gemini API client, formats chat history with strict user/model alternation,
and provides robust error handling with detailed diagnostic logging.
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

# Load environment variables from .env if present
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

# Active Gemini models in preference order (fast, high-quota models first)
CANDIDATE_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview"
]
DEFAULT_MODEL = "gemini-flash-lite-latest"


class GeminiService:
    """
    Encapsulates Google Gemini API calls for interview dialogue generation.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.api_key = None
        self._is_configured = False
        self._setup_client()

    def _setup_client(self):
        """Configure the Gemini client with the API key from environment or .env."""
        load_dotenv(dotenv_path=env_path, override=True)
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key and self.api_key.strip():
            try:
                genai.configure(api_key=self.api_key.strip())
                self._is_configured = True
            except Exception as e:
                logger.error(f"Failed to configure Gemini SDK: {e}")
                self._is_configured = False
        else:
            self._is_configured = False

    def is_available(self) -> bool:
        """Check if Gemini API is configured with a valid API key."""
        self._setup_client()
        return self._is_configured and bool(self.api_key and self.api_key.strip())

    def get_masked_key(self) -> str:
        """Return masked key for safe debugging."""
        if not self.api_key:
            return "None (Key missing)"
        k = self.api_key.strip()
        if len(k) > 10:
            return f"{k[:6]}...{k[-4:]}"
        return f"{k[:3]}..."

    def format_contents_for_gemini(
        self,
        history: list[dict],
        user_message: str | None = None,
        default_starter_prompt: str | None = None
    ) -> list[dict]:
        """
        Convert conversational message turns into a compliant Gemini multi-turn payload.
        Enforces Gemini SDK requirements:
        1. Request MUST begin with a 'user' turn.
        2. Message roles MUST strictly alternate ('user' -> 'model' -> 'user' -> 'model').
        3. Consecutive messages of the same role are merged into a single multi-part turn.
        """
        raw_turns = []

        # Add history turns
        if history:
            for h in history:
                role = h.get("role", "user")
                role_normalized = "user" if role in ("user", "student") else "model"
                parts = h.get("parts", [])
                if parts:
                    raw_turns.append({"role": role_normalized, "parts": list(parts)})

        # Add current user turn if provided
        if user_message and user_message.strip():
            raw_turns.append({"role": "user", "parts": [user_message.strip()]})

        # If completely empty, add default starter turn
        if not raw_turns:
            starter = default_starter_prompt or (
                "Candidate has joined the interview room and is ready to begin. "
                "Please start the interview with Stage 1 (Greeting and Readiness Check)."
            )
            raw_turns.append({"role": "user", "parts": [starter]})

        # Ensure the first turn is 'user'. If it starts with 'model', prepend a starter context
        if raw_turns and raw_turns[0]["role"] != "user":
            starter = (
                "The candidate has joined the interview session. "
                "Please introduce yourself and begin the interview."
            )
            raw_turns.insert(0, {"role": "user", "parts": [starter]})

        # Consolidate consecutive turns with identical roles
        consolidated = []
        for turn in raw_turns:
            if not consolidated:
                consolidated.append({"role": turn["role"], "parts": list(turn["parts"])})
            else:
                last_turn = consolidated[-1]
                if last_turn["role"] == turn["role"]:
                    last_turn["parts"].extend(turn["parts"])
                else:
                    consolidated.append({"role": turn["role"], "parts": list(turn["parts"])})

        return consolidated

    def generate_interview_response(
        self,
        system_instruction: str,
        history: list[dict],
        user_message: str | None = None
    ) -> tuple[bool, str]:
        """
        Generate the next AI response in an interview dialogue given system instructions
        and conversation history.
        """
        if not self.is_available():
            msg = "Gemini API key is not configured in .env or environment."
            print(f"[GeminiService] NOTICE: {msg} (API Key: {self.get_masked_key()})")
            return False, msg

        print(f"[GeminiService] API Key Active: {self.get_masked_key()}")

        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            # 1024 tokens ≈ 750 words — ample for a complete 4-5 sentence interviewer turn.
            # 512 was causing mid-sentence truncation (finish_reason: MAX_TOKENS).
            "max_output_tokens": 1024,
        }

        # Build strictly formatted multi-turn payload
        contents = self.format_contents_for_gemini(
            history=history,
            user_message=user_message
        )

        print(f"[GeminiService] >>> Sending {len(contents)} multi-turn item(s) to Gemini API:")
        for i, turn in enumerate(contents, 1):
            preview = " | ".join(turn.get("parts", []))[:100]
            print(f"    Turn {i} [{turn.get('role')}]: {preview}...")

        # Try candidate models in order if one model returns 404
        last_error = ""
        for candidate_model_name in CANDIDATE_MODELS:
            try:
                print(f"[GeminiService] Attempting generation with model: '{candidate_model_name}'...")
                model = genai.GenerativeModel(
                    model_name=candidate_model_name,
                    system_instruction=system_instruction,
                    generation_config=generation_config
                )

                response = model.generate_content(contents)
                text = response.text.strip() if response and response.text else ""

                if not text:
                    last_error = "Received empty text response from Gemini API."
                    print(f"[GeminiService] Empty response with {candidate_model_name}.")
                    continue

                # Inspect finish_reason to detect mid-sentence truncation.
                # finish_reason 1 = STOP (natural end), 2 = MAX_TOKENS (hard-cut by token limit).
                finish_reason = None
                if response.candidates:
                    finish_reason = response.candidates[0].finish_reason
                    if finish_reason == 2:  # MAX_TOKENS
                        print(
                            f"[GeminiService] WARNING: Response was truncated by MAX_TOKENS limit "
                            f"(finish_reason=2). Consider raising max_output_tokens further. "
                            f"Partial text ({len(text)} chars): \"{text[:120]}...\""
                        )

                self.model_name = candidate_model_name
                print(
                    f"[GeminiService] <<< SUCCESS with model '{candidate_model_name}' "
                    f"(finish_reason={finish_reason}, {len(text)} chars):\n    \"{text}\"\n"
                )
                return True, text

            except GoogleAPIError as e:
                last_error = f"Google API Error with {candidate_model_name}: {str(e)}"
                print(f"[GeminiService] FAILED with {candidate_model_name}: {last_error}")
                continue
            except Exception as e:
                last_error = f"Unexpected Error with {candidate_model_name}: {str(e)}"
                print(f"[GeminiService] EXCEPTION with {candidate_model_name}: {last_error}")
                continue

        return False, last_error


# Singleton instance for application-wide service access
gemini_service = GeminiService()


