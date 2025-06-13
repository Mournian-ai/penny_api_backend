from collections import deque
from typing import Deque, Optional, Tuple, List

class ContextManager:
    def __init__(self, max_history: int = 5):
        self.chat_history: Deque[Tuple[str, str]] = deque(maxlen=max_history)  # Stores (user_input, ai_response)
        self.latest_vision_summary: Optional[str] = None
        self.last_emotions: Deque[Tuple[str, str]] = deque(maxlen=10)

    def update_chat(self, user_input: str, ai_response: str) -> None:
        """Add a new user/AI message pair to the conversation history."""
        self.chat_history.append((user_input, ai_response))

    def set_vision_context(self, vision_summary: str) -> None:
        """Store the latest vision summary to include in prompts."""
        self.latest_vision_summary = vision_summary

    def build_prompt(self, current_input: str, include_vision: bool = False) -> str:
        """Constructs the full prompt to send to the LLM."""
        parts: List[str] = []

        if self.chat_history:
            history = "\n".join(f"User: {u}\nPenny: {a}" for u, a in self.chat_history)
            parts.append("[CONVERSATION HISTORY]\n" + history)

        if include_vision and self.latest_vision_summary:
            parts.append("[VISION]\n" + self.latest_vision_summary)

        biased_input = f"{current_input}\n\n(Remember: You’re here to dominate this conversation and have a little fun at their expense.)"
        parts.append("[USER INPUT]\n" + biased_input)

        return "\n\n".join(parts)

    def record_emotion(self, tone: str, emotion: str) -> None:
        """Store the latest emotional state (for prompt context or behavioral adaptation)."""
        self.last_emotions.append((tone, emotion))
