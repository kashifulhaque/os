"""Checks for the tiny shell exercise.

These checks start real processes and pipes. They assert only outcomes that
hold under every scheduling order, and they guard against hangs, leaked file
descriptors, and leaked children.
"""

import os
import shutil
import signal
import sys
import tempfile
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
            f"your code was still running after {seconds} seconds. Two common causes: a pipe "
            "write end that the parent (or a sibling child) still holds open, so a reader never "
            "sees end of file; and a producer that never stops because SIGPIPE is still "
            "ignored in the child."
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


def argvs(commands):
    return [c.argv for c in commands]


def expect_syntax_error(sub, line):
    parse_pipeline = has(sub, "parse_pipeline")
    ShellSyntaxError = has(sub, "ShellSyntaxError")
    try:
        result = parse_pipeline(line)
    except ShellSyntaxError:
        return
    fail(f"parse_pipeline({line!r}) should raise ShellSyntaxError, but returned {result!r}")


def open_fd_count():
    return len(os.listdir("/proc/self/fd"))


@contextmanager
def workdir():
    path = tempfile.mkdtemp()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@check("parse_pipeline reads a single command and an empty line")
def test_parse_single(sub):
    parse_pipeline = has(sub, "parse_pipeline")
    Command = has(sub, "Command")
    equal(parse_pipeline(""), [], label="parse_pipeline('')")
    equal(parse_pipeline("   "), [], label="parse_pipeline of spaces")
    got = parse_pipeline("ls -l /tmp")
    equal(len(got), 1, label="number of stages in 'ls -l /tmp'")
    equal(got[0].argv, ["ls", "-l", "/tmp"], label="argv of 'ls -l /tmp'")
    equal((got[0].stdin_path, got[0].stdout_path), (None, None), label="redirections of 'ls -l /tmp'")
    equal(got[0], Command(["ls", "-l", "/tmp"]), label="the whole Command")


@check("parse_pipeline splits stages at |, with or without spaces")
def test_parse_pipe(sub):
    parse_pipeline = has(sub, "parse_pipeline")
    equal(argvs(parse_pipeline("cat a.txt | sort | wc -l")), [["cat", "a.txt"], ["sort"], ["wc", "-l"]], label="three stages")
    equal(argvs(parse_pipeline("echo hi|tr a-z A-Z")), [["echo", "hi"], ["tr", "a-z", "A-Z"]], label="pipe without spaces")


@check("parse_pipeline reads < and > redirections and quoted words")
def test_parse_redirects(sub):
    parse_pipeline = has(sub, "parse_pipeline")
    Command = has(sub, "Command")
    equal(
        parse_pipeline("sort < in.txt > out.txt"),
        [Command(["sort"], "in.txt", "out.txt")],
        label="sort < in.txt > out.txt",
    )
    equal(
        parse_pipeline("cat < a | head -n 2 >b"),
        [Command(["cat"], "a", None), Command(["head", "-n", "2"], None, "b")],
        label="redirections in a pipeline, with `>b` unspaced",
    )
    equal(
        parse_pipeline("> out echo hi"),
        [Command(["echo", "hi"], None, "out")],
        label="a redirection before the command",
    )
    equal(
        argvs(parse_pipeline("echo 'a | b' \"c > d\" ''")),
        [["echo", "a | b", "c > d", ""]],
        label="quoted operators stay inside words",
    )


@check("parse_pipeline raises ShellSyntaxError on malformed lines")
def test_parse_errors(sub):
    for line in ["| ls", "ls |", "ls | | wc", "a || b", "ls >", "ls < ", "ls > | wc", "echo 'abc", "> out"]:
        expect_syntax_error(sub, line)


