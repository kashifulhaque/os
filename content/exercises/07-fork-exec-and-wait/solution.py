"""Reference solution. Real processes: fork, exec, wait, and pipes.

Every function here talks to the Linux kernel. The harness reserves file
descriptor 1 for its own messages, so a child must never print to the
inherited stdout. It sends output through a pipe instead.

`read_all` is given. Fill in everything else.
"""

import json
import os


def read_all(fd: int) -> bytes:
    """Read from `fd` until end of file and return everything as bytes.

    End of file arrives only after every copy of the pipe's write end is closed.
    """
    chunks = []
    while True:
        data = os.read(fd, 65536)
        if not data:
            return b"".join(chunks)
        chunks.append(data)


def decode_status(status: int) -> tuple:
    """Decode a raw wait status from os.waitpid.

    Return ("exited", code) for a normal exit, or ("signaled", signum) when a
    signal killed the process. Return ("other", status) for anything else.

    >>> decode_status(3 << 8)
    ('exited', 3)
    >>> decode_status(9)
    ('signaled', 9)
    """
    if os.WIFEXITED(status):
        return ("exited", os.WEXITSTATUS(status))
    if os.WIFSIGNALED(status):
        return ("signaled", os.WTERMSIG(status))
    return ("other", status)


def exit_code(status: int) -> int:
    """Turn a raw wait status into a shell-style exit code.

    A normal exit gives its code. A death by signal N gives 128 + N, the
    number a shell reports in `$?`. Use `decode_status`.

    >>> exit_code(3 << 8)
    3
    >>> exit_code(9)
    137
    """
    kind, value = decode_status(status)
    if kind == "exited":
        return value
    if kind == "signaled":
        return 128 + value
    return status


def who_am_i() -> dict:
    """Fork one child and report the process ids both sides see.

    Return a dict with four keys: "parent" (the parent's os.getpid()), "child"
    (the pid that os.fork returned in the parent), "child_self" (the child's
    own os.getpid()), and "child_parent" (the child's os.getppid()). The child
    sends its two numbers to the parent through a pipe as JSON. Reap the child.
    """
    parent_pid = os.getpid()
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        # Child: report its own view, then leave without returning.
        try:
            os.close(r)
            message = {"child_self": os.getpid(), "child_parent": os.getppid()}
            os.write(w, json.dumps(message).encode())
            os.close(w)
        finally:
            os._exit(0)
    # Parent: close the write end so read_all can see end of file.
    os.close(w)
    data = read_all(r)
    os.close(r)
    os.waitpid(pid, 0)
    info = json.loads(data)
    return {"parent": parent_pid, "child": pid, **info}


def fork_isolation(items: list) -> tuple:
    """Show that a forked child gets its own copy of memory.

    Fork a child that appends the string "child" to `items` and sends the list
    back through a pipe as JSON. Return `(parent_items, child_items)`, where
    `parent_items` is `items` as the parent sees it after the child has been
    reaped. Appending in the child must not change the parent's list.

    >>> fork_isolation(["a"])
    (['a'], ['a', 'child'])
    """
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(r)
            items.append("child")  # changes the child's copy only
            os.write(w, json.dumps(items).encode())
            os.close(w)
        finally:
            os._exit(0)
    os.close(w)
    data = read_all(r)
    os.close(r)
    os.waitpid(pid, 0)
    return (items, json.loads(data))


def run_and_wait(argv: list) -> int:
    """Run the program `argv` in a child and return its exit code.

    Fork, exec `argv[0]` with `os.execvp(argv[0], argv)`, and wait. Send the
    child's stdout and stderr to os.devnull so they cannot disturb the harness.
    If the program cannot be started, return 127. Use `exit_code` on the status.

    >>> run_and_wait(["sh", "-c", "exit 7"])
    7
    """
    pid = os.fork()
    if pid == 0:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            os.execvp(argv[0], argv)  # replaces this process; returns only on failure
        finally:
            # Reached only if exec failed (the exception is dropped by _exit).
            os._exit(127)
    _, status = os.waitpid(pid, 0)
    return exit_code(status)


def run_capture(argv: list) -> tuple:
    """Run `argv` and return `(exit_code, output_bytes)`.

    Create a pipe, fork, and in the child dup2 the write end onto both fd 1 and
    fd 2 before the exec. The parent reads everything the child writes (the
    program can write more than a pipe holds, so read before you wait), then
    reaps the child.

    >>> run_capture(["echo", "hi"])
    (0, b'hi\\n')
    """
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(r)
            os.dup2(w, 1)  # fd 1 now points at the pipe
            os.dup2(w, 2)
            os.close(w)
            os.execvp(argv[0], argv)
        finally:
            os._exit(127)
    os.close(w)  # the parent must not hold the write end, or read_all never ends
    output = read_all(r)  # read first: a full pipe would block the child forever
    os.close(r)
    _, status = os.waitpid(pid, 0)
    return exit_code(status), output


def fork_many(n: int, func) -> list:
    """Run `func(i)` in n children, one per i in 0..n-1, and collect the results.

    Each child computes `func(i)` (an int), writes it as text to its own pipe,
    and exits with code 0. The parent reads every pipe and returns the results
    as a list ordered by i, whatever order the children finish in. If `func`
    raises in a child, that child exits with code 1 and, after the parent has
    reaped every child, the parent raises RuntimeError.

    >>> fork_many(4, lambda i: i * i)
    [0, 1, 4, 9]
    """
    readers = []  # (pid, read_fd) in order of i
    for i in range(n):
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            code = 1
            try:
                os.close(r)
                os.write(w, str(func(i)).encode())
                os.close(w)
                code = 0
            finally:
                os._exit(code)
        os.close(w)
        readers.append((pid, r))
    results = []
    failed = []
    for i, (pid, r) in enumerate(readers):
        data = read_all(r)
        os.close(r)
        _, status = os.waitpid(pid, 0)
        if exit_code(status) != 0:
            failed.append(i)
        else:
            results.append(int(data))
    if failed:
        raise RuntimeError(f"children {failed} failed")
    return results


if __name__ == "__main__":
    print("who_am_i:", who_am_i())
    print("isolation:", fork_isolation(["a"]))
    print("decode:", decode_status(3 << 8), decode_status(9))
    print("run_and_wait:", run_and_wait(["sh", "-c", "exit 7"]))
    print("run_capture:", run_capture(["echo", "hello from a child"]))
    print("fork_many:", fork_many(5, lambda i: i * i))
