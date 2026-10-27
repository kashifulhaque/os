---
title: Pipes, file descriptors, and a tiny shell
slug: 08-pipes-and-a-tiny-shell
part: "Part 2 — Processes"
summary: Rewire a process's file descriptors with dup2, connect programs with pipes, and build a shell that runs pipelines and redirections.
minutes: 60
gpu: false
objectives:
  - Say what a file descriptor is, and draw the descriptor table before and after dup2.
  - Explain how a shell does redirection with open and dup2 between fork and exec.
  - Wire a pipeline of any length with pipe, and say which pipe ends each process must close.
  - Parse a command line with pipes and redirections into commands, and run it.
prereqs:
  - 07-fork-exec-and-wait
exercise: 08-pipes-and-a-tiny-shell
---

# Pipes, file descriptors, and a tiny shell

When you type `ls | wc -l`, two programs start. The first lists files. The
second counts lines. Neither knows the other exists. `ls` writes its output as
it would to a screen, and `wc` reads input as it would from a keyboard. Yet the
output of one becomes the input of the other.

A program that does this wiring for you is the *shell*. Most of what a shell
does is the three calls from the last lesson: `fork`, `exec`, and `wait`. The
rest is a small trick with file descriptors. In this lesson you learn the trick
and build a working shell that runs pipelines and redirections on the real
kernel. It is the payoff of Part 2.

## What you already know

- `fork` copies a process, and the child shares the parent's open files.
- `exec` replaces a process's program but keeps its open file descriptors.
- `wait` collects a child's exit status.
- `os.pipe()` returns two descriptors, a read end and a write end.
- A reader sees end of file only after every copy of the write end is closed.

## File descriptors

Programs read and write many things: files, the keyboard, the screen, network
connections, pipes. The kernel hides the differences behind one idea. Each
process has a table of *file descriptors*. A file descriptor is a small
non-negative integer, and each one names an open "thing" the process can read
or write.

By convention every process starts with three:

| Number | Name | Used for |
|---|---|---|
| 0 | standard input, `stdin` | Where the program reads its input |
| 1 | standard output, `stdout` | Where the program writes its results |
| 2 | standard error, `stderr` | Where the program writes error messages |

A program that wants to print calls `write(1, ...)` and does not care what is
behind descriptor 1. In a terminal it is the screen. The program never
decides. The *process that started it* decides, by setting up the table first.

```text
 the descriptor table of a program started from a terminal

   fd   points to
   0 -> terminal (keyboard)
   1 -> terminal (screen)
   2 -> terminal (screen)
```

> [!KEY]
> A program writes to descriptor 1 and reads from descriptor 0 without knowing
> what they are. A shell redirects a program by changing what those numbers
> point to before the program starts.

## dup2: make one descriptor point where another does

`dup2(old, new)` makes descriptor `new` refer to the same open thing as `old`.
If `new` was already open, the kernel closes it first. After the call, both
numbers lead to the same place.

Take `echo hi > out.txt`. The shell must make `echo`'s descriptor 1 point at the
file. It runs these steps:

1. `fd = open("out.txt", O_WRONLY | O_CREAT | O_TRUNC, 0o644)` returns, say, 3.
2. `dup2(3, 1)` makes descriptor 1 point at the file, closing the screen.
3. `close(3)`, since descriptor 1 does the job.

Here is the table in each step.

```text
 start               after open()         after dup2(3, 1)        after close(3)

 0 -> terminal       0 -> terminal        0 -> terminal           0 -> terminal
 1 -> terminal       1 -> terminal        1 -> out.txt            1 -> out.txt
 2 -> terminal       2 -> terminal        2 -> terminal           2 -> terminal
                     3 -> out.txt         3 -> out.txt
```

The same code in C and in Python:

```c
int fd = open("out.txt", O_WRONLY | O_CREAT | O_TRUNC, 0644);
dup2(fd, 1);
close(fd);
```

```python
fd = os.open("out.txt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
os.dup2(fd, 1)
os.close(fd)
```

