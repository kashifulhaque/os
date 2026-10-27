"""The backend that executes a reader's submission and streams the result.

Only the `local` runner exists: it runs the code in a subprocess inside this
container, under CPU, file-size, and process limits. It exposes an async
generator of event dictionaries. The event types are `status`, `plan`,
`stdout`, `stderr`, `check`, `error`, and `done`.
"""

from .base import Event, RunRequest, RunnerError
from .local import run_local

__all__ = ["Event", "RunRequest", "RunnerError", "run_local"]
