"""Checks for the fork, exec, and wait exercise.

These checks start real processes. They assert only outcomes that hold under
every scheduling order, and they guard against hangs and leaked children.
"""

import os
import signal
import sys
import time
from contextlib import contextmanager

from oscheck import check, equal, fail, has


class _Timeout(BaseException):
    pass


def _children():
    """Pids whose parent is this process, read from /proc (Linux)."""
    mine = os.getpid()
    found = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat") as f:
                stat = f.read()
        except OSError:
            continue
        # The command name sits in parentheses and may hold spaces, so split after the last ")".
        if int(stat.rsplit(")", 1)[1].split()[1]) == mine:
            found.append(int(name))
    return found


def _kill_and_reap_children():
    """Kill and reap every child. Repeat, because a killed child's own children
    are adopted by this process when it is pid 1 in a container."""
    for _ in range(100):
        for pid in _children():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        try:
            while os.waitpid(-1, os.WNOHANG)[0]:
                pass
        except ChildProcessError:
            return
        time.sleep(0.02)


def _leftovers():
    """Reap what the reader forgot to wait for, and say how many children it was."""
    count = 0
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return count
        if pid == 0:  # a child is still running
            _kill_and_reap_children()
            return count + 1
        count += 1


@contextmanager
def guard(seconds=4):
    """Fail instead of hanging, and fail when the code under test leaks a child."""

    def on_alarm(signum, frame):
        raise _Timeout()

    old = signal.signal(signal.SIGALRM, on_alarm)
    signal.alarm(seconds)
    try:
        yield
    except _Timeout:
        _kill_and_reap_children()
        fail(
            f"your code was still running after {seconds} seconds. A common cause is a "
            "pipe write end that the parent never closed, so read() never sees end of file."
        )
    except BaseException:
        _kill_and_reap_children()
        raise
    else:
        signal.alarm(0)
        leaked = _leftovers()
        if leaked:
            fail(
                f"{leaked} child process(es) were left running or unreaped when your "
                "function returned. Call os.waitpid for every child you fork."
            )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


@check("decode_status and exit_code read raw wait statuses")
def test_decode(sub):
    decode_status = has(sub, "decode_status")
    exit_code = has(sub, "exit_code")
    # A normal exit stores the code in bits 8-15: code << 8.
    equal(decode_status(0), ("exited", 0), label="decode_status(0)")
    equal(decode_status(3 << 8), ("exited", 3), label="decode_status(3 << 8)")
    equal(decode_status(255 << 8), ("exited", 255), label="decode_status(255 << 8)")
    # A death by signal stores the signal number in the low 7 bits; bit 7 means a core dump.
    equal(decode_status(9), ("signaled", 9), label="decode_status(9)")
    equal(decode_status(15), ("signaled", 15), label="decode_status(15)")
    equal(decode_status(11 | 0x80), ("signaled", 11), label="decode_status(11 | 0x80)")
    equal(exit_code(0), 0, label="exit_code(0)")
    equal(exit_code(3 << 8), 3, label="exit_code(3 << 8)")
    equal(exit_code(9), 137, label="exit_code(9), 128 + 9")
    equal(exit_code(15), 143, label="exit_code(15), 128 + 15")


@check("who_am_i shows fork returning the child's pid to the parent and 0 to the child")
def test_who_am_i(sub):
    who_am_i = has(sub, "who_am_i")
    with guard():
        info = who_am_i()
    equal(sorted(info), ["child", "child_parent", "child_self", "parent"], label="keys of the returned dict")
    equal(info["parent"], os.getpid(), label="'parent' is this process's pid")
    equal(info["child_self"], info["child"], label="the child's own getpid() vs the pid fork returned")
    equal(info["child_parent"], info["parent"], label="the child's getppid() vs the parent's pid")
    if info["child"] == info["parent"]:
        fail("the child and the parent have the same pid, which cannot happen")


@check("fork_isolation shows that a child changes only its own copy of memory")
def test_isolation(sub):
    fork_isolation = has(sub, "fork_isolation")
    items = ["a", "b"]
    with guard():
        parent_items, child_items = fork_isolation(items)
    equal(parent_items, ["a", "b"], label="the parent's list after the child appended")
    equal(child_items, ["a", "b", "child"], label="the child's list")
    equal(items, ["a", "b"], label="the list object passed in")


