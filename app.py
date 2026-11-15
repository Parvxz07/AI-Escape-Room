"""Streamlit front end for the AI Escape Room (Version 1 and Version 2)."""
import json
import os

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional at runtime
    pass

from escape_room import config as C
from escape_room.engine import progress
from escape_room.llm import GeminiClient, LLMError, get_api_key
from escape_room.v1 import V1Game
from escape_room.v2 import GameMaster

st.set_page_config(page_title=C.GAME_TITLE, page_icon="🗝️", layout="centered")

st.markdown(
    """
    <style>
      .block-container {max-width: 820px; padding-top: 2rem;}
      h1 {letter-spacing: .5px;}
      .tagline {color: #8a8f98; margin-top: -0.6rem; margin-bottom: 1rem;}
      div[data-testid="stSidebar"] .stButton button {width: 100%;}
    </style>
    """,
    unsafe_allow_html=True,
)

MODES = {"v1": "Version 1: LLM only", "v2": "Version 2: Reliable (state engine)"}


# ----------------------------------------------------------------- session
def init_session() -> None:
    if "games" not in st.session_state:
        st.session_state.games = {"v1": V1Game(), "v2": GameMaster()}
        st.session_state.chats = {"v1": [], "v2": []}
        st.session_state.pending = None


def intro_message() -> dict:
    return {"role": "assistant", "content": C.INTRO}


def restart(mode: str) -> None:
    st.session_state.games[mode] = V1Game() if mode == "v1" else GameMaster()
    st.session_state.chats[mode] = []


def current_llm():
    key = st.session_state.get("api_key_input") or get_api_key()
    if not key:
        return None
    cache = st.session_state.get("llm_cache")
    if not cache or cache[0] != key:
        try:
            cache = (key, GeminiClient(key))
        except LLMError as exc:
            st.sidebar.error(str(exc))
            return None
        st.session_state.llm_cache = cache
    return cache[1]


init_session()
llm = current_llm()

# ----------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("🗝️ " + C.GAME_TITLE)
    mode = st.radio("Game version", list(MODES), index=1, format_func=MODES.get, key="mode")
    game = st.session_state.games[mode]

    if st.button("🔄 Restart game"):
        restart(mode)
        st.rerun()

    with st.expander("How to play", expanded=False):
        st.markdown(C.HOW_TO_PLAY)

    st.divider()
    if llm:
        st.success(f"Gemini connected ({llm.model})")
    else:
        st.warning("No Gemini API key found.")
        st.text_input("Paste a key (kept in this session only)", type="password", key="api_key_input",
                      help="Or set GEMINI_API_KEY in a .env file. Free key: aistudio.google.com/apikey")
        if mode == "v2":
            st.caption("Version 2 still works without a key, using built-in parsing and narration.")

    if mode == "v2":
        st.divider()
        st.subheader("Inventory")
        inv = game.state["inventory"]
        st.write(", ".join(C.ITEMS[i]["name"] for i in inv) if inv else "*empty*")
        st.subheader("Progress")
        for label, done in progress(game.state):
            st.write(("✅ " if done else "⬜ ") + label)
        st.divider()
        show_details = st.toggle("Show engine details", value=False)
        with st.expander("Game state (developer view)"):
            st.json(game.state, expanded=False)
    else:
        show_details = False
        st.info("Version 1 has no state tracking or validation. Everything depends on the LLM.")

    st.divider()
    st.caption("Quick actions")
    for label, text in [("👀 Look around", "look around"), ("🎒 Inventory", "inventory"), ("💡 Hint", "hint")]:
        if st.button(label, key=f"qa_{label}"):
            st.session_state.pending = text

# -------------------------------------------------------------------- main
st.title(C.GAME_TITLE)
st.markdown(f'<div class="tagline">{MODES[mode]}</div>', unsafe_allow_html=True)

chat = st.session_state.chats[mode]
if not chat:
    chat.append(intro_message())

for msg in chat:
    with st.chat_message(msg["role"], avatar="🧙" if msg["role"] == "assistant" else "🧍"):
        st.markdown(msg["content"])
        if show_details and msg.get("meta"):
            st.caption(msg["meta"])
        if msg.get("notice"):
            st.caption("⚠️ " + msg["notice"])

escaped = game.escaped if mode == "v1" else game.state["escaped"]
if escaped:
    st.balloons()
    st.success("🎉 You escaped! Press **Restart game** in the sidebar to play again.")

needs_key = mode == "v1" and llm is None
if needs_key:
    st.info("Version 1 is powered entirely by Gemini. Add an API key in the sidebar to play it.")

typed = st.chat_input("What do you do?", disabled=needs_key or escaped)
user_text = st.session_state.pending or typed
st.session_state.pending = None

if user_text and not needs_key:
    chat.append({"role": "user", "content": user_text})
    with st.chat_message("user", avatar="🧍"):
        st.markdown(user_text)
    with st.chat_message("assistant", avatar="🧙"):
        with st.spinner("The Game Master considers..."):
            if mode == "v1":
                try:
                    reply = game.play(user_text, llm)
                    chat.append({"role": "assistant", "content": reply})
                except LLMError as exc:
                    chat.append({"role": "assistant", "content": f"⚠️ {exc}"})
            else:
                turn = game.play(user_text, llm)
                meta = (f"event: `{turn.result['event']}` · {'success' if turn.result['ok'] else 'rejected'} · "
                        f"command: `{json.dumps({k: v for k, v in turn.command.items() if v})}`")
                chat.append({"role": "assistant", "content": turn.reply, "meta": meta, "notice": turn.notice})
    st.rerun()
