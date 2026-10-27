---
title: "Creating processes: fork, exec, and wait"
slug: 07-fork-exec-and-wait
part: "Part 2 — Processes"
summary: Start real Linux processes with fork, replace their program with exec, collect their exit status with wait, and gather results through pipes.
minutes: 55
gpu: false
objectives:
  - Explain what fork returns in the parent and in the child, and what a child inherits.
  - "Use exec to replace a process's program, and say what survives the exec."
  - Decode a wait status into an exit code or a killing signal.
  - Run a program and capture its output through a pipe without deadlocking.
prereqs:
  - 06-processes
exercise: 07-fork-exec-and-wait
---

# Creating processes: fork, exec, and wait

Last lesson you built a process table. Every row in it came from somewhere: a
process created it. This lesson shows how the real kernel creates processes,
and you will do it from Python, with real processes on your real machine.

Windows has one call that says "start this program". Unix uses two steps.
`fork` makes a copy of the calling process. `exec` makes a process run a
different program. A third call, `wait`, lets a parent pick up the exit status
of a child. Together they are how every shell, every build tool, and every
server starts other programs.

Two steps seem odd at first. They exist because the gap between the steps is
where a shell rearranges file descriptors, so a command's output goes to a file
or a pipe. The next lesson builds that. This lesson builds the steps.

## What you already know

- A process has a pid, a parent, an address space, and a table of open files.
- A finished process stays a zombie until its parent calls `wait`.
- A system call is a request to the kernel, and Python's `os` module exposes
  many of them directly.
- An orphan, a process whose parent died, is adopted by pid 1.
- A `bytes` value is a sequence of numbers from 0 to 255.

## fork: make a copy of this process

`fork` takes no arguments. The kernel creates a second process that is an almost
exact copy of the caller. It has the same code, the same data, the same
registers, and the same open files. It has a different pid. The original is the
*parent*, and the copy is the *child*.

After `fork` both processes continue from the same place: the instruction right
after the call. Here is the odd part. The call returns twice, once in each
process, with a different value:

| Where | `fork` returns |
|---|---|
| In the parent | The child's pid, a positive number |
| In the child | 0 |
| On failure (parent only) | -1 in C, an `OSError` in Python |

That return value is how each process finds out which one it is. In Python:

```python
import os

pid = os.fork()
if pid == 0:
    print("I am the child; my pid is", os.getpid())
    os._exit(0)
else:
    print("I am the parent; my child has pid", pid)
    os.waitpid(pid, 0)
```

The same program in C looks nearly identical. You never write C in this
course, but you will meet it in books and manual pages:

```c
pid_t pid = fork();
if (pid == 0) {
    printf("child\n");
    _exit(0);
} else if (pid > 0) {
    printf("parent, child is %d\n", pid);
    waitpid(pid, NULL, 0);
} else {
    perror("fork");
}
```

```text
 before fork                  after fork

   +--------+           +--------+          +--------+
   | pid 100|           | pid 100|          | pid 101|
   | parent |   ---->   | parent |          | child  |
   | x = 5  |           | x = 5  |          | x = 5  |
   +--------+           | pid=101|          | pid=0  |
                        +--------+          +--------+
                       fork returned 101   fork returned 0
```

### The copy is private

The child's memory is a copy. If the child changes a variable, the parent does
not see it, and the reverse. Take this run:

1. The parent sets `x = 5`, then forks. Pid 100 is the parent, pid 101 the
   child.
2. The child sets `x = 6` and exits.
3. The parent waits, then prints `x`. It prints 5.

Copying all of memory sounds costly. The kernel avoids the cost with
*copy-on-write*: parent and child share the same pages until one of them writes
to a page, and then the kernel copies that one page. Lesson 14 explains the
machinery.

The open files are different. The child gets its own copy of the *table* of
open files, but each entry points to the same underlying open file. So the two
share a file's current read or write position. A pipe created before the fork
is usable by both processes. That fact powers the rest of the lesson.

> [!KEY]
> `fork` returns twice: the child's pid in the parent, and 0 in the child. The
> child gets a private copy of memory and shares the parent's open files.

### Why the child must call os._exit

In the earlier example the child ends with `os._exit(0)`, not `sys.exit(0)` or
a plain return. The difference matters.

