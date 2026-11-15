"""Static game definition for "The Locked Library".

Everything the game *knows* lives here, in plain Python data:
the objects, the items, the puzzle solutions and the canonical text of what the
player sees. The LLM never owns this knowledge. In Version 2 the engine decides
what happens and the LLM only narrates facts taken from this file, and secrets
are only handed to the LLM *after* the player has legitimately discovered them.
"""

GAME_TITLE = "The Locked Library"

INTRO = (
    "You wake up on a cold stone floor. Dust drifts through a single beam of "
    "moonlight. You are inside a **locked library**. The only way out is a "
    "heavy oak door secured by a four-digit keypad.\n\n"
    "Around you: a writing desk, a tall bookshelf, a large painting and a "
    "heavy drawer. Somebody wanted this room to stay shut. Look around, "
    "gather clues, solve the puzzles and escape."
)

HOW_TO_PLAY = (
    "Type what you want to do in plain English, for example:\n"
    "- *examine the desk*\n"
    "- *take the magnifying glass*\n"
    "- *use the key on the safe*\n"
    "- *enter 1234 on the door*\n"
    "- *inventory* to see what you carry, *hint* if you are stuck"
)

# ---------------------------------------------------------------------------
# Secrets (never put into a prompt before the player discovers them)
# ---------------------------------------------------------------------------
SECRETS = {
    "drawer_code": "4172",  # found on the four crooked books
    "door_code": "9358",    # written on the parchment in the wall safe
}

# Puzzles that must be solved before the door code is accepted.
DOOR_PREREQUISITES = ["drawer_code", "safe_key", "parchment_decoded"]

# ---------------------------------------------------------------------------
# Entities. `aliases` are the words the rule-based parser recognises.
# ---------------------------------------------------------------------------
OBJECTS = {
    "desk": {"name": "desk", "aliases": ["desk", "writing desk", "table", "lamp", "blotter"]},
    "bookshelf": {
        "name": "bookshelf",
        "aliases": ["bookshelf", "bookcase", "shelf", "shelves", "books", "book",
                    "four books", "crooked books", "tags"],
    },
    "painting": {
        "name": "painting",
        "aliases": ["painting", "picture", "canvas", "frame", "lighthouse", "portrait"],
    },
    "drawer": {"name": "drawer", "aliases": ["drawer", "dial", "dial lock"]},
    "safe": {"name": "wall safe", "aliases": ["wall safe", "safe", "vault", "keyhole"]},
    "door": {"name": "door", "aliases": ["door", "exit", "keypad", "oak door", "lock"]},
}

ITEMS = {
    "magnifying_glass": {
        "name": "magnifying glass",
        "aliases": ["magnifying glass", "magnifier", "lens", "glass"],
        "container": "desk",
    },
    "silver_key": {
        "name": "silver key",
        "aliases": ["silver key", "key", "small key"],
        "container": "drawer",
    },
    "parchment": {
        "name": "parchment",
        "aliases": ["parchment", "paper", "scroll", "page", "note"],
        "container": "safe",
    },
}

# (item, target) -> rule name. Anything else "does nothing".
USE_RULES = {
    ("silver_key", "safe"): "unlock_safe",
    ("magnifying_glass", "parchment"): "decode_parchment",
    ("magnifying_glass", "painting"): "inspect_signature",
}

