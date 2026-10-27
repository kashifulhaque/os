"""Checks for the signals exercise.

These checks send real signals and start real processes. They assert only
outcomes that hold under every scheduling order. Every check puts back the
signal handlers it touches, and a watchdog thread kills stray children so a
mistake becomes a failure instead of a hang.
"""

import os
import signal
import sys
import threading
import time
from contextlib import contextmanager

from oscheck import check, equal, fail, has


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
def watchdog(seconds=5):
    """Kill this process's children if the code under test waits too long, and
    fail the check when it leaves a child behind. A thread is used because the
    code under test may use SIGALRM itself."""
    fired = []

    def bite():
        fired.append(True)
        for pid in _children():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    timer = threading.Timer(seconds, bite)
    timer.daemon = True
    timer.start()
    try:
        yield
    except BaseException:
        timer.cancel()
        _kill_and_reap_children()
        raise
    timer.cancel()
    timer.join(1)
    if fired:
        _kill_and_reap_children()
        fail(
            f"your code was still waiting after {seconds} seconds, so the checker killed its "
            "children. Does your function send the signal that ends the child, and then wait for it?"
        )
    leaked = _leftovers()
    if leaked:
        fail(
            f"{leaked} child process(es) were left running or unreaped when your function "
            "returned. Call os.waitpid for every child you fork."
        )


def handler_state(signum):
    return signal.getsignal(signum)


@check("describe_status puts exit codes and killing signals into words")
def test_describe(sub):
    describe_status = has(sub, "describe_status")
    equal(describe_status(0), "exited with code 0", label="describe_status(0)")
    equal(describe_status(3 << 8), "exited with code 3", label="describe_status(3 << 8)")
    equal(describe_status(9), "killed by SIGKILL (9)", label="describe_status(9)")
    equal(describe_status(15), "killed by SIGTERM (15)", label="describe_status(15)")
    equal(describe_status(2), "killed by SIGINT (2)", label="describe_status(2)")
    # Bit 7 (0x80) of a status means the process dumped core.
    equal(describe_status(11 | 0x80), "killed by SIGSEGV (11), core dumped", label="describe_status(11 | 0x80)")


@check("can_catch says SIGKILL and SIGSTOP cannot be caught, and leaves handlers alone")
def test_can_catch(sub):
    can_catch = has(sub, "can_catch")
    for name in ["SIGUSR1", "SIGUSR2", "SIGTERM", "SIGHUP", "SIGINT"]:
        signum = getattr(signal, name)
        before = handler_state(signum)
        equal(can_catch(signum), True, label=f"can_catch({name})")
        equal(handler_state(signum), before, label=f"handler of {name} after can_catch")
    for name in ["SIGKILL", "SIGSTOP"]:
        equal(can_catch(getattr(signal, name)), False, label=f"can_catch({name})")


@check("catch_signal receives a signal sent to its own process and restores the old handler")
def test_catch_signal(sub):
    catch_signal = has(sub, "catch_signal")
    for name in ["SIGUSR1", "SIGUSR2", "SIGTERM", "SIGHUP"]:
        signum = getattr(signal, name)
        before = handler_state(signum)
        equal(catch_signal(signum), [signum], label=f"catch_signal({name})")
        equal(handler_state(signum), before, label=f"handler of {name} after catch_signal")
    # A handler installed by the caller must come back, not be replaced by SIG_DFL.
    def marker(number, frame):
        pass

    old = signal.signal(signal.SIGUSR1, marker)
    try:
        catch_signal(signal.SIGUSR1)
        if signal.getsignal(signal.SIGUSR1) is not marker:
            fail("catch_signal did not put back the handler that was installed before the call")
    finally:
        signal.signal(signal.SIGUSR1, old)


