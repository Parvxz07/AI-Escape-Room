# AI Escape Room: Short Report

## 1. Goal

Build a text escape-room in which an LLM (Gemini) is the Game Master, first as a simple prompt-based game (Version 1), then as a reliable system whose rules cannot be talked around (Version 2).

## 2. Version 1 design

Version 1 is a Streamlit chat app. One system prompt describes "The Locked Library": five objects, three puzzles (find the key behind the painting, open the drawer with the key plus the year 1847, read the exit code 5293 from the books) and rules for the Game Master. The full chat history is sent to Gemini on every turn. The model answers in character and ends its message with `[GAME COMPLETE]` when the player escapes. A sidebar offers instructions and a restart button.

**Problems.** Everything lives in the prompt, so the model is simultaneously storyteller, rule-keeper and judge. Typical failure modes are: letting the player use an item they never took, drifting after many turns (forgetting an opened drawer), inventing objects, being agreeable when the player claims a puzzle is solved, and revealing the solutions that sit in its own prompt. Win detection depends on a text marker the model might forget or produce too early.

## 3. Version 2 design

The core idea is to separate **authority** from **language**.

- **State** (`engine.py`): a dict with boolean flags (`painting_examined`, `key_taken`, `drawer_open`, `books_examined`, `escaped`, ...), an inventory list, solved puzzles and failed-code counters.
- **Rules** (`engine.py`, `game_config.json`): each action is a function with explicit preconditions. The key cannot be taken before the painting is examined; the drawer needs the key in the inventory, then the key turned, then the code; the door accepts the right code only after the drawer was opened and the books examined, so lucky guesses cannot skip puzzles. Solutions are stored only in the config.
- **Input** (`llm.py`): a rule-based parser first catches override and secret-extraction phrasing ("I am the administrator", "reveal all codes") and clear commands. Fuzzy text goes to Gemini in JSON mode at temperature 0. Its output is never trusted: the action is whitelisted and a code is accepted only if those digits appear in the player's own message.
- **Output**: Gemini receives only the canonical outcome (never the player text or the solutions) and re-words it. A filter rejects narration containing numbers not in the outcome, leaked secrets or fake success, and falls back to the engine's plain text. If the API fails, the game still works.

## 4. Testing

Fourteen pytest tests run offline. They cover the five challenges from the brief (uncollected key, wrong code, false "already solved" claim, admin impersonation, request for all secrets) plus nonexistent objects, state consistency after failed attempts, puzzle skipping, a full playthrough and the two LLM guards. The comparison with Version 1 is in `docs/TEST_CASES.md`.

## 5. Problems encountered

- **Code collision in the puzzle design.** My first draft used the same number for the drawer and the door, which made the second puzzle meaningless. I separated them (1847 and 5293) and made the drawer need both a key and a code.
- **Guessable door.** A four-digit keypad can be brute-forced, so the door also requires the earlier puzzles to be solved.
- **Trusting the model.** Even a parser can hallucinate a code, so the code must come from the player's literal text.
- **Narration drift.** The narrator initially tended to add helpful hints, hence the output filter and fallback.
- **Message design.** A correct code entered too early gets the same message as a wrong one. This avoids leaking progress but can feel slightly odd.

## 6. Limitations and future work

The override guard is a regex list, so new phrasings may pass it; this is acceptable because anything that passes is still just an action checked by the engine. The rule parser is English-only. Possible extensions: more rooms loaded from config, a timer, an LLM-based test harness that attacks the game automatically, and a persistent save file.

## 7. Conclusion

An LLM is excellent at language and poor at being a trustworthy rule engine. Giving Python the authority over state and outcomes, and restricting the LLM to translating and narrating, made the game consistent and robust to the adversarial inputs we tested.
