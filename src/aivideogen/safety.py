"""Prompt guard: she is an adult and is never to be depicted as a minor.

Every prompt that reaches an image or video model (dataset synthesis, training samples, generation) goes
through :func:`check_prompt`.
"""

from __future__ import annotations

import re

_MINOR_PATTERNS = [
    r"\bunder-?age\b",
    r"\bpre-?teens?\b",
    r"\bteen(s|age|aged|ager|agers)?\b",
    r"\bschool ?girls?\b",
    r"\blittle girls?\b",
    r"\byoung girls?\b",
    r"\bchild-?like\b",
    r"\bloli\w*",
    r"\bjailbait\b",
    r"\bas an? (child|kid|toddler|baby|minor)\b",
    r"\b(1[0-7]|[1-9])\s*(-|\s)?\s*(years?|yrs?)\s*(-|\s)?\s*old\b",
    r"\b(1[0-7]|[1-9])\s*y/?o\b",
    r"\baged?\s+(1[0-7]|[1-9])\b",
]
_MINOR_RE = re.compile("|".join(_MINOR_PATTERNS), re.IGNORECASE)


class UnsafePromptError(ValueError):
    pass


def check_prompt(prompt: str) -> str:
    """Return the prompt unchanged, or raise if it describes her as (or like) a minor."""
    match = _MINOR_RE.search(prompt)
    if match:
        raise UnsafePromptError(
            f"Prompt rejected ({match.group(0)!r}): the character is an adult "
            "and can't be depicted as a minor. "
            "Describe her as a young woman instead."
        )
    return prompt
