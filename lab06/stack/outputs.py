"""Save and load AWS stack outputs."""

import json
from pathlib import Path


OUTPUT_FILE = Path("stack_outputs.json")


def save_outputs(outputs: dict, path=OUTPUT_FILE):
    """Save stack information to a JSON file."""
    Path(path).write_text(
        json.dumps(outputs, indent=2) + "\n"
    )


def load_outputs(path=OUTPUT_FILE):
    """Read saved stack information."""
    file = Path(path)

    if not file.exists():
        return {}

    return json.loads(file.read_text())
