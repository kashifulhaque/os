---
title: Signals
slug: 09-signals
part: "Part 2 — Processes"
summary: Send, catch, and survive signals, read the status of a process a signal killed, and build a command timeout with SIGALRM and SIGKILL.
minutes: 55
gpu: false
objectives:
  - Say where signals come from, and name the default action of SIGTERM, SIGKILL, SIGINT, and SIGSEGV.
  - Install a handler with signal.signal, send a signal with os.kill, and restore the old handler.
  - Explain why pending standard signals do not queue, and why a handler must be installed before it is needed.
  - Run a program with a timeout, using SIGALRM to wake the parent and SIGKILL to stop the child.
prereqs:
  - 08-pipes-and-a-tiny-shell
exercise: 09-signals
---

# Signals

You press Ctrl-C and a runaway program stops. You run `kill 4312` and a stuck
server goes away. A program touches memory it does not own and the system prints
"Segmentation fault". Three different events, one mechanism: a *signal*.

A signal is a tiny message that the kernel delivers to a process. It carries
only a number. It interrupts the process wherever it is, and the process
either dies, ignores it, or runs a small piece of code you wrote. Signals are
the oldest way for events to reach a Unix process, and every process-handling
tool uses them.

In this lesson you send and catch real signals, read the status of a process a
signal killed, and build a function that runs a program with a time limit. It
finishes Part 2.

## What you already know

- A process has a pid, and you can find its parent.
- `os.fork` makes a child, and `os.waitpid` returns a status that says whether
  the child exited or was killed by a signal.
- `exec` replaces a program, and a shell reports a death by signal N as `128 + N`.
- A Python function can be passed around as a value, such as a handler.
- Python ignores `SIGPIPE`, and a child that execs inherits the ignore.

## Where signals come from

Four kinds of sender exist.

- **The kernel**, when a program does something wrong. A bad memory access
  sends `SIGSEGV`. A write to a pipe with no reader sends `SIGPIPE`. A division
  by zero in machine code sends `SIGFPE`.
- **The terminal**, when you press a key. Ctrl-C sends `SIGINT`. Ctrl-\
  sends `SIGQUIT`. Ctrl-Z sends `SIGTSTP`, which stops the job.
- **Another process**, through the `kill` system call. The name is misleading.
  `kill` sends any signal, and killing is only the most common use.
- **A timer**, when an alarm you set goes off. That signal is `SIGALRM`.

Each signal has a number and a name. These are the ones you meet most on x86-64
and Arm Linux. Other chips number a few of them differently.

| Signal | Number | Default action | Typical cause |
|---|---|---|---|
| `SIGHUP` | 1 | Terminate | The terminal closed |
| `SIGINT` | 2 | Terminate | Ctrl-C |
| `SIGQUIT` | 3 | Terminate and dump core | Ctrl-\ |
| `SIGKILL` | 9 | Terminate, cannot be caught | `kill -9` |
| `SIGSEGV` | 11 | Terminate and dump core | Bad memory access |
| `SIGPIPE` | 13 | Terminate | Write to a pipe with no reader |
| `SIGALRM` | 14 | Terminate | A timer fired |
| `SIGTERM` | 15 | Terminate | The polite `kill` |
| `SIGCHLD` | 17 | Ignore | A child ended |
| `SIGSTOP` | 19 | Stop, cannot be caught | Pause a process |
| `SIGUSR1`, `SIGUSR2` | 10, 12 | Terminate | Yours to define |

You can list them all on your machine with `kill -l`.

## What a process can do about a signal

A process picks one of three *dispositions* for each signal.

1. **Default.** Each signal has a default action: terminate, terminate and
   dump a core file, ignore, stop, or continue. The table above shows the
   defaults.
2. **Ignore.** The kernel drops the signal. `signal.SIG_IGN` sets this.
3. **Catch.** The process names a function, called a *handler*. The kernel runs
   it when the signal arrives.

Two signals break the rule. `SIGKILL` and `SIGSTOP` cannot be caught or ignored.
The kernel must keep a way to stop any process, however broken, so these two
always do their default action.

> [!KEY]
> A process can default, ignore, or catch most signals. `SIGKILL` and `SIGSTOP`
> cannot be caught or ignored, so they are the last resort.

## Sending a signal

In Python, `os.kill(pid, signum)` sends a signal:

```python
import os, signal
os.kill(child_pid, signal.SIGTERM)       # ask politely
os.kill(os.getpid(), signal.SIGUSR1)     # send one to yourself
```

The shell command is the same: `kill -TERM 4312`, or `kill -15 4312`. Signal 0
does nothing. `os.kill(pid, 0)` only checks whether you may signal that pid, so
it tests whether a process exists. In C:

```c
kill(pid, SIGTERM);
```

You can signal only your own processes, unless you are the superuser.

## Catching a signal

In Python you install a handler with `signal.signal(signum, handler)`. The
handler takes two arguments: the signal number and the current stack frame.
The call returns the *previous* handler, so you can put it back.

```python
def on_usr1(signum, frame):
    print("got signal", signum)

old = signal.signal(signal.SIGUSR1, on_usr1)
try:
    os.kill(os.getpid(), signal.SIGUSR1)
finally:
    signal.signal(signal.SIGUSR1, old)    # leave no trace
```

In C the call is `sigaction`. It does what `signal.signal` does, with more control:

```c
struct sigaction sa;
sa.sa_handler = on_usr1;
sigemptyset(&sa.sa_mask);
sa.sa_flags = 0;
sigaction(SIGUSR1, &sa, NULL);
```

Trying `signal.signal(signal.SIGKILL, handler)` raises `OSError`, because the
kernel refuses. That is a quick way to test whether a signal can be caught.

> [!TIP]
> Always save the return value of `signal.signal` and restore it in a `finally`
> block. A handler left behind by a function surprises the next piece of code.

## How delivery works

A signal does not run your handler by magic. Here is the mechanism.

1. The sender asks the kernel to deliver signal `N` to process `P`.
2. The kernel sets a bit in `P`'s control block. The signal is *pending*.
3. Before `P` next returns to user mode, the kernel checks for pending signals
   that are not blocked.
4. If one has a handler, the kernel arranges for the process to run it first and
   then resume where it left off.

```text
 time ->

 process P:  ... normal code ...  [interrupted] handler runs  [resumes] ... code ...
                                       ^
 kernel:    signal arrives -> mark pending -> on return to user mode, deliver
```

Python adds a twist. When the kernel runs the process's handler, that handler is
a small C function that only records "signal N arrived". Python runs *your*
function a moment later, in the main thread, between two bytecode instructions.
A signal that arrives while Python is inside a slow C call, such as a `sleep`,
interrupts the sleep. If your handler returns normally, Python resumes the
sleep or the system call. If your handler raises an exception, the exception
breaks out of the call. That is how a timeout works, later in this lesson.

### Blocked and pending signals

A process can *block* a signal for a while. The kernel keeps it pending and
delivers it when the process unblocks. Python offers `signal.pthread_sigmask`
for this.

Here is the surprise. Pending standard signals do not queue. The kernel keeps one
bit per signal, not a counter. If five `SIGUSR1` signals arrive while it is
blocked, one is delivered.

```text
 SIGUSR1 blocked        send x5            unblock

   pending: 0            pending: 1           handler runs once
                         (not 5)
```

So a signal means "this happened at least once", and never "this happened
five times". Programs that need counts use another channel, such as a pipe.

> [!KEY]
> Standard signals coalesce. A signal sent five times while pending arrives once.
> Never use signals to count.

## Signals across fork and exec

- A `fork` child inherits the parent's handlers and its blocked set.
- An `exec` resets every *caught* signal to the default, because the handler
  function no longer exists in the next program. Ignored signals stay ignored, and
  so does the blocked set. This is why a child of Python inherits an ignored
  `SIGPIPE`, as the last lesson showed.

## Reading how a process died

Lesson 7 gave you the wait status. When a signal kills a process, `os.WIFSIGNALED`
is true, `os.WTERMSIG` gives the signal number, and `os.WCOREDUMP` says whether it
dumped core. Python names signals through `signal.Signals`:

```python
>>> signal.Signals(9).name
'SIGKILL'
```

Your `describe_status` turns a status into the text a shell prints:
`exited with code 3`, `killed by SIGKILL (9)`, or
`killed by SIGSEGV (11), core dumped`.

## The ready race

Say a parent forks a child. The child installs a `SIGTERM` handler that exits
with code 42. The parent sends `SIGTERM`. Which runs first, the child's
`signal.signal` call or the parent's `os.kill`? Nobody knows. The kernel picks.