`sys.exit` unwinds through Python's normal shutdown. It flushes output buffers
and runs cleanup code. The child has a *copy* of all of it, so text that the
parent had not yet printed is printed twice, once per process. `os._exit`
leaves at once, with no cleanup. A forked child should always end this way.

A child that returns from your function is worse. It carries on running
the code after the call, as though it were the parent. In this course's test
runner, that means a child would start the remaining checks again. Always wrap
a child's work like this:

```python
pid = os.fork()
if pid == 0:
    try:
        ...  # the child's work
    finally:
        os._exit(0)   # runs even if the work raises
```

> [!WARNING]
> A child that returns or raises instead of calling `os._exit` runs the
> parent's code a second time. Put `os._exit` in a `finally` block.

## exec: replace the program

`fork` gives you a second copy of the same program. To run a different one, the
child calls `exec`. It does not create a process. It *replaces* the program
inside the calling process. The kernel throws away the old code and memory,
loads the other program from its file, and starts it from the top.

What changes and what stays:

| Survives `exec` | Replaced by `exec` |
|---|---|
| The pid and the parent | The code and data |
| The open file descriptors (usually) | The heap and the stack |
| The current directory | The registers, including the program counter |
| The environment (`execvp` passes it on) | Every caught signal's handler (ignored signals stay ignored) |

A successful `exec` never returns, because the code that called it is gone. If
it returns at all, it failed, for example because the file does not exist. In
Python a failure raises `FileNotFoundError` or another `OSError`.

Python names several variants. `os.execvp(file, args)` is the one to learn.
The `v` means the arguments come as a list. The `p` means the kernel looks for
`file` in each directory of the `PATH` environment variable, like a shell does.

```python
os.execvp("echo", ["echo", "hello"])
# Nothing after this line runs, unless exec failed.
```

The list's first item is `argv[0]`, the name the program thinks it was called
by. By convention it repeats the program name. In C:

```c
char *args[] = {"echo", "hello", NULL};
execvp("echo", args);
_exit(127);   /* reached only if execvp failed */
```

Here is the whole idea of "run a program" in one picture. The parent keeps its
pid and its code. The child begins as a copy, then turns into `echo`.

```text
 parent (pid 100)       child (pid 101)

   fork() ------------> starts as a copy of the parent
   |                    execvp("echo", ...)
   |                      the child's memory is replaced by echo's
   |                    echo runs, prints "hello"
   |                    echo exits with code 0   (child is now a zombie)
   waitpid(101) <------ the parent collects status 0
```

> [!TIP]
> If `exec` fails, the child is still a copy of your program. Exit it at once
> with a code the parent can recognise. Shells use 127, for "command not
> found". The `finally: os._exit(127)` pattern does exactly that.

## wait: collect the exit status

When a child ends, the kernel stores its exit status and leaves a zombie.
`os.waitpid(pid, options)` blocks until that child ends, then returns a pair
`(pid, status)` and frees the zombie. Use `pid = -1` to wait for any child, and
`options = os.WNOHANG` to return at once with `(0, 0)` when nothing has ended.
Calling it with no children raises `ChildProcessError`, the C error `ECHILD`.

```python
pid, status = os.waitpid(child_pid, 0)
```

The `status` is not the exit code. It is a packed number that says *how* the
process ended. Here is how its low 16 bits are laid out.

```text
 bit  15           8 7  6          0
      +-------------+--+------------+
      | exit code   |C | signal no. |
      +-------------+--+------------+
 normal exit: the exit code is in bits 8-15, bits 0-7 are 0
 killed by a signal: bits 0-6 hold the signal number; bit 7 (C) means a core dump
```

Decode it with helpers from `os`, not by hand:

| Call | Meaning |
|---|---|
| `os.WIFEXITED(status)` | True for a normal exit |
| `os.WEXITSTATUS(status)` | The exit code (0 to 255), for a normal exit |
| `os.WIFSIGNALED(status)` | True when a signal killed the process |
| `os.WTERMSIG(status)` | The signal number that killed it |

Take three examples. A process that calls `exit(3)` leaves status `3 << 8`,
which is 768. A process killed by signal 9 leaves status 9. A process that
crashed with signal 11 and dumped core leaves `11 | 0x80`, which is 139.

Shells report this to you in `$?`. A normal exit shows its code. A death by
signal N shows `128 + N`. So `137` means killed by signal 9, and `143` means
killed by signal 15. The next lesson on signals explains what those are.

