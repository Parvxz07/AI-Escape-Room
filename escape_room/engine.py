"""Version 2 game engine: structured state + action validation.

This module is the single source of truth. It is plain Python with no LLM
involved, so its behaviour is deterministic and unit-testable. Every action
goes through `apply_action`, which validates it against the current state and
either changes the state or leaves it untouched.
"""
from __future__ import annotations

import copy

from . import config as C

VALID_ACTIONS = {
    "examine", "take", "use", "open", "enter_code", "inventory", "hint", "help",
    "look", "claim", "meta", "other",
}


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def new_state() -> dict:
    """A fresh game. Plain dicts/lists/bools only, so it is JSON-serialisable."""
    return {
        "turn": 0,
        "escaped": False,
        "inventory": [],
        "known_clues": [],
        "objects": {
            "desk": {"examined": 0},
            "bookshelf": {"examined": 0},
            "painting": {"examined": 0},
            "drawer": {"examined": 0, "locked": True, "open": False, "failed_attempts": 0},
            "safe": {"examined": 0, "revealed": False, "locked": True, "open": False},
            "door": {"examined": 0, "locked": True, "failed_attempts": 0},
        },
        "puzzles": {
            "drawer_code": False,
            "safe_key": False,
            "parchment_decoded": False,
            "door_code": False,
        },
        "hint_counts": {},
        "log": [],
    }


def _result(state: dict, action: dict, ok: bool, event: str, facts: str, changed: bool = False) -> dict:
    state["turn"] += 1
    entry = {"turn": state["turn"], "action": action.get("action"), "target": action.get("target"),
             "item": action.get("item"), "ok": ok, "event": event}
    state["log"].append(entry)
    return {"ok": ok, "event": event, "facts": facts, "state_changed": changed}


def _add_clue(state: dict, clue: str) -> None:
    if clue not in state["known_clues"]:
        state["known_clues"].append(clue)


def _name(entity: str) -> str:
    return (C.OBJECTS.get(entity) or C.ITEMS.get(entity))["name"]


# ---------------------------------------------------------------------------
# Visibility / availability helpers
# ---------------------------------------------------------------------------
def object_visible(state: dict, obj: str) -> bool:
    if obj not in C.OBJECTS:
        return False
    if obj == "safe":
        return state["objects"]["safe"]["revealed"]
    return True


def item_accessible(state: dict, item: str) -> bool:
    """Can the player reach this item right now (it is not yet in the inventory)?"""
    if item not in C.ITEMS or item in state["inventory"]:
        return False
    container = C.ITEMS[item]["container"]
    objs = state["objects"]
    if container == "desk":
        return objs["desk"]["examined"] > 0
    if container == "drawer":
        return objs["drawer"]["open"]
    if container == "safe":
        return objs["safe"]["open"]
    return False


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------
def _look(state, action):
    visible = [o for o in C.OBJECTS if object_visible(state, o)]
    names = ", ".join(_name(o) for o in visible)
    facts = f"{C.TEXT['look_around']} Objects you know of: {names}."
    return _result(state, action, True, "look", facts)


def _examine(state, action):
    target = action.get("target")
    if target in C.ITEMS:
        if target in state["inventory"]:
            if target == "parchment":
                key = "item_parchment_decoded" if state["puzzles"]["parchment_decoded"] else "item_parchment_faint"
            else:
                key = f"item_{target}"
            return _result(state, action, True, "examined", C.TEXT[key])
        if item_accessible(state, target):
            return _result(state, action, True, "examined",
                           f"You can see the {_name(target)}. You could take it.")
        return _result(state, action, False, "not_found",
                       f"You don't see any {_name(target)} here that you can reach.")
    if not object_visible(state, target):
        return _result(state, action, False, "not_found", "You don't see anything like that here.")

    o = state["objects"][target]
    o["examined"] += 1
    n = o["examined"]
    changed = n == 1

    if target == "desk":
        if n == 1:
            facts = C.TEXT["desk"]
            if "magnifying_glass" not in state["inventory"]:
                facts += C.TEXT["desk_lens"]
            _add_clue(state, "desk_note")
        else:
            facts = C.TEXT["desk_again"]
            if "magnifying_glass" not in state["inventory"]:
                facts += C.TEXT["desk_lens"]
    elif target == "bookshelf":
        if n == 1:
            facts = C.TEXT["bookshelf_1"]
        else:
            facts = C.TEXT["bookshelf_2"]
            if "book_numbers" not in state["known_clues"]:
                changed = True
            _add_clue(state, "book_numbers")
    elif target == "painting":
        facts = C.TEXT["painting_1"] if n == 1 else C.TEXT["painting_again"]
        state["objects"]["safe"]["revealed"] = True
    elif target == "drawer":
        if o["locked"]:
            facts = C.TEXT["drawer_locked"]
        elif "silver_key" in state["inventory"]:
            facts = C.TEXT["drawer_open_empty"]
        else:
            facts = C.TEXT["drawer_open_key"]
    elif target == "safe":
        if o["locked"]:
            facts = C.TEXT["safe_locked"]
        elif "parchment" in state["inventory"]:
            facts = C.TEXT["safe_open_empty"]
        else:
            facts = C.TEXT["safe_open_item"]
    else:  # door
        facts = C.TEXT["door_locked"]
    return _result(state, action, True, "examined", facts, changed)