```text
 lucky order                         unlucky order

 child:  install handler             parent: os.kill(child, SIGTERM)
 parent: os.kill(child, SIGTERM)     child:  killed by SIGTERM (default action)
 child:  handler runs, exit 42       child:  never installs the handler
```

The unlucky order is a *race condition*: the result depends on timing. The fix is
to make the order certain. The child, after it installs the handler, writes one
byte into a pipe. The parent reads that byte before it sends the signal. A read
on a pipe blocks until the byte arrives, so the order is fixed.

> [!WARNING]
> A handler must be installed before the signal can arrive. When a parent
> signals a child, make the child say "ready" through a pipe first.

## A timeout with SIGALRM and SIGKILL

Servers, test runners, and build tools must stop programs that run too long. The
plan:

1. Fork and exec the program.
2. Ask the kernel to send `SIGALRM` to you after `seconds`. Python's call is
   `signal.setitimer(signal.ITIMER_REAL, seconds)`, which accepts fractions. The
   C relative is `alarm(n)`, whole seconds only.
3. Install a `SIGALRM` handler that *raises an exception*.
4. Call `os.waitpid`. If the child ends first, you get its status. If the alarm
   fires first, the handler raises, and the exception breaks out of `waitpid`.
5. In the second case, send the child `SIGKILL` and call `waitpid` again to reap it.
6. Always cancel the timer (`setitimer(ITIMER_REAL, 0)`) and put back the old
   `SIGALRM` handler, whatever happened.

```text
 parent                                   child
   fork ------------------------------->  exec sleep 30
   setitimer(0.3 s)                       sleeping...
   waitpid()  ... blocked ...
   [0.3 s] SIGALRM -> handler raises
   waitpid interrupted
   kill(child, SIGKILL) -------------->   dies
   waitpid() -> status 9
```

Why `SIGKILL` and not `SIGTERM`? A process can catch or ignore `SIGTERM`, and some
do. `SIGKILL` always works. Real tools often send `SIGTERM` first and
`SIGKILL` later, to let a well-behaved program clean up. The `timeout` command
works this way when you give it `-k`.

A small race hides here. If the child exits at the same instant as the alarm,
the exception may arrive after `waitpid` has already reaped the child. Careful
code blocks `SIGALRM` while it cleans up. The exercise tests with a clear gap
between the two events, so the simple version passes.

## Try it on your own machine

These work on Linux. Most work on macOS.

1. List the signals.

   ```bash
   kill -l
   ```

   The numbers match the table above on x86-64 and Arm Linux.

2. Kill a process and read its status.

   ```bash
   sleep 100 & kill -TERM $!; wait $!; echo $?
   ```

   It prints 143, which is 128 plus 15.

3. Catch a signal in the shell.

   ```bash
   bash -c 'trap "echo caught USR1" USR1; kill -USR1 $BASHPID; echo done'
   ```

   `trap` installs a handler. The output is `caught USR1`, then `done`.

4. Stop and continue a process.

   ```bash
   sleep 100 & kill -STOP $!; ps -o pid,stat,cmd -p $!; kill -CONT $!; kill $!
   ```

   `STAT` shows `T` while it is stopped. `SIGSTOP` cannot be caught.

5. See a process's signal settings in `/proc` (Linux).

   ```bash
   grep -E 'SigPnd|SigBlk|SigIgn|SigCgt' /proc/self/status
   ```

   Each line is a bit mask: pending, blocked, ignored, and caught signals.

6. Use a real timeout.

   ```bash
   timeout 1 sleep 10; echo $?
   ```

   The exit code is 124, the code `timeout` uses when it had to stop the command.

## Build it step by step

The starter gives you `exit_code`. You write seven functions. The checks run
real signals, and put back every handler they touch.

1. **`describe_status(status)`** turns a wait status into a string.
   `exited with code N` for a normal exit. `killed by NAME (N)` for a signal,
   plus `, core dumped` when `os.WCOREDUMP(status)` is true. Get the name from
   `signal.Signals(N).name`.
2. **`can_catch(signum)`** returns whether a handler can be installed. Try
   `signal.signal`, return `False` on `OSError`, and put the old handler back
   before you return `True`. The usual slip is leaving your test handler in place.