> [!KEY]
> A zombie lives until someone calls `wait`. The wait status says whether the
> process exited or was killed, and gives the code or the signal.

## Putting it together: run a program

Fork, exec, and wait together make a function that runs a program and returns
its exit code. Here is the shape:

```python
def run(argv):
    pid = os.fork()
    if pid == 0:
        try:
            os.execvp(argv[0], argv)
        finally:
            os._exit(127)      # only reached when exec failed
    _, status = os.waitpid(pid, 0)
    return status
```

In C it is the same three steps:

```c
pid_t pid = fork();
if (pid == 0) { execvp(argv[0], argv); _exit(127); }
int status;
waitpid(pid, &status, 0);
```

Python's `subprocess` module does this for you, with many extra options.

## Pipes: sending results back

A child's result has to get back to its parent. Memory will not do, because
the memory is private. You need a channel the kernel provides. The simplest is
a *pipe*.

A pipe is a one-way channel of bytes inside the kernel. `os.pipe()` returns two
file descriptors, `(r, w)`. Bytes written to `w` come out of `r`, in order. A
pipe holds a small buffer, 64 KiB on Linux. When the buffer is full, a writer
waits. When it is empty, a reader waits.

Because `fork` copies the table of open files, a pipe made before the fork has
both ends open in both processes. Each process closes the end it does not use.

```text
 after os.pipe() and fork()

   parent                         child
   r --------------+  +--------- r   (child closes r)
                   |  |
                 [ pipe buffer ]
                   ^  ^
   w (closed) -----+  +--------- w   (child writes here)

 parent reads from r; child writes into w. Each closes the other end.
```

The reader finds out the writer has finished through *end of file*. `os.read`
returns an empty `bytes` value, `b""`, only after *every* copy of the write end
is closed, in every process. If the parent keeps its own copy of `w` open, the
read never ends. This is the most common bug in this lesson.

> [!WARNING]
> Close the write end in the parent before you read. A leftover copy of the
> write end means the reader never sees end of file, and your program hangs.

A second trap: read before you wait. A child that prints 300,000 bytes fills the
64 KiB buffer and stops, waiting for a reader. If the parent calls `waitpid`
first, it waits for a child that waits for it. Neither moves. Read until end
of file first, then wait.

### Running many children

To run `n` jobs in parallel, make one pipe and one child per job. Each child
computes a value, writes it to its pipe, and exits. The parent closes each write
end at once, then reads each pipe in order of `i` and waits for each child. The
results come back in order, even when the children finish in another order,
because the parent blocks on pipe 0 until child 0 is done.

### Sending output into a pipe

Programs you `exec` print to file descriptor 1. In a terminal that is your
screen, so output appears by itself. In this course's runner, descriptor 1 is
the channel to the web page, and a stray `echo` would corrupt it. So the child
must point descriptor 1 at a pipe first. `os.dup2(w, 1)` does that: it makes
descriptor 1 a second name for the pipe's write end. The `exec` that follows
keeps it, so `echo` writes into your pipe. The next lesson explains `dup2`
properly. In C it is `dup2(w, 1);`.

## Try it on your own machine

All of these work on Linux. Some work on macOS, with different tools.

1. Watch the kernel create and run a process.

   ```bash
   strace -f -e trace=clone,clone3,execve,wait4 sh -c 'echo hi; ls /' 2>&1 | head -20
   ```

   `-f` follows children. Look for `clone` (what `fork` becomes in Linux),
   `execve` with the program name, and `wait4`. If `strace` is missing,
   install it with your package manager.

2. Read a wait status yourself.

   ```bash
   sh -c 'exit 3'; echo $?
   python3 -c 'import os; os.kill(os.getpid(), 9)'; echo $?
   ```

   The first prints 3. The second prints 137, which is 128 plus signal 9.

3. See fork's two return values.

   ```bash
   python3 -c "import os; print('fork returned', os.fork())"
   ```

   Two lines print: one with a large number and one with 0. Run it a few times.
   The order can change, because the kernel can run either process first.

## Build it step by step

Every function here uses real system calls. The starter gives you `read_all(fd)`,
which reads a pipe to end of file. The checks run each function in a real
process and guard against hangs and leaked children.