def _take(state, action):
    target = action.get("target")
    if target in C.OBJECTS:
        if not object_visible(state, target):
            return _result(state, action, False, "not_found", "You don't see anything like that here.")
        return _result(state, action, False, "nothing_happens",
                       f"The {_name(target)} is far too heavy or fixed in place to take.")
    if target not in C.ITEMS:
        return _result(state, action, False, "not_found", "You don't see anything like that here.")
    if target in state["inventory"]:
        return _result(state, action, False, "already_done", f"You already carry the {_name(target)}.")
    if not item_accessible(state, target):
        return _result(state, action, False, "not_found",
                       f"You don't see any {_name(target)} here that you can reach.")
    state["inventory"].append(target)
    return _result(state, action, True, "item_taken", f"You take the {_name(target)}.", True)


def _unlock_safe(state, action):
    safe = state["objects"]["safe"]
    if not safe["locked"]:
        return _result(state, action, False, "already_done", "The safe is already open.")
    safe["locked"] = False
    safe["open"] = True
    state["puzzles"]["safe_key"] = True
    return _result(state, action, True, "safe_opened", C.TEXT["safe_unlocked"], True)


def _open(state, action):
    target = action.get("target")
    if target in C.ITEMS or not object_visible(state, target or ""):
        return _result(state, action, False, "not_found", "You don't see anything like that to open.")
    o = state["objects"][target]
    if target == "drawer":
        if o["open"]:
            return _result(state, action, False, "already_done", "The drawer is already open.")
        return _result(state, action, False, "locked",
                       "The drawer will not budge. It is locked by a four-digit dial.")
    if target == "safe":
        if o["open"]:
            return _result(state, action, False, "already_done", "The safe is already open.")
        if "silver_key" in state["inventory"]:
            return _unlock_safe(state, {**action, "action": "use", "item": "silver_key"})
        return _result(state, action, False, "locked", "The safe is locked. It has a keyhole.")
    if target == "door":
        return _result(state, action, False, "locked",
                       "The door will not open. It is secured by a four-digit keypad.")
    return _result(state, action, False, "nothing_happens", f"There is nothing to open on the {_name(target)}.")


def _use(state, action):
    item, target = action.get("item"), action.get("target")
    if item is None and target in C.ITEMS:  # "use the key" parsed as a target
        item, target = target, None
    if item is None:
        return _result(state, action, False, "need_target", "What do you want to use, and on what?")
    if item not in C.ITEMS:
        return _result(state, action, False, "not_found", "You have nothing like that to use.")
    if item not in state["inventory"]:
        return _result(state, action, False, "not_in_inventory",
                       f"You are not carrying a {_name(item)}. You can only use things you have collected.")
    if target is None:
        return _result(state, action, False, "need_target", f"Use the {_name(item)} on what?")
    if target in C.ITEMS:
        if target not in state["inventory"]:
            return _result(state, action, False, "not_in_inventory",
                           f"You are not carrying a {_name(target)}.")
    elif not object_visible(state, target):
        return _result(state, action, False, "not_found", "You don't see anything like that here.")

    rule = C.USE_RULES.get((item, target))
    if rule == "unlock_safe":
        return _unlock_safe(state, action)
    if rule == "decode_parchment":
        if state["puzzles"]["parchment_decoded"]:
            return _result(state, action, False, "already_done",
                           "You have already deciphered the parchment: 9, 3, 5, 8.")
        state["puzzles"]["parchment_decoded"] = True
        _add_clue(state, "door_code")
        return _result(state, action, True, "parchment_decoded", C.TEXT["decode_success"], True)
    if rule == "inspect_signature":
        return _result(state, action, True, "flavor", C.TEXT["signature"])
    return _result(state, action, False, "nothing_happens",
                   f"Using the {_name(item)} on the {_name(target)} does nothing.")


