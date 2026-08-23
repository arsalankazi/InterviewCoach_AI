"""
services/gemini_service.py

Wrapper for the Google Generative AI SDK (google-generativeai).
Configures the Gemini API client, formats chat history, and handles errors gracefully.
"""

import os
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

# Load environment variables from .env if present
load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiService:
    """
    Encapsulates Google Gemini API calls for interview dialogue generation.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self._is_configured = False
        self._setup_client()

    def _setup_client(self):
        """Configure the Gemini client with the API key from environment."""
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self._is_configured = True
            except Exception as e:
                logger.error(f"Failed to configure Gemini SDK: {e}")
                self._is_configured = False
        else:
            logger.warning("GEMINI_API_KEY environment variable is not set.")
            self._is_configured = False

    def is_available(self) -> bool:
        """Check if Gemini API is configured with an API key."""
        if not self._is_configured or not self.api_key:
            # Re-check in case .env was loaded or environment changed dynamically
            self._setup_client()
        return self._is_configured and bool(self.api_key)

    def generate_interview_response(
        self,
        system_instruction: str,
        history: list[dict],
        user_message: str | None = None
    ) -> tuple[bool, str]:
        """
        Generate the next AI response in an interview dialogue given system instructions
        and conversation history.

        Args:
            system_instruction: System prompt framing the interviewer persona, role, and rules.
            history: List of past messages formatted as [{'role': 'user'|'model', 'parts': ['...']}].
            user_message: The latest student answer/input (if any).

        Returns:
            tuple[bool, str]: (Success boolean, Generated text or error message)
        """
        if not self.is_available():
            return False, "Gemini API key is not configured. Please ensure GEMINI_API_KEY is set in your .env file."

        try:
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "max_output_tokens": 512,
            }

            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction,
                generation_config=generation_config
            )

            # Build full multi-turn contents list
            contents = []
            if history:
                for h in history:
                    role = h.get("role", "user")
                    parts = h.get("parts", [])
                    contents.append({"role": role, "parts": parts})

            if user_message and user_message.strip():
                contents.append({"role": "user", "parts": [user_message.strip()]})
            elif not contents:
                # Initial opening turn if no history and no user message yet
                prompt = (
                    "Begin the interview now according to Stage 1 of your system instructions. "
                    "Greet the candidate, introduce yourself by your persona name and role, and ask if they are ready and comfortable to begin."
                )
                contents.append({"role": "user", "parts": [prompt]})

            response = model.generate_content(contents)
            text = response.text.strip() if response and response.text else ""
            if not text:
                return False, "Received empty response from Gemini API."
            return True, text

        except GoogleAPIError as e:
            logger.error(f"Google API Error during generation: {e}")
            return False, f"AI service error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during Gemini API call: {e}")
            return False, f"Failed to generate response: {str(e)}"


# Singleton instance for application-wide service access
gemini_service = GeminiService()