The flags say: open for writing only, create the file if missing, and empty it
if it exists. The `0o644` is the permission mode, used only when the file is
created. Lesson 26 explains it.

## Why fork and exec are separate calls

The odd design makes sense at last. Here is what a shell does for `echo hi > out.txt`:

```text
 shell                         child
   fork() ------------------>  (a copy of the shell)
   |                           open("out.txt"), dup2(fd, 1), close(fd)
   |                           execvp("echo", ["echo", "hi"])
   |                           echo writes "hi" to descriptor 1: the file
   waitpid() <---------------  echo exits
```

The shell rearranges the child's descriptors *after* `fork` and *before*
`exec`. The change affects only the child. The shell keeps its own terminal. And
`exec` keeps descriptors, so `echo` inherits the rearranged table without any
code to support it. If `fork` and `exec` were a single call, it would need a
parameter for every possible rearrangement.

This also explains why `cd` is a shell *builtin*. A child cannot change its
parent's current directory. So the shell runs `cd` itself, without forking.

## Pipes

A pipe, from the last lesson, is a kernel buffer with a read end and a write
end. To connect `ls | wc -l`, the shell does this:

1. `os.pipe()` returns `(r, w)`, say `(3, 4)`.
2. Fork the left child. Set its descriptor 1 to `w`. Exec `ls`.
3. Fork the right child. Set its descriptor 0 to `r`. Exec `wc`.
4. In the shell, close `r` and `w`. Then wait for both children.

Here is the shell's descriptor table, then each child's table after its `dup2`
calls and before its `exec`.

```text
 shell (after pipe)      left child (ls)          right child (wc)

 0 -> terminal           0 -> terminal            0 -> pipe (read)
 1 -> terminal           1 -> pipe (write)        1 -> terminal
 2 -> terminal           2 -> terminal            2 -> terminal
 3 -> pipe (read)        3 -> pipe (read)   close 3 -> pipe (read)   close
 4 -> pipe (write)       4 -> pipe (write)  close 4 -> pipe (write)  close
```

The "close" marks matter. Each child must close the original pipe descriptors
after `dup2`. The copy on descriptor 0 or 1 is all it needs.

### The closing rule

Every unneeded copy of a pipe end must be closed, in every process, or the
pipeline breaks in one of two ways.

- **A leftover write end hangs the reader.** `wc` reads until end of file. End
  of file comes only when every copy of the write end is closed. If the shell
  still holds one, `wc` waits forever.
- **A leftover read end hides a dead reader.** When a reader exits, a writer
  should learn the pipe is broken. If some process still holds a read end, the
  writer's data keeps going into the buffer.

Python helps in one way. Descriptors you create with `os.pipe()` and `os.open()`
are *close-on-exec*: the kernel closes them for you at `exec`. A descriptor you
`dup2` onto 0, 1, or 2 is not, so it survives. The shell's parent process still
must close its own copies by hand, and a child should close extras before the
exec so they do not linger while it runs.

### Longer pipelines and SIGPIPE

Three commands, `a | b | c`, need two pipes. Command `b` reads from the first
and writes to the second. Command `i` of `n` gets stdin from pipe `i-1` and
stdout to pipe `i`. In a real shell, the first command keeps the shell's stdin and the last keeps
its stdout. Your function captures output instead, so it adds one more pipe after
the last command and reads it in the parent.

Suppose you run `yes | head -n 3`. `yes` prints `y` forever. `head` takes 3
lines and exits. The next time `yes` writes, the kernel sees a pipe with no
reader. It sends `yes` the signal `SIGPIPE`, and by default that kills it. This
is how infinite producers stop.

Python changes this default. At start-up it tells the kernel to *ignore*
`SIGPIPE`, so a failed write raises `BrokenPipeError` instead. The setting
survives `fork` and `exec`. Every program your Python code starts
inherits the ignore. A program that does not stop on a failed write, such as the
shell loop `while true; do echo y; done`, would spin forever. A shell
written in Python must restore the default before it execs:

```python
signal.signal(signal.SIGPIPE, signal.SIG_DFL)
```

The next lesson covers signals in depth.

