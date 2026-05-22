import os
import json
from datetime import datetime

# Default path for persistent memory file
MEMORY_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output", "agent_memory.json")

class AgentMemory:
    """
    Manages loading, updating, and formatting of persistent agent memory
    (lessons learned from past QA failures/successes).
    """
    def __init__(self, memory_file_path=MEMORY_FILE_PATH):
        self.memory_file_path = memory_file_path
        self.lessons = []
        self.load_memory()

    def load_memory(self):
        """Loads lessons from JSON file."""
        if not os.path.exists(self.memory_file_path):
            self.lessons = []
            return

        try:
            with open(self.memory_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.lessons = data
                elif isinstance(data, dict) and "lessons" in data:
                    self.lessons = data["lessons"]
        except Exception as e:
            print(f"[AgentMemory] Warning: Failed to load memory from {self.memory_file_path}: {e}")
            self.lessons = []

    def save_memory(self):
        """Saves current lessons to JSON file."""
        try:
            dir_name = os.path.dirname(self.memory_file_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

            with open(self.memory_file_path, "w", encoding="utf-8") as f:
                json.dump({"lessons": self.lessons}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AgentMemory] Error saving memory: {e}")

    def add_lesson(self, category, error_description, correction_rule):
        """Adds a lesson learned to the memory database, avoiding duplicates."""
        new_lesson = {
            "category": category,
            "error": error_description.strip(),
            "rule": correction_rule.strip(),
            "timestamp": datetime.now().isoformat()
        }

        # Check for duplication of the rule
        for lesson in self.lessons:
            if lesson.get("rule").lower() == new_lesson["rule"].lower():
                return  # Duplicate rule, skip

        # Keep a maximum of 25 lessons to avoid bloat
        self.lessons.insert(0, new_lesson)
        self.lessons = self.lessons[:25]
        self.save_memory()

    def get_lessons_prompt_block(self):
        """Formats the stored lessons as a Markdown block for prompt injection."""
        if not self.lessons:
            return ""

        prompt_lines = [
            "\n### IMPORTANT: LESSONS LEARNED FROM PREVIOUS RUNS",
            "Below is a list of mistakes made in previous runs and the rules you MUST follow to prevent them:"
        ]
        
        for idx, lesson in enumerate(self.lessons, 1):
            prompt_lines.append(f" {idx}. [{lesson['category'].upper()}] Rule: {lesson['rule']} (Reference Error: {lesson['error']})")
        
        prompt_lines.append("\nStrictly avoid repeating these errors.")
        return "\n".join(prompt_lines)