@check("coalesced_count shows that pending signals do not queue")
def test_coalesced(sub):
    coalesced_count = has(sub, "coalesced_count")
    equal(coalesced_count(signal.SIGUSR1, 0), 0, label="coalesced_count(SIGUSR1, 0)")
    equal(coalesced_count(signal.SIGUSR1, 1), 1, label="coalesced_count(SIGUSR1, 1)")
    # Five sends while blocked leave one pending signal, so the handler runs once.
    equal(coalesced_count(signal.SIGUSR1, 5), 1, label="coalesced_count(SIGUSR1, 5)")
    equal(coalesced_count(signal.SIGUSR2, 20), 1, label="coalesced_count(SIGUSR2, 20)")
    blocked = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    if signal.SIGUSR1 in blocked:
        fail("SIGUSR1 is still blocked after coalesced_count returned; restore the signal mask")
    equal(handler_state(signal.SIGUSR1), signal.SIG_DFL, label="handler of SIGUSR1 after coalesced_count")


@check("kill_child returns a status that says the signal killed the child")
def test_kill_child(sub):
    kill_child = has(sub, "kill_child")
    with watchdog():
        for name in ["SIGTERM", "SIGKILL", "SIGUSR1", "SIGHUP"]:
            signum = getattr(signal, name)
            status = kill_child(signum)
            if not os.WIFSIGNALED(status):
                fail(f"kill_child({name}): status {status} does not say the child was killed by a signal")
            equal(os.WTERMSIG(status), signum, label=f"signal that killed the child for {name}")


@check("graceful_child exits with code 42 because its SIGTERM handler ran")
def test_graceful(sub):
    graceful_child = has(sub, "graceful_child")
    with watchdog():
        # Repeated, because a parent that signals too early only fails some of the time.
        for attempt in range(8):
            status = graceful_child()
            if not os.WIFEXITED(status):
                fail(
                    f"attempt {attempt}: status {status} says the child was killed by a signal. "
                    "The signal probably arrived before the handler was installed. "
                    "Wait for the child's ready byte before you call os.kill."
                )
            equal(os.WEXITSTATUS(status), 42, label=f"exit code of the child, attempt {attempt}")


@check("run_with_timeout returns the exit code of a program that finishes in time")
def test_timeout_fast(sub):
    run_with_timeout = has(sub, "run_with_timeout")
    with watchdog():
        equal(run_with_timeout(["sh", "-c", "exit 3"], 5), (False, 3), label="exit 3")
        equal(run_with_timeout(["true"], 5), (False, 0), label="true")
        equal(run_with_timeout(["false"], 5), (False, 1), label="false")
        equal(run_with_timeout(["no-such-program-xyz"], 5), (False, 127), label="a missing program")
        equal(run_with_timeout(["sh", "-c", "kill -9 $$"], 5), (False, 137), label="a child killed by its own SIGKILL")
        for i in range(10):
            equal(run_with_timeout(["true"], 5), (False, 0), label=f"repeat {i} of a quick program")


@check("run_with_timeout kills a program that runs too long")
def test_timeout_slow(sub):
    run_with_timeout = has(sub, "run_with_timeout")
    with watchdog():
        started = time.monotonic()
        result = run_with_timeout(["sleep", "30"], 0.3)
        elapsed = time.monotonic() - started
        equal(result, (True, 137), label="run_with_timeout(['sleep', '30'], 0.3)")
        if elapsed > 3:
            fail(f"the timeout was 0.3 seconds but the call took {elapsed:.1f} seconds")
        # A program that ignores SIGTERM still dies, because SIGKILL cannot be ignored.
        stubborn = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
        equal(run_with_timeout([sys.executable, "-c", stubborn], 0.5), (True, 137), label="a program that ignores SIGTERM")


@check("run_with_timeout restores SIGALRM and cancels its timer, whether or not it times out")
def test_timeout_cleanup(sub):
    run_with_timeout = has(sub, "run_with_timeout")

    def marker(number, frame):
        pass

    old = signal.signal(signal.SIGALRM, marker)
    try:
        with watchdog():
            for argv, seconds in [(["true"], 5), (["sleep", "30"], 0.2)]:
                run_with_timeout(argv, seconds)
                if signal.getsignal(signal.SIGALRM) is not marker:
                    fail(f"after run_with_timeout({argv}, {seconds}) the SIGALRM handler was not restored")
                left = signal.getitimer(signal.ITIMER_REAL)[0]
                if left != 0:
                    fail(f"after run_with_timeout({argv}, {seconds}) a timer is still running ({left:.2f} s left)")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
