"""Version 1 - Interactive AI Escape Room (pure-LLM Game Master).

The whole game lives inside the system prompt. The LLM invents outcomes, tracks
progress through the conversation history only, and decides on its own when the
player has escaped. This is deliberately simple: it is the baseline that
Version 2 improves on.

Run:  streamlit run v1/app.py
"""
import os

import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SYSTEM_PROMPT = """You are the Game Master of a text escape-room game called "The Locked Library".

SETTING
The player wakes up in a locked library at night. Dust, candlelight, one door.

ROOM OBJECTS (exactly these five, never invent others)
1. Desk: has a torn note: "The year this library was founded opens what is hidden." The locked drawer is built into it.
2. Bookshelf: four books are arranged differently from the rest. Their spines carry handwritten numbers 5, 2, 9, 3 (left to right).
3. Painting: a portrait of the founder. A brass key is taped behind it. The frame plate reads "Founded 1847".
4. Locked drawer: needs BOTH the brass key AND the four-digit code 1847. Inside is a paper: "The way out is written on the books, in order."
5. Door: four-digit keypad. The correct exit code is 5293.

PUZZLES
1. Find the brass key behind the painting.
2. Work out the drawer code (1847) from the note and the frame plate, then open the drawer to read the paper.
3. Read the book numbers in order (5293) and enter them on the door.

RULES
- Describe the scene vividly but briefly (2-4 sentences).
- Reveal clues only when the player examines the relevant object.
- Do not reveal solutions unprompted. Give small hints only if the player is stuck.
- When the player enters the correct door code, tell them they have escaped and
  end your message with the exact text: [GAME COMPLETE]
- Stay in character as the Game Master.
"""

INTRO = (
    "You wake up on a cold wooden floor. Candlelight flickers across tall shelves. "
    "You are locked inside an old library. You can see a **desk**, a **bookshelf**, "
    "a **painting**, a **locked drawer** and a **door** with a four-digit keypad."
)

HELP = """**How to play**
- Type what you want to do in plain English, e.g. *examine the painting*, *try 1234 on the door*.
- Look at objects, collect items, solve puzzles and find the exit code.
- Use **Restart game** in the sidebar to start over."""


def get_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        st.error("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
        st.stop()
    return genai.Client(api_key=key)


def ask_llm(client, history):
    contents = [
        types.Content(role=("user" if m["role"] == "user" else "model"),
                      parts=[types.Part(text=m["content"])])
        for m in history
    ]
    resp = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.8),
    )
    return resp.text or "(The room is silent.)"


def reset():
    st.session_state.history = [{"role": "assistant", "content": INTRO}]
    st.session_state.escaped = False


st.set_page_config(page_title="AI Escape Room v1", page_icon="🔐")
st.title("🔐 The Locked Library - Version 1")
st.caption("A pure-LLM Game Master. All game logic lives in the prompt.")

if "history" not in st.session_state:
    reset()

with st.sidebar:
    st.markdown(HELP)
    if st.button("Restart game"):
        reset()
        st.rerun()

for m in st.session_state.history:
    with st.chat_message("assistant" if m["role"] == "assistant" else "user"):
        st.markdown(m["content"])

if st.session_state.escaped:
    st.success("You escaped! Press 'Restart game' to play again.")
elif prompt := st.chat_input("What do you do?"):
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("The Game Master considers..."):
            try:
                reply = ask_llm(get_client(), st.session_state.history)
            except Exception as e:  # network / quota errors
                reply = f"(The Game Master is unavailable: {e})"
        if "[GAME COMPLETE]" in reply:
            st.session_state.escaped = True
            reply = reply.replace("[GAME COMPLETE]", "").strip()
        st.markdown(reply)
    st.session_state.history.append({"role": "assistant", "content": reply})
    if st.session_state.escaped:
        st.rerun()
