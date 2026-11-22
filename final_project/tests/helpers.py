"""Shared helpers for Lab 05 tests."""

import pytest

from stack.outputs import load_outputs


def deployed_stack():
    """Read the saved AWS deployment information."""
    try:
        outputs = load_outputs()
    except (FileNotFoundError, OSError):
        pytest.skip(
            "Stack is not deployed yet. Run create_stack.py first."
        )

    if not outputs:
        pytest.skip("No deployment information found.")

    return outputs
