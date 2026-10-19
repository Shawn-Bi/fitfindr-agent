"""
Loads the example wardrobe used by run_eval.py and agent.py's demo.
Listings never come from here: they come from sources/ (live or recorded fixtures).
"""

import json
import os
from typing import Optional

# Resolve the path to the data directory relative to this file
_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_wardrobe_schema() -> dict:
    """
    Load the wardrobe schema, including the example wardrobe and empty template.

    Returns:
        A dictionary containing:
        - schema: the field definitions for a wardrobe item
        - example_wardrobe: a sample wardrobe with 10 items
        - empty_wardrobe: a starting template for a new user
    """
    path = os.path.join(_DATA_DIR, "wardrobe_schema.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _wardrobe(name: str) -> dict:
    """
    Pull one wardrobe out of the schema file, without the documentation keys.

    The JSON uses underscore-prefixed keys (_description, _note) to explain
    itself to a human reader. Those are notes about the file, not part of a
    wardrobe, and stripping them here means both wardrobes below come back
    the same shape. Otherwise the empty one carries an extra _note key, and a
    tool that formats the whole dict into a prompt would send the model a
    sentence about templates.
    """
    wardrobe = load_wardrobe_schema()[name]
    return {k: v for k, v in wardrobe.items() if not k.startswith("_")}


def get_example_wardrobe() -> dict:
    """
    Convenience function — returns just the example wardrobe items list.

    Returns:
        A wardrobe dict with an 'items' key containing a list of wardrobe items.
    """
    return _wardrobe("example_wardrobe")


def get_empty_wardrobe() -> dict:
    """
    Convenience function — returns an empty wardrobe template.

    Returns:
        A wardrobe dict with an empty 'items' list. Same shape as the example
        wardrobe — the only difference is that 'items' is empty.
    """
    return _wardrobe("empty_wardrobe")


# --- Quick sanity check ---
if __name__ == "__main__":
    wardrobe = get_example_wardrobe()
    print(f"Example wardrobe has {len(wardrobe['items'])} items.")
    print(f"First item: {wardrobe['items'][0]['name']}")
