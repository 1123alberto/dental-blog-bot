import os
import time
from google import genai
from google.genai import types

class BaseAgent:
    """
    Base Agent class that shares the Google GenAI Client and common utility methods.
    """
    def __init__(self, client=None, model_name="gemini-3.5-flash"):
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
        # Try primary model first, fallback to stable models if needed
        models = [self.model_name, "gemini-2.5-flash", "gemini-2.0-flash"]
        unique_models = []
        for m in models:
            if m not in unique_models:
                unique_models.append(m)

        for model in unique_models:
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
                    time.sleep(1)

        raise last_error
