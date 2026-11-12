"""Deterministic game engine for Version 2.

Python owns the truth: the state, the rules and the solutions. The LLM never
decides whether an action succeeds; it only (a) translates player text into a
structured action and (b) narrates the result this engine returns.
"""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("game_config.json")

# The only actions the engine will ever execute. Anything else is rejected.
VALID_ACTIONS = {"look", "examine", "take", "use", "enter_code", "inventory", "hint", "help", "unknown"}


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def new_state() -> dict:
    """Structured, JSON-serialisable game state."""
    return {
        "flags": {
            "note_read": False,
            "books_examined": False,
            "painting_examined": False,
            "key_visible": False,
            "key_taken": False,
            "drawer_key_used": False,
            "drawer_open": False,
            "paper_taken": False,
            "door_unlocked": False,
            "escaped": False,
        },
        "inventory": [],
        "solved_puzzles": [],   # "find_key", "open_drawer", "exit_door"
        "failed_codes": {"drawer": 0, "door": 0},
        "turns": 0,
    }


@dataclass
class Result:
    """Outcome of one action. `message` is the canonical, always-true text."""
    ok: bool
    message: str
    action: dict = field(default_factory=dict)
    state_changed: bool = False


class Game:
    def __init__(self, config: dict | None = None, state: dict | None = None):
        self.cfg = config or load_config()
        self.state = state or new_state()

    # ------------------------------------------------------------------ helpers
    @property
    def flags(self) -> dict:
        return self.state["flags"]

    def snapshot(self) -> dict:
        return copy.deepcopy(self.state)

    def _resolve_object(self, name: str | None) -> str | None:
        if not name:
            return None
        n = name.lower().strip()
        for key, obj in self.cfg["objects"].items():
            if n == key or n in obj["aliases"]:
                return key
        return None

    def _resolve_item(self, name: str | None) -> str | None:
        if not name:
            return None
        n = name.lower().strip()
        for key, item in self.cfg["items"].items():
            if n == key or n in item["aliases"]:
                return key
        return None

    @staticmethod
    def _norm_code(code) -> str | None:
        if code is None:
            return None
        digits = re.sub(r"\D", "", str(code))
        return digits if len(digits) == 4 else None

    def _solve(self, puzzle: str) -> None:
        if puzzle not in self.state["solved_puzzles"]:
            self.state["solved_puzzles"].append(puzzle)

    # --------------------------------------------------------------- main entry
    def apply(self, action: dict) -> Result:
        """Validate and execute one structured action."""
        act = (action or {}).get("action", "unknown")
        if act not in VALID_ACTIONS:
            act = "unknown"
        action = {**action, "action": act}

        if self.flags["escaped"]:
            return Result(True, "You have already escaped. Press Restart to play again.", action)

        handler = getattr(self, f"_do_{act}")
        before = json.dumps(self.state, sort_keys=True)
        res = handler(action)
        res.action = action
        if act != "unknown":
            self.state["turns"] += 1
        res.state_changed = json.dumps(self.state, sort_keys=True) != before
        return res

    # ----------------------------------------------------------------- handlers
    def _do_unknown(self, a: dict) -> Result:
        reason = a.get("reason")
        if reason == "override":
            return Result(False, "The rules of this room cannot be changed by talking. Only what you actually do in the room counts.")
        if reason == "reveal":
            return Result(False, "The room keeps its secrets until you find them yourself. Try examining things, or ask for a hint.")
        return Result(False, "That is not something you can do here. Try examining an object, taking or using an item, or entering a code.")

    def _do_help(self, a: dict) -> Result:
        return Result(True, "You can examine objects, take items, use items on objects, enter four-digit codes, check your inventory, or ask for a hint.")

    def _do_look(self, a: dict) -> Result:
        return Result(True, self.cfg["intro"])

    def _do_inventory(self, a: dict) -> Result:
        inv = self.state["inventory"]
        if not inv:
            return Result(True, "You are carrying nothing.")
        return Result(True, "You are carrying: " + ", ".join(inv) + ".")

    def _do_hint(self, a: dict) -> Result:
        for h in self.cfg["hints"]:
            if not self.flags.get(h["if_not"], False):
                return Result(True, "Hint: " + h["text"])
        return Result(True, "Hint: you have everything you need.")

    def _do_examine(self, a: dict) -> Result:
        target = a.get("target")
        obj = self._resolve_object(target)
        item = self._resolve_item(target)
        if item and item in self.state["inventory"]:
            return Result(True, self.cfg["items"][item]["description"])
        if obj is None:
            if item:  # exists but not collected / not seen
                return Result(False, f"You don't have a {item}, and you haven't found one.")
            return Result(False, f"There is no '{target}' in this room.")
        o = self.cfg["objects"][obj]
        if obj == "drawer":
            return Result(True, o["examine_open"] if self.flags["drawer_open"] else o["examine_locked"])
        for flag in o.get("sets", []):
            self.flags[flag] = True
        msg = o["examine"]
        if obj == "painting" and self.flags["key_taken"]:
            msg = "A stern portrait of the library's founder. The frame plate reads 'Founded 1847'. The back of the canvas bears a patch of tape where the key was."
        return Result(True, msg)

    def _do_take(self, a: dict) -> Result:
        target = a.get("item") or a.get("target")
        item = self._resolve_item(target)
        if item is None:
            return Result(False, f"There is no '{target}' you can take.")
        if item in self.state["inventory"]:
            return Result(False, f"You already have the {item}.")
        it = self.cfg["items"][item]
        if not self.flags.get(it["requires_flag"], False):
            return Result(False, f"You haven't found any {item} yet.")
        self.state["inventory"].append(item)
        if item == "brass key":
            self.flags["key_taken"] = True
            self._solve("find_key")
        if item == "folded paper":
            self.flags["paper_taken"] = True
        return Result(True, it["take_message"])

    def _do_use(self, a: dict) -> Result:
        item = self._resolve_item(a.get("item"))
        obj = self._resolve_object(a.get("target"))
        if item is None:
            return Result(False, f"You have no '{a.get('item')}'.")
        if item not in self.state["inventory"]:
            return Result(False, f"You don't have the {item}. You need to find and take it first.")
        if obj is None:
            return Result(False, f"There is no '{a.get('target')}' to use the {item} on.")
        if item == "brass key" and obj == "drawer":
            if self.flags["drawer_key_used"]:
                return Result(False, "The key is already turned in the lock.")
            self.flags["drawer_key_used"] = True
            return Result(True, "The brass key turns with a click. The dial still needs a four-digit code.")
        return Result(False, f"Using the {item} on the {obj} does nothing.")

    def _do_enter_code(self, a: dict) -> Result:
        code = self._norm_code(a.get("code"))
        obj = self._resolve_object(a.get("target")) or "door"
        if code is None:
            return Result(False, "A code must be exactly four digits.")
        if obj == "drawer":
            return self._code_drawer(code)
        if obj == "door":
            return self._code_door(code)
        return Result(False, f"The {obj} has no keypad or dial.")

    def _code_drawer(self, code: str) -> Result:
        if self.flags["drawer_open"]:
            return Result(False, "The drawer is already open.")
        if not self.flags["drawer_key_used"]:
            return Result(False, "The drawer is still locked by its keyhole. The dial alone won't open it.")
        if code == self.cfg["solutions"]["drawer_code"]:
            self.flags["drawer_open"] = True
            self._solve("open_drawer")
            return Result(True, "The dial clicks and the drawer slides open. Inside lies a folded paper.")
        self.state["failed_codes"]["drawer"] += 1
        return Result(False, "The dial spins but the drawer stays locked. Wrong code.")

    def _code_door(self, code: str) -> Result:
        ready = self.flags["drawer_open"] and self.flags["books_examined"]
        if ready and code == self.cfg["solutions"]["door_code"]:
            self.flags["door_unlocked"] = True
            self.flags["escaped"] = True
            self._solve("exit_door")
            return Result(True, "The keypad chimes, the lock releases and the door swings open. You step out into the cold night air. You have escaped!")
        self.state["failed_codes"]["door"] += 1
        return Result(False, "The keypad buzzes angrily. The door stays locked.")
