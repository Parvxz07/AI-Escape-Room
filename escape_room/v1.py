"""Version 1: the LLM *is* the game.

One system prompt contains the whole room, the solution and the rules. The only
memory is the chat history that is re-sent each turn. There is no structured
state and no validation, which is exactly what Version 2 fixes.
"""
from __future__ import annotations

from . import config as C
from .llm import LLMError

ESCAPE_TOKEN = "[ESCAPED]"


class V1Game:
    def __init__(self):
        self.history: list[tuple[str, str]] = []
        self.escaped = False

    def play(self, message: str, llm) -> str:
        if llm is None:
            raise LLMError("Version 1 needs a Gemini API key.")
        self.history.append(("user", message))
        try:
            reply = llm.generate(C.V1_SYSTEM_PROMPT, self.history, temperature=0.8)
        except LLMError:
            self.history.pop()  # do not keep a turn the model never answered
            raise
        if ESCAPE_TOKEN in reply:
            self.escaped = True
            reply = reply.replace(ESCAPE_TOKEN, "").strip()
        self.history.append(("model", reply))
        return reply