> [!WARNING]
> Python ignores `SIGPIPE`, and an `exec` keeps that setting. Reset it to
> `SIG_DFL` in the child, or a producer that ignores write errors never stops.

## What a shell does

A shell is a loop:

1. Print a prompt and read a line.
2. Split the line into words and operators.
3. Group them into commands, one per pipeline stage.
4. For a builtin such as `cd`, run it in the shell itself.
5. Otherwise fork one child per stage, wire descriptors, and exec.
6. Wait for the children. Report the exit status of the last one.

You build steps 2, 3, 5, and 6. Your shell takes one line and returns the output
and the status, instead of looping.

## Parsing a command line

The line `sort < in.txt | head -n 2 > out.txt` must become two *commands*. Each
command has a list of words (`argv`), an optional input file, and an optional
output file:

```python
Command(argv=["sort"], stdin_path="in.txt", stdout_path=None)
Command(argv=["head", "-n", "2"], stdin_path=None, stdout_path="out.txt")
```

The first step is *tokenizing*: cutting the text into pieces. The starter gives
you `tokenize`. It returns `("word", text)` for words and `("op", "|")`,
`("op", "<")`, and `("op", ">")` for operators. It does not need spaces around
operators. Quotes keep spaces and operators inside a word, so `'a | b'` is one
word.

For the example, `tokenize` returns:

```text
 ("word","sort") ("op","<") ("word","in.txt") ("op","|")
 ("word","head") ("word","-n") ("word","2") ("op",">") ("word","out.txt")
```

Your `parse_pipeline` then works in two passes. First, split the token list at
each `("op", "|")`. That gives the stages. Second, walk each stage. A word joins
`argv`. A `<` or `>` takes the next token, which must be a word, as a file name.

Some inputs are errors. `| ls` and `ls |` have an empty stage. `ls >` has no file
name. A real shell prints a message, and your code raises `ShellSyntaxError`.

## A worked example: three fd tables

Follow `echo hi | tr a-z A-Z` as your `run_pipeline` runs it. It makes two
pipes: `P1` between the commands, and `Out` for the final output. Suppose the
descriptors come out as `P1 = (3, 4)` and `Out = (5, 6)`.

```text
 command     fd 0               fd 1               other fds closed
 echo hi     /dev/null          P1 write end (4)   3, 4, 5, 6
 tr a-z A-Z  P1 read end (3)    Out write end (6)  3, 4, 5, 6
 parent      terminal           terminal           closes 3, 4, 6, keeps 5
```

The parent reads from `5` until end of file. That happens when `echo` has
exited, closing its end of `P1`, so `tr` sees end of file, finishes, and
exits, closing its end of `Out`. The parent then waits for both and returns the
status of `tr`.

## Try it on your own machine

These work on Linux. On macOS, `/proc` does not exist, and `lsof -p` with a pid shows a process's descriptors.

1. Look at a process's descriptor table.

   ```bash
   ls -l /proc/self/fd
   ```

   You see `0`, `1`, and `2` pointing at your terminal, such as `/dev/pts/0`. A
   fourth entry is the directory `ls` opened to read this list.

2. Watch a pipeline get built.

   ```bash
   strace -f -e trace=pipe2,dup2,dup3,close,execve sh -c 'echo hi | tr a-z A-Z' 2>&1 | head -30
   ```

   Look for `pipe2`, then `dup2` (or `dup3`) calls with 0 or 1 as the second
   argument, then `execve` for each program.

3. See SIGPIPE end a producer.

   ```bash
   yes | head -n 3
   ```

   It prints three lines and returns. With bash, `echo ${PIPESTATUS[@]}`
   afterward prints `141 0`. The `141` is 128 plus 13, the number of `SIGPIPE`.

4. See that the last command sets the status.

   ```bash
   false | true; echo $?
   true | false; echo $?
   ```

   The first prints 0, and the second prints 1.

5. Redirect by hand.

   ```bash
   echo hello > /tmp/out.txt; cat < /tmp/out.txt | tr a-z A-Z
   ```

   `>` creates the file. `<` feeds it back in. The pipe sends it to `tr`.