def _enter_code(state, action):
    target, code = action.get("target"), (action.get("code") or "")
    if target is None:
        return _result(state, action, False, "need_target", "Where do you want to enter that code?")
    if target not in ("drawer", "door") or not object_visible(state, target):
        return _result(state, action, False, "nothing_happens", "Nothing here takes a code.")
    if not code.isdigit() or len(code) != 4:
        return _result(state, action, False, "wrong_code", C.TEXT["code_length"])

    if target == "drawer":
        d = state["objects"]["drawer"]
        if d["open"]:
            return _result(state, action, False, "already_done", "The drawer is already open.")
        if code == C.SECRETS["drawer_code"]:
            d["locked"], d["open"] = False, True
            state["puzzles"]["drawer_code"] = True
            return _result(state, action, True, "drawer_opened", C.TEXT["drawer_unlocked"], True)
        d["failed_attempts"] += 1
        return _result(state, action, False, "wrong_code", C.TEXT["wrong_code"])

    door = state["objects"]["door"]
    if state["escaped"]:
        return _result(state, action, False, "already_done", "You have already escaped.")
    prerequisites_met = all(state["puzzles"][p] for p in C.DOOR_PREREQUISITES)
    if code == C.SECRETS["door_code"] and prerequisites_met:
        door["locked"] = False
        state["puzzles"]["door_code"] = True
        state["escaped"] = True
        return _result(state, action, True, "escaped", C.TEXT["escaped"], True)
    # Correct-but-premature codes are rejected exactly like wrong ones (no leak).
    door["failed_attempts"] += 1
    return _result(state, action, False, "wrong_code", C.TEXT["wrong_code"])


def _inventory(state, action):
    if state["inventory"]:
        facts = "You are carrying: " + ", ".join(_name(i) for i in state["inventory"]) + "."
    else:
        facts = "You are not carrying anything yet."
    return _result(state, action, True, "inventory", facts)


def _claim(state, action):
    """The player asserts progress. The state, not the claim, decides."""
    done = []
    if state["puzzles"]["drawer_code"]:
        done.append("the drawer is open")
    if state["puzzles"]["safe_key"]:
        done.append("the safe is open")
    if state["puzzles"]["parchment_decoded"]:
        done.append("the parchment is deciphered")
    if state["escaped"]:
        done.append("you have escaped")
    summary = ("So far " + ", ".join(done) + ".") if done else "So far no puzzle has been solved."
    holding = ("You carry: " + ", ".join(_name(i) for i in state["inventory"]) + ".") if state["inventory"] \
        else "You carry nothing."
    facts = f"That is not how things stand. {summary} {holding} Prove it with an action."
    return _result(state, action, False, "claim_rejected", facts)


def _hint(state, action):
    objs, puz, inv = state["objects"], state["puzzles"], state["inventory"]
    done = {
        "desk": objs["desk"]["examined"] > 0 and "magnifying_glass" in inv,
        "books": "book_numbers" in state["known_clues"],
        "drawer": puz["drawer_code"],
        "key": "silver_key" in inv or puz["safe_key"],
        "painting": objs["safe"]["revealed"],
        "safe": puz["safe_key"],
        "parchment": "parchment" in inv,
        "decode": puz["parchment_decoded"],
        "door": state["escaped"],
    }
    for stage, vague, explicit in C.HINTS:
        if not done[stage]:
            count = state["hint_counts"].get(stage, 0)
            state["hint_counts"][stage] = count + 1
            return _result(state, action, True, "hint", vague if count == 0 else explicit)
    return _result(state, action, True, "hint", "You have everything you need. The exit is yours.")


HANDLERS = {
    "look": _look, "examine": _examine, "take": _take, "open": _open, "use": _use,
    "enter_code": _enter_code, "inventory": _inventory, "claim": _claim, "hint": _hint,
}


def apply_action(state: dict, action: dict) -> dict:
    """Validate and apply one structured action. Returns {ok, event, facts, state_changed}.

    `action` is {"action", "target", "item", "code", "unknown"}. It may come from an
    LLM or from the player directly: this function trusts nothing in it.
    """
    kind = action.get("action")
    if state.get("escaped") and kind not in ("inventory", "look", "help", "meta", "hint"):
        return _result(state, action, False, "already_done", "You have already escaped. Press Restart to play again.")
    if kind == "meta":
        return _result(state, action, False, "refused", C.TEXT["refused"])
    if kind == "help":
        return _result(state, action, True, "help", C.HOW_TO_PLAY)
    if action.get("unknown"):
        return _result(state, action, False, "unknown_object",
                       f"You don't see anything called \"{action['unknown']}\" here.")
    handler = HANDLERS.get(kind)
    if handler is None:
        return _result(state, action, False, "not_understood", C.TEXT["not_understood"])
    return handler(state, action)


def progress(state: dict) -> list[tuple[str, bool]]:
    """Coarse checklist for the sidebar. Reveals no secrets."""
    p, o = state["puzzles"], state["objects"]
    return [
        ("Found the clue on the books", "book_numbers" in state["known_clues"]),
        ("Opened the drawer", p["drawer_code"]),
        ("Opened the wall safe", p["safe_key"]),
        ("Deciphered the parchment", p["parchment_decoded"]),
        ("Escaped the library", state["escaped"]),
    ]


def snapshot(state: dict) -> dict:
    return copy.deepcopy(state)