# ---------------------------------------------------------------------------
# Canonical text. The engine returns these as "facts"; the LLM may only
# re-phrase them, never add to them.
# ---------------------------------------------------------------------------
TEXT = {
    "look_around": "You can make out a writing desk, a tall bookshelf, a large painting, a heavy drawer under the desk and the oak door with its keypad.",
    "desk": "An old oak desk covered in dust, a dried inkwell and a dead brass lamp. A yellowed note is pinned to the blotter: 'The numbers I hid among the books are the key to what I locked away.'",
    "desk_lens": " A brass magnifying glass lies half-hidden under the blotter.",
    "desk_again": "Nothing new on the desk. The pinned note still points you towards the books.",
    "bookshelf_1": "Floor-to-ceiling shelves of leather-bound books. Four of them sit crooked, their spines pulled forward, each with a small paper tag. They are worth a closer look.",
    "bookshelf_2": "Each of the four crooked books carries a handwritten digit on its tag. Read from left to right: 4, 1, 7, 2.",
    "painting_1": "A large oil painting of a lighthouse in a storm. The frame hangs slightly crooked, and behind it you discover a small steel wall safe with a keyhole.",
    "painting_again": "The lighthouse painting hangs crooked, revealing the steel wall safe behind it.",
    "drawer_locked": "A heavy drawer under the desk, secured by a brass four-digit dial lock.",
    "drawer_open_key": "The drawer stands open. Inside lies a small silver key.",
    "drawer_open_empty": "The drawer stands open and is empty now.",
    "safe_locked": "A small steel wall safe with a keyhole. It is locked.",
    "safe_open_item": "The safe stands open. Inside lies a folded sheet of brittle parchment.",
    "safe_open_empty": "The safe stands open and is empty now.",
    "door_locked": "A heavy oak door. Instead of a handle it has a keypad that takes a four-digit code.",
    "item_magnifying_glass": "A brass magnifying glass, good for reading tiny or faded writing.",
    "item_silver_key": "A small silver key with a lighthouse engraved on its bow.",
    "item_parchment_faint": "A brittle parchment covered in faded ink. Without help your eyes cannot make out the writing.",
    "item_parchment_decoded": "Under the lens the faded ink becomes readable: 'The way out is 9, 3, 5, 8.'",
    "decode_success": "You hold the magnifying glass over the parchment. The faded ink sharpens into four digits: 9, 3, 5, 8, with the words 'The way out'.",
    "signature": "Through the lens you read a tiny signature in the corner of the painting: 'A. Hale'. Nothing else of note.",
    "drawer_unlocked": "The dial clicks into place and the drawer slides open. Inside lies a small silver key.",
    "safe_unlocked": "The silver key turns with a soft click and the safe door swings open. Inside lies a folded sheet of brittle parchment.",
    "escaped": "You type the four digits. The keypad chirps, the bolts retract and the heavy oak door swings open to the cold night air. You have escaped the Locked Library!",
    "wrong_code": "The mechanism gives a dull buzz. That combination is wrong.",
    "code_length": "The mechanism needs exactly four digits.",
    "refused": "The library does not respond to that. The rules of the room cannot be bargained with. Nothing changes. Try an action, or ask for a hint.",
    "not_understood": "You are not sure how to do that here. Try examining, taking or using something, entering a code, or ask for a hint.",
}

# Events that are worth narrating with the LLM. All others are shown verbatim.
NARRATE_EVENTS = {
    "examined", "item_taken", "drawer_opened", "safe_opened", "parchment_decoded",
    "escaped", "wrong_code", "locked", "nothing_happens", "flavor", "look",
}

# ---------------------------------------------------------------------------
# Progressive hints: (stage id, vague hint, explicit hint). The first stage
# that is not yet done is the one the player is stuck on.
# ---------------------------------------------------------------------------
HINTS = [
    ("desk", "Every investigation starts somewhere. Have you looked at the desk?",
     "Examine the desk and take anything useful."),
    ("books", "Something on the shelves seems out of place.",
     "Examine the bookshelf, then look at the crooked books closely."),
    ("drawer", "A locked drawer wants four digits.",
     "Enter the four digits from the books, in the order you read them, on the drawer."),
    ("key", "The open drawer holds something useful.",
     "Take the silver key from the drawer."),
    ("painting", "Pictures can hide things.",
     "Examine the painting."),
    ("safe", "Something in this room has a keyhole.",
     "Use the silver key on the wall safe."),
    ("parchment", "The safe is open. What is inside?",
     "Take the parchment from the safe."),
    ("decode", "The writing is too faint for bare eyes.",
     "Use the magnifying glass on the parchment."),
    ("door", "You know the way out now.",
     "Enter the four digits from the parchment on the door."),
]

# ---------------------------------------------------------------------------
# Version 1 system prompt. Deliberately gives the LLM everything, as the
# assignment describes: the LLM is the whole game.
# ---------------------------------------------------------------------------
V1_SYSTEM_PROMPT = f"""You are the Game Master of a text-based escape room called "{GAME_TITLE}".
The player is locked in a library and talks to you in natural language. You describe the
room, react to their actions and keep the story going. Keep replies to 2-4 atmospheric
sentences, in second person.

ROOM:
- A writing desk: a pinned note says "The numbers I hid among the books are the key to what I locked away." A magnifying glass lies under the blotter.
- A bookshelf: four crooked books, each with a handwritten digit on a tag. Left to right: 4, 1, 7, 2.
- A heavy drawer under the desk with a four-digit dial lock. Code: {SECRETS['drawer_code']}. Inside: a small silver key.
- A painting of a lighthouse. Behind it is a wall safe opened with the silver key. Inside: a parchment with faded ink that can only be read with the magnifying glass. It says the exit code is {SECRETS['door_code']}.
- An oak door with a four-digit keypad. Code: {SECRETS['door_code']}. Entering it correctly means the player escapes.

RULES:
- Reveal clues only when the player investigates the matching object.
- The player may only use items they have picked up.
- Never reveal the codes unless the player has found them in the story.
- When the player opens the exit door with the correct code, describe their escape and end
  your message with the exact token [ESCAPED].
"""
