"""Signals: handlers, os.kill, wait statuses, and a command timeout.

`exit_code` is given. Fill in everything else. Never let a function leave a
signal handler, a signal mask, or a timer behind, and reap every child.

The harness reserves file descriptor 1 for its own messages, so a child sends
messages through a pipe and runs programs with stdout and stderr on os.devnull.
"""

import os
import signal
import time


def exit_code(status: int) -> int:
    """Raw wait status to shell exit code: the code, or 128 + N for death by signal N."""
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return status


def describe_status(status: int) -> str:
    """Describe a raw wait status in words, the way a shell would.

    A normal exit gives "exited with code N". A death by signal gives
    "killed by SIGNAME (N)", with ", core dumped" added when the process
    dumped core (`os.WCOREDUMP`). Name the signal with `signal.Signals`.

    >>> describe_status(3 << 8)
    'exited with code 3'
    >>> describe_status(9)
    'killed by SIGKILL (9)'
    >>> describe_status(11 | 0x80)
    'killed by SIGSEGV (11), core dumped'
    """
    raise NotImplementedError


def can_catch(signum: int) -> bool:
    """Return True if a Python handler can be installed for `signum`.

    Try to install a handler. Return False if the kernel refuses (SIGKILL and
    SIGSTOP). Put the old handler back before you return, whatever happens.

    >>> can_catch(signal.SIGUSR1)
    True
    >>> can_catch(signal.SIGKILL)
    False
    """
    raise NotImplementedError


def catch_signal(signum: int) -> list:
    """Install a handler, send `signum` to this process, and return what the handler saw.

    The handler appends the signal number it receives to a list. Send the
    signal with `os.kill(os.getpid(), signum)`. Return the list, so one
    delivery gives `[signum]`. Restore the previous handler before returning.

    >>> catch_signal(signal.SIGUSR1)
    [10]
    """
    raise NotImplementedError


def coalesced_count(signum: int, n: int) -> int:
    """Send `signum` to this process `n` times while it is blocked, then count handler runs.

    Block `signum` with `signal.pthread_sigmask`, send it `n` times to yourself,
    then unblock it, so every copy is sent before any is delivered. The handler
    counts how many times it runs. Return that count. Restore the handler and
    the signal mask before returning.

    >>> coalesced_count(signal.SIGUSR1, 5)
    1
    """
    raise NotImplementedError


def kill_child(signum: int) -> int:
    """Fork a child that waits forever, kill it with `signum`, and return its raw wait status.

    The child loops on `time.sleep`. The parent sends `signum` with `os.kill`
    and reaps the child with `os.waitpid`. Use signals whose default action is
    to terminate (SIGTERM, SIGKILL, SIGUSR1, SIGHUP).

    >>> os.WTERMSIG(kill_child(signal.SIGTERM))
    15
    """
    raise NotImplementedError


def graceful_child() -> int:
    """Fork a child that handles SIGTERM by exiting with code 42; return its raw wait status.

    The child installs a SIGTERM handler that calls `os._exit(42)`, then tells
    the parent it is ready by writing one byte to a pipe, then waits. The parent
    must not send SIGTERM until it has read that byte, or the signal can arrive
    before the handler exists. Then the parent sends SIGTERM and reaps the child.

    >>> os.WEXITSTATUS(graceful_child())
    42
    """
    raise NotImplementedError


def run_with_timeout(argv: list, seconds: float) -> tuple:
    """Run `argv` and stop it if it takes longer than `seconds`.

    Return `(timed_out, code)`. `code` is the child's exit code as `exit_code`
    computes it, and 127 if the program cannot be started. On a timeout, kill
    the child with SIGKILL, reap it, and return `(True, 137)`. The child's
    stdout and stderr go to os.devnull. Use SIGALRM (`signal.setitimer`) for
    the timer, and restore the old SIGALRM handler and cancel the timer before
    you return.

    >>> run_with_timeout(["sh", "-c", "exit 3"], 5)
    (False, 3)
    >>> run_with_timeout(["sleep", "30"], 0.2)
    (True, 137)
    """
    raise NotImplementedError


if __name__ == "__main__":
    print("describe:", describe_status(3 << 8), "|", describe_status(9), "|", describe_status(11 | 0x80))
    print("can_catch USR1, KILL:", can_catch(signal.SIGUSR1), can_catch(signal.SIGKILL))
    print("catch_signal:", catch_signal(signal.SIGUSR1))
    print("five sends, handler runs:", coalesced_count(signal.SIGUSR1, 5))
    print("kill_child:", describe_status(kill_child(signal.SIGTERM)))
    print("graceful_child:", describe_status(graceful_child()))
    started = time.monotonic()
    print("timeout:", run_with_timeout(["sleep", "30"], 0.3), f"after {time.monotonic() - started:.1f}s")
