"""The assertion vocabulary an exercise's `tests.py` writes against.

A check is a function registered with `@check`, taking the reader's module as its
only argument. It passes by returning and fails by raising `CheckFailure`, which
the helpers here raise on your behalf with a message the reader can act on.

The harness imports this module under the name `oscheck` and reads `REGISTRY`.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


class CheckFailure(AssertionError):
    """Raised when a check's expectation is not met."""


@dataclass
class Check:
    description: str
    func: Callable[[Any], None]
    timings: dict[str, float] = field(default_factory=dict)


REGISTRY: list[Check] = []

# Populated by `timed`, drained by the harness after each check.
_TIMINGS: dict[str, float] = {}


def check(description: str) -> Callable[[Callable[[Any], None]], Callable[[Any], None]]:
    """Register a check. The description is the line the reader sees."""

    def decorate(func: Callable[[Any], None]) -> Callable[[Any], None]:
        REGISTRY.append(Check(description=description, func=func))
        return func

    return decorate


def fail(message: str) -> None:
    """Fail the current check with `message`."""
    raise CheckFailure(message)


def _describe(value: Any, limit: int = 600) -> str:
    text = repr(value)
    if len(text) > limit:
        text = text[: limit - 20] + " ... " + text[-15:]
    return text


def _label(label: str | None) -> str:
    return f"{label}: " if label else ""


def _floats(value: Any) -> list[float]:
    if isinstance(value, (int, float)):
        return [float(value)]
    return [float(v) for v in value]


def close(
    got: Any,
    want: Any,
    rtol: float = 1e-5,
    atol: float = 1e-8,
    label: str | None = None,
) -> None:
    """Fail unless two numbers or flat sequences of numbers agree within tolerance."""
    try:
        got_f = _floats(got)
    except (TypeError, ValueError):
        fail(f"{_label(label)}expected numbers, got {_describe(got)}")
    want_f = _floats(want)
    if len(got_f) != len(want_f):
        fail(
            f"{_label(label)}got {len(got_f)} values, expected {len(want_f)}.\n"
            f"  got:  {_describe(got)}\n"
            f"  want: {_describe(want)}"
        )
    for i, (g, w) in enumerate(zip(got_f, want_f)):
        # Written as `not <=` so that a NaN fails rather than slipping past.
        if not abs(g - w) <= atol + rtol * abs(w):
            fail(
                f"{_label(label)}value {i} is {g:.6g}, expected {w:.6g} "
                f"(rtol={rtol:g}, atol={atol:g}).\n"
                f"  got:  {_describe(got)}\n"
                f"  want: {_describe(want)}"
            )


def almost(got: Any, want: Any, tol: float, label: str | None = None) -> None:
    """Fail unless two scalars agree within `tol`."""
    got_f = float(got)
    want_f = float(want)
    if not abs(got_f - want_f) <= tol:
        fail(
            f"{_label(label)}got {got_f:.6g}, expected {want_f:.6g} within {tol:g}"
        )


def equal(got: Any, want: Any, label: str | None = None) -> None:
    """Fail unless two values are equal with `==`.

    A tuple and a list holding the same items count as equal, because readers
    often return one where the other was described.
    """
    if _normalise(got) == _normalise(want):
        return
    fail(
        f"{_label(label)}values differ.\n"
        f"  got:  {_describe(got)}\n"
        f"  want: {_describe(want)}"
    )


def _normalise(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    return value


def has(module: Any, name: str) -> Any:
    """Return `module.name`, failing with a readable message when it is missing."""
    if not hasattr(module, name):
        fail(f"your module defines no `{name}`")
    return getattr(module, name)


@contextmanager
def timed(label: str) -> Iterator[None]:
    """Record how long a block takes, and report it beside the check."""
    start = time.perf_counter()
    try:
        yield
    finally:
        _TIMINGS[label] = time.perf_counter() - start


def drain_timings() -> dict[str, float]:
    """Take and clear the timings recorded since the last call."""
    taken = dict(_TIMINGS)
    _TIMINGS.clear()
    return taken
