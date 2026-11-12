"""Version 2 - Reliable AI Escape Room.

Python engine = source of truth (state, rules, validation).
LLM = translator (text -> action) and narrator (outcome -> prose).

Run:  streamlit run v2/app.py
Works without an API key too (rule parser + canonical text), which is handy for demos and tests.
"""
import json

import streamlit as st
from dotenv import load_dotenv

from engine import Game, load_config
from llm import interpret, make_client, narrate

load_dotenv()
CFG = load_config()

HELP = """**How to play**
- Type what you want to do, e.g. *examine the painting*, *take the key*, *use the key on the drawer*, *enter 1234 on the door*.
- Only items in your **inventory** can be used.
- Say *hint* if you are stuck. Use **Restart game** to start over."""


@st.cache_resource
def client():
    return make_client()


def reset():
    st.session_state.game = Game(CFG)
    st.session_state.history = [{"role": "assistant", "content": CFG["intro"]}]
    st.session_state.last_action = None


st.set_page_config(page_title="AI Escape Room v2", page_icon="🔐")
st.title("🔐 The Locked Library - Version 2")
st.caption("Reliable edition: Python enforces the rules, the AI tells the story.")

if "game" not in st.session_state:
    reset()
game: Game = st.session_state.game

with st.sidebar:
    st.markdown(HELP)
    st.subheader("Inventory")
    st.write(", ".join(game.state["inventory"]) or "empty")
    st.subheader("Puzzles solved")
    labels = {"find_key": "Found the key", "open_drawer": "Opened the drawer", "exit_door": "Opened the door"}
    solved = [labels[p] for p in game.state["solved_puzzles"]]
    st.write("\n".join(f"- {s}" for s in solved) or "none yet")
    st.caption(f"Turns: {game.state['turns']}")
    if client() is None:
        st.warning("No GEMINI_API_KEY found: running in offline mode (no AI narration).")
    if st.button("Restart game"):
        reset()
        st.rerun()
    with st.expander("Debug: last parsed action"):
        st.json(st.session_state.last_action or {})

for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if game.flags["escaped"]:
    st.success("You escaped! Press 'Restart game' to play again.")
elif prompt := st.chat_input("What do you do?"):
    st.session_state.history.append({"role": "user", "content": prompt})
    action = interpret(prompt, game, client())
    result = game.apply(action)
    st.session_state.last_action = action
    reply = narrate(client(), game, result)
    st.session_state.history.append({"role": "assistant", "content": reply})
    st.rerun()
