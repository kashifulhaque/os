"""A tiny shell: parse `a | b < in > out`, then run it with fork, pipe, dup2, and exec.

`tokenize`, `exit_code`, `read_all`, `Command`, and `ShellSyntaxError` are
given. Fill in `parse_pipeline`, `run_pipeline`, and `run_line`.

The harness reserves file descriptor 1 for its own messages, so the last
command of a pipeline writes into a pipe that your code reads, and stderr of
every command goes to os.devnull.
"""

import os
import signal
from dataclasses import dataclass, field
from typing import Optional


class ShellSyntaxError(Exception):
    """The command line is not valid shell syntax."""


@dataclass
class Command:
    """One stage of a pipeline: a program, its arguments, and optional redirections."""

    argv: list = field(default_factory=list)
    stdin_path: Optional[str] = None  # from `< path`
    stdout_path: Optional[str] = None  # from `> path`


def read_all(fd: int) -> bytes:
    """Read from `fd` until end of file."""
    chunks = []
    while True:
        data = os.read(fd, 65536)
        if not data:
            return b"".join(chunks)
        chunks.append(data)


def exit_code(status: int) -> int:
    """Raw wait status to shell exit code: the code, or 128 + N for death by signal N."""
    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return status


def tokenize(line: str) -> list:
    """Split a command line into ("word", text) and ("op", "|" / "<" / ">") tokens.

    Single and double quotes group characters, including spaces and operators,
    into one word. An operator needs no spaces around it.

    >>> tokenize("cat a|wc")
    [('word', 'cat'), ('word', 'a'), ('op', '|'), ('word', 'wc')]
    >>> tokenize("echo 'a | b'")
    [('word', 'echo'), ('word', 'a | b')]
    """
    tokens = []
    word = None  # characters of the word being built, or None between words
    i = 0
    while i < len(line):
        ch = line[i]
        if ch in " \t":
            if word is not None:
                tokens.append(("word", "".join(word)))
                word = None
            i += 1
        elif ch in "|<>":
            if word is not None:
                tokens.append(("word", "".join(word)))
                word = None
            tokens.append(("op", ch))
            i += 1
        elif ch in "'\"":
            end = line.find(ch, i + 1)
            if end == -1:
                raise ShellSyntaxError(f"unterminated {ch} quote")
            if word is None:
                word = []
            word.append(line[i + 1 : end])
            i = end + 1
        else:
            if word is None:
                word = []
            word.append(ch)
            i += 1
    if word is not None:
        tokens.append(("word", "".join(word)))
    return tokens


def parse_pipeline(line: str) -> list:
    """Parse a command line into a list of `Command`, one per pipeline stage.

    Use `tokenize`. Split on `|`. In each stage, words build `argv`, `< word`
    sets `stdin_path`, and `> word` sets `stdout_path`. An empty line gives
    `[]`. Raise `ShellSyntaxError` for a stage with no command (`| ls`,
    `ls |`, `a || b`), for `<` or `>` with no file name after it, and for an
    unterminated quote.

    >>> parse_pipeline("sort < in.txt | head -n 2 > out.txt")
    [Command(argv=['sort'], stdin_path='in.txt', stdout_path=None),
     Command(argv=['head', '-n', '2'], stdin_path=None, stdout_path='out.txt')]
    """
    raise NotImplementedError


def run_pipeline(commands: list) -> tuple:
    """Run the commands as one pipeline and return `(exit_code, output_bytes)`.

    Command i's stdout feeds command i+1's stdin through a pipe. The last
    command's stdout goes to a pipe that you read (unless it has `stdout_path`,
    and then the output is b""). The first command reads from os.devnull
    unless it has `stdin_path`. A redirection overrides the pipe on the same
    side. Every command's stderr goes to os.devnull. The exit code is the last
    command's, as `exit_code` computes it. A program that cannot be started
    gives 127. A redirect file that cannot be opened gives 1. An empty list
    gives `(0, b"")`. Reap every child.

    >>> run_pipeline([Command(["echo", "hi"]), Command(["tr", "a-z", "A-Z"])])
    (0, b'HI\\n')
    """
    raise NotImplementedError


def run_line(line: str) -> tuple:
    """Parse `line` and run it. Return `(exit_code, output_bytes)`.

    >>> run_line("echo hello world | tr a-z A-Z")
    (0, b'HELLO WORLD\\n')
    """
    raise NotImplementedError


if __name__ == "__main__":
    print(parse_pipeline("sort < in.txt | head -n 2 > out.txt"))
    print(run_line("echo hello world | tr a-z A-Z"))
    print(run_line("echo one two three | wc -w"))
    print(run_line("no-such-program"))