1. **`decode_status(status)`** takes a raw wait status and returns
   `("exited", code)` or `("signaled", signum)`. Use the four `os.W*` helpers.
   A frequent mistake is to read `status` as the code. For a normal exit it is
   the code shifted left by eight.
2. **`exit_code(status)`** returns the shell's number: the code, or `128 + N`
   for a death by signal N. Build it on `decode_status`.
3. **`who_am_i()`** forks one child and returns a dict with `parent`, `child`,
   `child_self`, and `child_parent`. The child writes its `getpid()` and
   `getppid()` into a pipe as JSON. The parent closes `w`, calls `read_all`, and
   reaps the child. The checks confirm that `fork`'s return value in the parent
   equals the child's own `getpid()`.
4. **`fork_isolation(items)`** forks a child that appends `"child"` to the list
   and sends the list back as JSON. The function returns the parent's list and
   the child's list. They differ, which proves memory is private.
5. **`run_and_wait(argv)`** forks, execs `argv`, and returns the exit code. In
   the child, `dup2` a handle on `os.devnull` onto descriptors 1 and 2 first, so
   the program cannot print into the runner. If exec fails, return 127. The
   usual slip is to forget `finally: os._exit(127)`, which lets a failed child
   run on as a second copy of your function.
6. **`run_capture(argv)`** is the same, with a pipe instead of `/dev/null`. It
   returns `(exit_code, output_bytes)`. Send both descriptor 1 and descriptor 2
   to the pipe's write end. In the parent, close the write end, read to end of
   file, and only then wait.
7. **`fork_many(n, func)`** runs `func(i)` in `n` children and returns the list
   of results in order of `i`. A child that raises exits with code 1, and after
   you have reaped all `n` children the parent raises `RuntimeError`. Reap
   everyone before you raise.

## Where this breaks

- **Fork of a big process is slow.** Copy-on-write avoids copying the data, but
  the kernel still copies the page tables. A multi-gigabyte server that
  forks to run a tiny command pays for it. Linux offers `vfork` and
  `posix_spawn`, which start a program without copying the caller. Python's
  `subprocess` uses them where it can.
- **Fork and threads do not mix.** Only the thread that called `fork` exists in
  the child. If another thread held a lock at that instant, the child sees a
  lock that nobody will ever release. Python 3.12 prints a warning when you
  fork a process that has several threads.
- **Output buffers duplicate.** Unflushed text in the parent is copied into the
  child. Flush before you fork, or end the child with `os._exit`.
- **Descriptors leak into children.** A child inherits every open descriptor.
  Python opens files and pipes as close-on-exec by default, so an `exec` closes
  them. In C you must set the flag yourself, or leaked descriptors keep pipes
  open longer than you meant.
- **Fork can fail.** A full process table or a process limit makes `fork`
  fail. Real code checks for it.
- **Fork is a debated design.** The last paper below argues it is a poor
  primitive for a modern system.

## Further reading

- [Operating Systems: Three Easy Pieces, chapter 5, Interlude: Process API](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf)
  walks through `fork`, `wait`, and `exec` with C examples.
- [The fork(2) manual page](https://man7.org/linux/man-pages/man2/fork.2.html)
  lists exactly what a child inherits and what it does not.
- [The execve(2) manual page](https://man7.org/linux/man-pages/man2/execve.2.html)
  says what survives an exec, including the descriptor rules.
- [The wait(2) manual page](https://man7.org/linux/man-pages/man2/wait.2.html)
  documents `waitpid`, `WNOHANG`, and every status macro.
- [The pipe(2) manual page](https://man7.org/linux/man-pages/man2/pipe.2.html)
  covers the buffer size and the end-of-file rule.
- [A fork() in the road](https://www.microsoft.com/en-us/research/uploads/prod/2019/04/fork-hotos19.pdf)
  argues that `fork` has outlived its usefulness.

## The exercise

You write seven functions that use the real kernel: `decode_status`,
`exit_code`, `who_am_i`, `fork_isolation`, `run_and_wait`, `run_capture`, and
`fork_many`. The checks run each one in real processes. They test only
outcomes that hold under every scheduling order, never timing.

The checks look for the classic mistakes. One program writes 300,000 bytes, to
catch a parent that waits before it reads. A missing program must give 127. A
child killed by `kill -9` must give 137. After every function returns, the
checker looks for leftover children, and it stops a function that hangs after
four seconds. A failure message says what your function returned and what it
should have returned.