## Build it step by step

The starter gives you `tokenize`, `exit_code`, `read_all`, the `Command`
dataclass, and `ShellSyntaxError`. You write three functions.

1. **`parse_pipeline(line)`** returns a list of `Command`. An empty line gives
   `[]`. Split the tokens at `("op", "|")`, then read each stage as described
   above. Raise `ShellSyntaxError` for an empty stage or a missing file name.
   The usual mistake is to forget the empty-stage cases at either end of the line
   (`| ls`, `ls |`) and between pipes (`a || b`).
2. **`run_pipeline(commands)`** returns `(exit_code, output_bytes)`. Make every
   pipe before you fork. In each child, `dup2` the pipe ends onto 0 and 1, send
   descriptor 2 to `os.devnull`, close all the pipe descriptors, apply the file
   redirections, set `SIGPIPE` back to the default, and `execvp`. Do the
   redirections after the pipe `dup2` calls, so `>` replaces the pipe. The first
   command reads `/dev/null` unless it has a `<` file. End each child with
   `os._exit` in a `finally`: 127 if exec failed, 1 if a redirect file would not
   open. In the parent, close every pipe end except the read end of the output
   pipe, read it to end of file, then wait for every child. The status of the last
   command is the result.
3. **`run_line(line)`** parses, then runs. It is one line.

The checks include a pipeline that needs `SIGPIPE`, one that moves 200,000 bytes,
and a count of your open descriptors before and after, so a leak shows up.

## Where this breaks

Your shell is tiny. Real shells do much more, and some of it is hard.

- **No job control.** A real shell puts each pipeline in a *process group*, so
  Ctrl-C reaches the whole pipeline and not the shell. It also lets you stop a job
  and resume it later.
- **No variables, globbing, or control flow.** `$HOME`, `*.txt`, `&&`, `;`, and
  `if` are all work for the shell, before it forks.
- **More redirections.** Real shells have `>>` to append, `2>` for stderr, `2>&1`
  to merge them, and `<<` for inline text. They are all `open` and `dup2`.
- **Quoting is deep.** Escapes, nested quotes, and substitutions make shell syntax
  tricky. Your quoting is the simplest useful subset.
- **A pipe has a fixed capacity.** If two processes each wait for the other to
  read, they deadlock. A shell avoids this by not letting a command read and write
  the same pipe.
- **Descriptor leaks are quiet.** A single leaked write end can hang a pipeline
  that works on every other run. Programs that create many pipes must close them
  carefully.
- **A forked child pays the cost of forking the shell.** For big shells this adds
  up, which is why shells use `vfork` or `posix_spawn` where they can.

## Further reading

- [Operating Systems: Three Easy Pieces, chapter 5, Interlude: Process API](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf)
  shows how a shell uses `fork`, `exec`, and `dup` for redirection and pipes.
- [The dup(2) manual page](https://man7.org/linux/man-pages/man2/dup.2.html)
  defines `dup2` and what happens when the target is already open.
- [The pipe(7) manual page](https://man7.org/linux/man-pages/man7/pipe.7.html)
  explains capacity, blocking, and what a reader sees when the writers close.
- [POSIX shell command language](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html)
  is the specification that shells such as `sh` follow, including pipelines and
  redirection.
- [xv6: a simple, Unix-like teaching operating system](https://pdos.csail.mit.edu/6.828/2023/xv6/book-riscv-rev3.pdf)
  shows in chapter 1 how a small shell uses `fork`, `exec`, `dup`, and pipes.

## The exercise

You write `parse_pipeline`, `run_pipeline`, and `run_line`. The first four checks
test only the parser, so you see progress before any process runs. Then the checks
run real pipelines: single commands, two and five stages, the status of the last
command, `<` and `>` redirections, and a `>` that replaces a pipe.

The last two checks look for the bugs that matter. One pushes 200,000 bytes
through a pipe and compares your descriptor count before and after. The other runs
an endless producer into `head -n 3`, which hangs if `SIGPIPE` is still ignored.
A watchdog stops any check that waits longer than four seconds, and says which
mistakes usually cause it.