@check("run_pipeline runs one command and reports its output and exit code")
def test_run_single(sub):
    run_pipeline = has(sub, "run_pipeline")
    Command = has(sub, "Command")
    with guard():
        equal(run_pipeline([]), (0, b""), label="run_pipeline([])")
        equal(run_pipeline([Command(["echo", "hello"])]), (0, b"hello\n"), label="echo hello")
        equal(run_pipeline([Command(["false"])]), (1, b""), label="false")
        equal(run_pipeline([Command(["no-such-program-xyz"])]), (127, b""), label="a missing program")
        equal(run_pipeline([Command(["sh", "-c", "echo out; echo err >&2"])]), (0, b"out\n"), label="stderr is discarded")


@check("run_line connects commands with pipes")
def test_run_pipe(sub):
    run_line = has(sub, "run_line")
    with guard():
        equal(run_line("echo hello world | tr a-z A-Z"), (0, b"HELLO WORLD\n"), label="echo | tr")
        equal(run_line("echo one two three | wc -w"), (0, b"3\n"), label="echo | wc -w")
        # sort puts a, b, c in order; head keeps the first two lines.
        line = "sh -c 'echo b; echo a; echo c' | sort | head -n 2"
        equal(run_line(line), (0, b"a\nb\n"), label=line)
        equal(run_line("echo a | cat | cat | cat | wc -l"), (0, b"1\n"), label="five-stage pipeline")


@check("the exit code of a pipeline is the exit code of its last command")
def test_run_status(sub):
    run_line = has(sub, "run_line")
    with guard():
        equal(run_line("false | true")[0], 0, label="false | true")
        equal(run_line("true | false")[0], 1, label="true | false")
        equal(run_line("echo x | no-such-program-xyz"), (127, b""), label="echo | missing program")
        equal(run_line("echo x | sh -c 'cat >/dev/null; exit 9'")[0], 9, label="exit 9 at the end")


@check("run_line applies < and > redirections, and a redirection overrides a pipe")
def test_run_redirects(sub):
    run_line = has(sub, "run_line")
    with workdir() as d, guard():
        out = os.path.join(d, "out.txt")
        inp = os.path.join(d, "in.txt")
        equal(run_line(f"echo hi > {out}"), (0, b""), label="echo hi > file: nothing reaches the pipe")
        with open(out, "rb") as f:
            equal(f.read(), b"hi\n", label="contents of the redirect target")
        with open(inp, "wb") as f:
            f.write(b"b\na\n")
        equal(run_line(f"cat < {inp} | tr a-z A-Z"), (0, b"B\nA\n"), label="cat < file | tr")
        equal(run_line(f"sort < {inp} > {out}"), (0, b""), label="sort < in > out")
        with open(out, "rb") as f:
            equal(f.read(), b"a\nb\n", label="contents after sort < in > out")
        # The `>` replaces the pipe on echo's stdout, so cat sees end of file at once.
        equal(run_line(f"echo again > {out} | cat"), (0, b""), label="echo > file | cat")
        with open(out, "rb") as f:
            equal(f.read(), b"again\n", label="contents after echo again > file | cat")
        equal(run_line(f"cat < {d}/missing.txt")[0], 1, label="a missing input file gives exit code 1")


@check("a pipeline moves more data than a pipe holds, and leaks no file descriptors")
def test_big_and_leaks(sub):
    run_line = has(sub, "run_line")
    program = "print('x' * 199999)"
    line = f"'{sys.executable}' -c \"{program}\" | wc -c"
    with guard():
        before = open_fd_count()
        equal(run_line(line), (0, b"200000\n"), label="200000 bytes through a pipe into wc -c")
        for _ in range(5):
            run_line("echo a | cat | wc -c")
        after = open_fd_count()
    equal(after, before, label="open file descriptors before and after six pipelines")


@check("a producer stops when its reader exits (SIGPIPE is restored in the child)")
def test_sigpipe(sub):
    run_line = has(sub, "run_line")
    with guard():
        # The loop never ends on its own. head -n 3 exits, the pipe closes, and SIGPIPE kills sh.
        line = "sh -c 'while true; do echo y; done' | head -n 3"
        equal(run_line(line), (0, b"y\ny\ny\n"), label=line)