@check("run_and_wait returns the exit code of the program")
def test_run_and_wait(sub):
    run_and_wait = has(sub, "run_and_wait")
    with guard():
        equal(run_and_wait(["true"]), 0, label="run_and_wait(['true'])")
        equal(run_and_wait(["false"]), 1, label="run_and_wait(['false'])")
        equal(run_and_wait(["sh", "-c", "exit 7"]), 7, label="run_and_wait(['sh', '-c', 'exit 7'])")
        equal(run_and_wait(["echo", "this goes to /dev/null"]), 0, label="run_and_wait(['echo', ...])")


@check("run_and_wait returns 127 for a missing program and 128 + N for a death by signal N")
def test_run_and_wait_failures(sub):
    run_and_wait = has(sub, "run_and_wait")
    with guard():
        equal(run_and_wait(["no-such-program-xyz"]), 127, label="run_and_wait of a missing program")
        equal(run_and_wait(["sh", "-c", "kill -9 $$"]), 137, label="a child that kills itself with SIGKILL")
        equal(run_and_wait(["sh", "-c", "kill -15 $$"]), 143, label="a child that kills itself with SIGTERM")


@check("run_capture returns the exit code and what the program wrote to stdout and stderr")
def test_capture(sub):
    run_capture = has(sub, "run_capture")
    with guard():
        equal(run_capture(["echo", "hello"]), (0, b"hello\n"), label="run_capture(['echo', 'hello'])")
        equal(run_capture(["echo", "a  b", "c"]), (0, b"a  b c\n"), label="arguments reach the program unchanged")
        equal(run_capture(["true"]), (0, b""), label="a program that prints nothing")
        code, out = run_capture(["sh", "-c", "echo out; echo err >&2; exit 4"])
    equal((code, out), (4, b"out\nerr\n"), label="stdout and stderr together, with exit code 4")


@check("run_capture reads more output than a pipe can hold")
def test_capture_large(sub):
    run_capture = has(sub, "run_capture")
    # A pipe holds 64 KiB on Linux. 300000 bytes forces the child to block until the parent reads.
    program = "import sys; sys.stdout.write('x' * 300000)"
    with guard():
        code, out = run_capture([sys.executable, "-c", program])
    equal(code, 0, label="exit code of the large writer")
    equal(len(out), 300000, label="number of bytes captured (read before you wait)")


@check("run_capture gives 127 for a missing program and shows the signal for a killed one")
def test_capture_failures(sub):
    run_capture = has(sub, "run_capture")
    with guard():
        code, out = run_capture(["no-such-program-xyz"])
        equal(code, 127, label="exit code for a missing program")
        equal(out, b"", label="output for a missing program")
        equal(run_capture(["sh", "-c", "echo before; kill -9 $$"]), (137, b"before\n"), label="killed after printing")


@check("fork_many returns results ordered by i, even when children finish out of order")
def test_fork_many(sub):
    fork_many = has(sub, "fork_many")

    def slow_first(i):
        # Child 0 sleeps longest, so it finishes last. The results must still start with its value.
        time.sleep((5 - i) * 0.03)
        return i * 10 + 1

    with guard():
        equal(fork_many(0, lambda i: i), [], label="fork_many(0, ...)")
        equal(fork_many(1, lambda i: 42), [42], label="fork_many(1, ...)")
        equal(fork_many(6, lambda i: i * i), [0, 1, 4, 9, 16, 25], label="fork_many(6, square)")
        equal(fork_many(5, slow_first), [1, 11, 21, 31, 41], label="fork_many(5, slow_first)")
        equal(fork_many(3, lambda i: -i), [0, -1, -2], label="negative results")


@check("fork_many raises RuntimeError when a child fails, after reaping every child")
def test_fork_many_failure(sub):
    fork_many = has(sub, "fork_many")

    def boom_on_two(i):
        if i == 2:
            raise ValueError("child 2 fails")
        return i

    with guard():
        try:
            fork_many(5, boom_on_two)
        except NotImplementedError:
            raise  # NotImplementedError is a RuntimeError, so let it through as a failure
        except RuntimeError:
            pass
        else:
            fail("fork_many should raise RuntimeError when one child raises, but it returned normally")
        # guard() fails this check if any of the five children is left unreaped.
