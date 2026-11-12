# Architecture

GitHub renders the Mermaid diagrams below automatically.

## Version 1 - LLM as everything

```mermaid
flowchart LR
    P[Player] -->|natural language| UI[Streamlit chat UI]
    UI -->|full chat history| LLM[Gemini API<br/>Game Master]
    SP[(System prompt<br/>room, clues, solutions, rules)] --> LLM
    LLM -->|free-text reply| UI
    UI -->|shows reply| P
    LLM -. "'[GAME COMPLETE]' marker" .-> UI
```

- The only memory is the chat history.
- Solutions are inside the prompt, so the model can leak them.
- The model decides whether an action works and when the game is won.

## Version 2 - Python owns the game, LLM translates and narrates

```mermaid
flowchart TD
    P[Player] -->|natural language| UI[Streamlit chat UI]
    UI --> RP{Rule parser<br/>override / reveal guard}
    RP -->|clear command| SA[sanitize and whitelist action]
    RP -->|fuzzy text| LP[Gemini intent parser<br/>JSON output, temp 0]
    LP --> SA
    SA -->|"structured action<br/>{action, target, item, code}"| ENG[Game engine<br/>validation + rules]
    CFG[(game_config.json<br/>objects, items, solutions, hints)] --> ENG
    ENG <--> ST[(Game state<br/>flags, inventory,<br/>solved puzzles, door)]
    ENG -->|"Result: ok + canonical message"| NAR[Gemini narrator]
    NAR --> FIL{Output filter<br/>no new numbers,<br/>no leaked secrets,<br/>no fake success}
    FIL -->|safe| UI
    FIL -->|unsafe or API error| CAN[Canonical engine text] --> UI
    UI --> P
```

Key idea: the LLM never sees the solutions and never decides an outcome. It
only converts text to a validated action and rephrases a result that has already
been decided by Python.
