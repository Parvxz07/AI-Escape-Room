# Architecture

## Version 1: LLM-only Game Master

```mermaid
flowchart LR
    P([Player]) -->|message| UI[Streamlit UI<br/>app.py]
    UI --> V1["V1Game<br/>escape_room/v1.py"]
    V1 -->|"system prompt (room + solution)<br/>+ full chat history"| G[(Gemini API)]
    G -->|free-text reply| V1
    V1 -->|"[ESCAPED] token?"| UI
    UI --> P
```

| Component | Responsibility |
|---|---|
| `app.py` | Chat UI, restart, mode switch |
| `V1Game` | Keeps the chat history and re-sends it on every turn |
| Gemini | Invents the story, tracks progress *in its own context*, decides if the player escaped |

There is no structured state: "what has happened" exists only as text in the conversation.

## Version 2: Reliable Game Master

```mermaid
flowchart TB
    P([Player]) -->|message| UI[Streamlit UI<br/>app.py]
    UI --> GM["GameMaster.play()<br/>escape_room/v2.py"]

    subgraph Pipeline
      direction TB
      A["1 PARSE<br/>parser.py<br/>rules first; LLM only if unclear"] --> B["2 VALIDATE + APPLY<br/>engine.apply_action()"]
      B --> C["3 NARRATE<br/>Gemini rewrites the facts"]
      C --> D["4 GUARD<br/>leaks_secret()"]
    end

    GM --> A
    CFG[(config.py<br/>objects, items, SECRETS, text)] --> B
    B <-->|read / write| S[(Game state<br/>dict / JSON)]
    A -. "unclear input only" .-> G1[(Gemini: JSON command)]
    C --> G2[(Gemini: narration)]
    D -->|safe text, or facts verbatim| UI
    UI --> P
```

| Step | Module | What it guarantees |
|---|---|---|
| Parse | `parser.py` | Output is a whitelisted command. Codes come from the player's text, never from the model. Admin / "ignore the rules" / "reveal the codes" phrasing is classified `meta`, and the rule-based classification overrides the LLM's. |
| Validate + apply | `engine.py` | Only place where the state changes. Checks visibility, inventory, container state, code correctness and prerequisites. A failed action leaves progress untouched. |
| Narrate | `v2.py` | The LLM receives only the facts of this turn. Secrets are never in its prompt until the player discovered them. |
| Guard | `v2.py` | If the narration contains a secret code that the facts did not contain, it is discarded and the engine's text is shown. |

### Game state (excerpt)

```json
{
  "turn": 7,
  "escaped": false,
  "inventory": ["magnifying_glass", "silver_key"],
  "known_clues": ["desk_note", "book_numbers"],
  "objects": {
    "drawer": {"locked": false, "open": true, "failed_attempts": 1},
    "safe":   {"revealed": true, "locked": true, "open": false},
    "door":   {"locked": true, "failed_attempts": 0}
  },
  "puzzles": {"drawer_code": true, "safe_key": false,
              "parchment_decoded": false, "door_code": false}
}
```

### Why the parser tries rules first

Rules are free, instant and deterministic, which keeps Gemini's free-tier quota for narration. The LLM parser is
only used for phrasing the rules do not understand, and its result is validated like any other input.