3. **`catch_signal(signum)`** installs a handler that appends the signal number to
   a list, sends the signal to your own pid with `os.kill`, restores the old
   handler in a `finally`, and returns the list.
4. **`coalesced_count(signum, n)`** blocks the signal with
   `signal.pthread_sigmask(signal.SIG_BLOCK, {signum})`, sends it `n` times to
   yourself, unblocks it, and returns how many times the handler ran. Restore
   the mask and the handler. The answer is 1 for any `n` of 1 or more.
5. **`kill_child(signum)`** forks a child that loops on `time.sleep`, sends it the
   signal, and returns the raw status from `os.waitpid`. The child ends with
   `os._exit` in a `finally`, as before.
6. **`graceful_child()`** forks a child that installs a `SIGTERM` handler calling
   `os._exit(42)`, writes one byte to a pipe, then sleeps. The parent reads that
   byte, sends `SIGTERM`, and returns the raw status. The mistake: sending the
   signal before the ready byte arrives. The check repeats eight times to catch it.
7. **`run_with_timeout(argv, seconds)`** returns `(timed_out, code)`. Send the
   child's stdout and stderr to `os.devnull`. Use `signal.setitimer` and a
   handler that raises. On a timeout, `SIGKILL` the child, reap it, and return
   `(True, 137)`. Otherwise return `(False, exit_code(status))`. A program that
   cannot start gives 127. Cancel the timer and restore the old handler in a
   `finally` that always runs.

## Where this breaks

- **Signals are lossy.** They coalesce, and they carry no data. A program that
  must not lose events needs a pipe, a socket, or a queue. Linux also has
  real-time signals that queue and carry a value, but few programs use them.
- **Handlers are dangerous.** A handler can interrupt a program in the middle of
  anything, including `malloc`. In C, a handler may call only a short list of
  functions called *async-signal-safe*. The usual advice is to set a flag in the
  handler and do the real work in the main loop. Python avoids most of the
  danger by running your handler between bytecodes.
- **Races are everywhere.** The ready race above, the alarm race, and "check
  whether the process exists, then signal it" are all races. A pid can even be
  reused between the check and the signal.
- **System calls get interrupted.** A signal can cut a blocking call short with
  the error `EINTR`. C code must retry. Python retries for you unless your
  handler raises.
- **Threads complicate delivery.** In a multi-threaded program, the kernel picks
  a thread to run the handler. Python runs handlers only in the main thread.
- **`SIGKILL` does not clean up.** The process gets no chance to flush files or
  remove temporary files. And if the child started children of its own, killing
  the child leaves those running. Real tools signal a whole *process group*.
- **A process in state `D` ignores even `SIGKILL`** until its disk request returns.
- **Modern alternatives exist.** On Linux, `signalfd` turns signals into file
  descriptors, and `pidfd_send_signal` signals a specific process without the
  pid-reuse risk.

## Further reading

- [Operating Systems: Three Easy Pieces, chapter 5, Interlude: Process API](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf)
  has a short section on signals and how a shell uses them.
- [The signal(7) manual page](https://man7.org/linux/man-pages/man7/signal.7.html)
  lists every Linux signal, its default action, and the rules for delivery.
- [The sigaction(2) manual page](https://man7.org/linux/man-pages/man2/sigaction.2.html)
  documents the C call for installing handlers.
- [The signal-safety(7) manual page](https://man7.org/linux/man-pages/man7/signal-safety.7.html)
  lists what a C handler may call.
- [Python's signal module](https://docs.python.org/3/library/signal.html)
  explains how Python runs handlers, and the rules for threads and `EINTR`.
- [The kill(2) manual page](https://man7.org/linux/man-pages/man2/kill.2.html)
  describes who may send a signal to whom, and the special pids 0 and -1.

## The exercise

You write `describe_status`, `can_catch`, `catch_signal`, `coalesced_count`,
`kill_child`, `graceful_child`, and `run_with_timeout`. The first four test
signals within one process, so you see progress before any child exists.

The last three use real children. One check repeats `graceful_child` eight
times, to catch a parent that signals too early. Others test a program that
ignores `SIGTERM`, which only `SIGKILL` can stop, and confirm that
`run_with_timeout` puts back the `SIGALRM` handler and cancels its timer. A
watchdog thread kills stray children after five seconds, so a mistake appears as
a failed check, not a hang. Every message shows what your function returned
beside what the check expected.
