"""The shape every execution backend shares."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

Event = dict[str, Any]


class RunnerError(RuntimeError):
    """A failure in the runner itself, as opposed to in the reader's code."""


@dataclass
class RunRequest:
    exercise_id: str
    mode: str  # "run" or "check"
    code: str
    timeout: int
