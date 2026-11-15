# Project Report: AI-Powered Escape Room

**Author:** Mohammed Parvez · **Repository:** github.com/Parvxz07/AI-Escape-Room

## 1. Goal

Build an escape-room game in which an LLM acts as the Game Master, then make it reliable. The player wakes in a
locked library and must find clues, solve puzzles and enter a four-digit code to leave. The assignment has two
stages: a working LLM-driven game (Version 1) and a hardened version with structured state and validation (Version 2).

## 2. Game design

The room has six interactive objects (desk, bookshelf, painting, drawer, wall safe, door) and three collectable
items (magnifying glass, silver key, parchment). The solution is a chain of four puzzles:

1. Desk note leads to the bookshelf, where four crooked books show a drawer code.
2. The open drawer holds a key.
3. The painting hides a wall safe, which the key opens.
4. The parchment inside is unreadable without the magnifying glass; once decoded it gives the door code.

The chain makes inventory rules meaningful (the key and lens must be collected) and gives each step a clear
prerequisite.

## 3. Version 1: LLM as the whole game

Gemini receives one system prompt that contains the room, the solutions and the rules, plus the full chat history
on every turn. It decides what is possible, remembers progress and reports the escape with a token. This is quick to
build and reads well, but all game logic is implicit in generated text. Its weaknesses follow directly from that design:

- No authoritative state, so progress can be forgotten or contradicted in a long session.
- The solutions are inside the prompt, so they can be leaked.
- Nothing prevents invented objects, early clues or actions on items the player never collected.
- The model can be talked into unlocking the exit (administrator claims, "ignore the rules").

## 4. Version 2: Python decides, the LLM describes

The key change is a separation of responsibilities.

| Layer | Implementation | Role |
|---|---|---|
| State | `engine.new_state()` (nested dicts) | Single source of truth: inventory, object flags, puzzle flags, clues, door status, log |
| Rules | `engine.apply_action()` and handlers | Validate visibility, inventory, container state, codes and prerequisites |
| Knowledge | `config.py` | Objects, items, secrets and canonical text, outside any generated response |
| Parser | `parser.py` | Free text to whitelisted JSON command; rules first, LLM for unclear phrasing |
| Narrator | `v2.py` | Gemini re-phrases the facts of one turn, nothing more |
| Guard | `leaks_secret()` | Blocks narration that contains an undiscovered code |

Design decisions worth explaining:

- **Least-privilege prompting.** The narrator never sees a secret until the player has found it, because secrets only
  reach it as part of a fact. This is stronger than telling the model "do not reveal the code".
- **The LLM output is treated as untrusted input.** Parser output is whitelisted, codes are taken from the player's
  own text, and a rule-based `meta` classification overrides the LLM parser.
- **Premature correct codes fail like wrong ones.** The door requires the three earlier puzzles to be solved, and a
  correct-but-early code gets the same response as a wrong one, so it gives no feedback.
- **Graceful degradation.** Without an API key or when Gemini is rate-limited, the game continues with the engine's text.
- **Rules before LLM for parsing** to preserve free-tier quota and keep common commands deterministic.

## 5. Testing

42 pytest tests cover the full walkthrough, the five example challenges from the brief, the premature door code,
hidden objects, unreachable items, nonexistent objects, state integrity after failed actions, malformed commands,
the leak guard with a deliberately leaky fake narrator, and LLM outage handling. They use fake LLM objects so they
are deterministic and need no key. See `docs/TEST_CASES.md` for the Version 1 vs Version 2 comparison table.

## 6. Problems encountered

- **Environment:** `pip` and `streamlit` were not on the Windows PATH; the fix was `py -m pip` and `py -m streamlit`.
- **Empty files committed:** the first commits contained empty files, which is why the Streamlit page was blank
  (no code to render). The project was then written in full and committed in logical steps.
- **SDK choice:** the older `google-generativeai` package is deprecated, so the project uses `google-genai`.
- **Model availability:** Gemini model names change over time, so the client tries a list of fallbacks and the model
  can be overridden with `GEMINI_MODEL`.
- **Rate limits:** two LLM calls per turn would exhaust a free tier quickly; the parser therefore only calls the LLM for
  phrasing it cannot understand, and static replies (inventory, hints, refusals) are not sent to the narrator.
- **Parsing ambiguity:** words such as "key" or "note" appear in several contexts, so the parser resolves
  longest aliases first and the engine validates the result.
- **Retired model:** Google retired `gemini-2.5-flash` for new accounts, which showed up as a 404 NOT_FOUND error. I listed the available models with `models.list()`, tested which one worked, and switched the default to a current model.

## 7. Limitations and future work

The rule parser supports common phrasing only; the LLM parser covers the rest but is non-deterministic. There is one
room and one linear puzzle chain. Future work: multiple rooms, saved games, a live-API adversarial test runner and
embedding-free intent classification evaluation.

## 8. Conclusion

Version 1 shows how quickly an LLM can produce an engaging game; Version 2 shows that reliability comes from
moving authority out of the model. The LLM remains valuable, but only for language, while Python owns the truth.
