import os
import time
from google import genai
from google.genai import types


PRIMARY_GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_FALLBACK_MODELS = ("gemini-3.5-flash",)


def get_gemini_model_chain(preferred_model=None):
    """Return the bounded production model chain, without duplicate attempts."""
    models = [preferred_model or PRIMARY_GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]
    return list(dict.fromkeys(models))


def is_transient_gemini_error(error):
    """Identify errors worth one short retry before moving to the next model."""
    status_code = getattr(error, "status_code", None) or getattr(error, "code", None)
    if status_code in (429, 503):
        return True
    error_text = str(error).lower()
    return any(marker in error_text for marker in (
        "429", "503", "resource_exhausted", "high demand",
    ))

def log_group_start(title):
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::group::{title}", flush=True)
    else:
        print(f"\n=== {title} ===", flush=True)

def log_group_end():
    if os.getenv("GITHUB_ACTIONS") == "true":
        print("::endgroup::", flush=True)
    else:
        print("=" * 40 + "\n", flush=True)

class BaseAgent:
    """
    Base Agent class that shares the Google GenAI Client and common utility methods.
    """
    def __init__(self, client=None, model_name=PRIMARY_GEMINI_MODEL):
        self.client = client
        self.model_name = model_name

    def run_llm(self, prompt, system_instruction=None, response_schema=None, mime_type=None, retries=2):
        """
        Executes a call to the Gemini API, with built-in retry logic and model fallbacks.
        """
        if not self.client:
            raise ValueError(f"[{self.__class__.__name__}] Gemini client is not initialized.")

        # Set up content generation config
        config = types.GenerateContentConfig()
        if system_instruction:
            config.system_instruction = system_instruction
        if mime_type:
            config.response_mime_type = mime_type
        if response_schema:
            config.response_mime_type = "application/json"
            config.response_schema = response_schema

        last_error = None
        for model in get_gemini_model_chain(self.model_name):
            for attempt in range(retries):
                try:
                    response = self.client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config
                    )
                    return response.text
                except Exception as e:
                    last_error = e
                    print(f"[{self.__class__.__name__}] Call failed with model '{model}' (attempt {attempt+1}): {e}")
                    if not is_transient_gemini_error(e) or attempt == retries - 1:
                        break
                    time.sleep(1)

        raise last_error
