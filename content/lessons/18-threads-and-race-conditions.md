---
title: Threads and race conditions
slug: 18-threads-and-race-conditions
part: "Part 5 — Concurrency"
summary: See why two threads adding to one counter lose updates, count every possible schedule, and fix the bug with a lock.
minutes: 55
gpu: false
objectives:
  - Say what a thread is, and what a thread shares with its siblings and what it keeps private.
  - Break `counter += 1` into atomic load, add, and store steps, and enumerate every interleaving of two threads.
  - Find the schedule that loses an update, and say why a lock removes it.
  - "Explain honestly why Python's GIL does not make `counter += 1` safe."
prereqs:
  - 06-processes
  - 11-round-robin-and-mlfq
exercise: 18-threads-and-race-conditions
---

# Threads and race conditions

A program that does one thing at a time wastes your machine. A web server that
reads a file blocks every other visitor while the disk spins. A game that
decodes video freezes its menus. The fix is to let one program run several
streams of work at once. Each stream is called a *thread*.

Threads bring the first bug in this course that you cannot catch by reading the
code line by line. Two threads touch the same variable. Most runs work. Once in
a while the answer is wrong, and the next run is fine again. This kind of bug
is called a *race condition*, and it is the reason the rest of Part 5 exists.

In this lesson you build a tiny machine that runs threads one atomic step at a
time. You will list every possible order of those steps, find the one that
breaks a counter, and then fix the counter with a real lock.

## What you already know

- A process is a running program with its own address space, and the kernel
  switches between processes (lessons 06 and 11).
- A timer interrupt can stop a running program at almost any instruction, and
  the kernel saves and restores its registers (lesson 04).
- Memory is a long list of cells, and a CPU reads a cell into a register before
  it computes on it (lesson 02).
- A Python function can take a list, a dict, and a lock-like object and return a
  result.

## What a thread is

A *thread* is one stream of instructions that the kernel can schedule. A
process always has at least one. You can think of a process as an office, and
each thread as a worker in it. The workers share the office: its desks, files,
and whiteboards. Each worker still has a private notepad and a finger on the
page they are reading.

In computer terms, threads in one process share:

- the code,
- the global variables and the heap (memory from `malloc` or Python objects),
- open files.

Each thread keeps its own:

- registers, including the program counter that says which instruction is next,
- stack, which holds its function calls and local variables.

The following diagram shows one process with three threads.

```text
        one process: one address space
  +------------------------------------------+
  |  code        (shared)                    |
  |  globals     (shared)   counter = 7      |
  |  heap        (shared)                    |
  +------------+------------+----------------+
  |  thread 0  |  thread 1  |  thread 2      |
  |  pc, regs  |  pc, regs  |  pc, regs      |
  |  stack     |  stack     |  stack         |
  +------------+------------+----------------+
       private      private      private
```

Compare this with `fork` from lesson 07. A child process gets a *copy* of the
parent's memory, so writes in one are invisible to the other. Threads share
memory directly. Sharing is cheap and fast, and it is also the source of every
bug in this lesson.

The kernel schedules threads the same way it schedules processes. On Linux, a
thread is a kernel object that `clone` creates with the flag "share my address
space". The scheduler sees each thread as an independent runnable task. With
several CPU cores, two threads of one process can run at the same instant. With
one core, the scheduler time-slices them. Either way, you cannot know in what
order their instructions will run.

## The bug: counter += 1

Here is a program with two threads. Both run the same function.

```python
counter = 0

def worker():
    global counter
    counter += 1
```

One line of Python looks like one action. A CPU does not see it that way. It
cannot add to a memory cell directly. It must read the cell into a register,
change the register, and write the register back. The line becomes three steps.

```text
load  r, counter     # r = counter       (read memory into a register)
add   r, 1           # r = r + 1         (compute inside the register)
store counter, r     # counter = r       (write the register to memory)
```

Each thread has its own `r`, because registers are private. The cell `counter`
is shared.

Suppose the timer interrupt hits thread 0 right after its `load`. The kernel
switches to thread 1, which runs all three steps. Then thread 0 resumes. The
following table shows the order, with `counter` starting at 0.

```text
step  thread  operation          r of T0  r of T1  counter
----  ------  -----------------  -------  -------  -------
 1    T0      load  r, counter      0        -        0
 2    T1      load  r, counter      0        0        0
 3    T1      add   r, 1            0        1        0
 4    T1      store counter, r      0        1        1
 5    T0      add   r, 1            1        1        1
 6    T0      store counter, r      1        1        1
```

Two threads each added 1, and the counter says 1. Thread 0's `r` held a stale
copy of the counter from step 1. Thread 1's update at step 4 was overwritten at
step 6. This failure is called a *lost update*.

> [!KEY]
> A line of high-level code is several machine steps. Another thread can run
> between any two of them. When the result depends on which order the steps
> happen in, you have a race condition.

## Atomic steps and schedules

To study this bug without waiting for bad luck, you will model it. The model
has four ideas.

- A *step* is an operation that happens all at once. Nobody can see it half
  done. Computer scientists call such an operation *atomic*, from the Greek
  word for "cannot be cut". In the model, `load`, `add`, and `store` are each
  atomic.
- A *program* is a list of steps for one thread.
- A *schedule* is a list of thread ids. The schedule `[0, 1, 0]` means: run one
  step of thread 0, then one step of thread 1, then one more step of thread 0.
- An *interleaving* is a schedule in which each thread runs exactly its own
  number of steps, in its own order.

The kernel's scheduler picks one schedule on every run. If you can list all
schedules, you can see every outcome the real machine could produce.

The program for `counter += 1` in the simulator is a list of tuples.

```python
[("load", "r", "counter"), ("add", "r", 1), ("store", "counter", "r")]
```

The `Machine` you work with holds shared memory in a dict, and a register dict
and program counter for each thread. Its `step(tid)` method runs thread `tid`'s
next step.

## Counting the interleavings

Two threads with three steps each have 20 interleavings. You can count them
without listing. A schedule has six slots. You choose which three belong to
thread 0, and thread 1 gets the rest. That is "6 choose 3", which is 20.

For threads with $n_1, n_2, \dots$ steps, the count is

$$
\frac{(n_1 + n_2 + \cdots)!}{n_1! \, n_2! \cdots}
$$

Here are a few values.

| Threads | Steps each | Interleavings |
|---|---|---|
| 2 | 3 | 20 |
| 2 | 5 | 252 |
| 3 | 3 | 1,680 |
| 2 | 10 | 184,756 |
| 4 | 10 | about $4.7 \times 10^{21}$ |

The count explodes. A real program has billions of steps, so nobody can test
all of its schedules. That is why concurrency bugs survive testing: the bad
schedule exists, but the test machine rarely picks it.

For this lesson, two threads of three steps are small enough to list by hand.
The simulator does it in under a millisecond.

### What the 20 schedules do

Run all 20 interleavings of two incrementing threads, starting with the counter
at 0. Only two schedules keep both updates: all of thread 0 first, or all of
thread 1 first. In the other 18, each thread loads before the other stores, so
both write 1.

```text
final counter   schedules   example
-------------   ---------   ------------------------------------
      2              2      [0,0,0,1,1,1]   one thread, then the other
      1             18      [0,0,1,0,1,1]   T1 loads before T0 stores
```

Most schedules are bad. In the real world the kernel rarely picks them for such
a short window, which is why the bug is rare but not absent. Make the window
longer, with more steps between the load and the store, and it shows up
constantly.

Here is the first losing schedule in lexicographic order, `[0, 0, 1, 0, 1, 1]`,
worked step by step.

```text
schedule index  thread  step              r0  r1  counter
--------------  ------  ----------------  --  --  -------
      0         T0      load  r, counter   0   -     0
      1         T0      add   r, 1         1   -     0
      2         T1      load  r, counter   1   0     0
      3         T0      store counter, r   1   0     1
      4         T1      add   r, 1         1   1     1
      5         T1      store counter, r   1   1     1
```

Thread 1 reads the counter at index 2, before thread 0's store at index 3. It
computes from stale data.

## Taming the race with a lock

The bug is that two threads are inside the read-modify-write at the same time.
The fix is to let only one thread in. The region of code that must not be
shared is called a *critical section*. Keeping other threads out of it is
called *mutual exclusion*, or "mutex" for short.

A *lock* provides mutual exclusion. It has two operations. `acquire` waits
until the lock is free, then takes it. `release` gives it back. A lock is like
the key to a single toilet in a café. Whoever holds the key is inside, and
everyone else waits at the counter.

```python
import threading

lock = threading.Lock()

def worker():
    global counter
    with lock:          # acquire on entry, release on exit
        counter += 1
```

The `with` statement releases the lock even if the body raises an exception.
Always use it in place of manual `acquire` and `release` calls.

With the lock, the bad schedules cannot happen. Thread 1's `acquire` has to wait
until thread 0 releases.

```text
T0: acquire  load  add  store  release
T1:    (waits at acquire ...)     acquire  load  add  store  release
```

> [!KEY]
> A lock makes a group of steps behave as one atomic step. Other threads see the
> state before the group or after it, never the middle.

How the lock itself works is a puzzle: `acquire` also has to read and write
memory, so what stops two threads from taking the lock together? Lesson 19
answers it. For the moment, treat `threading.Lock` as provided by the system.

## Python's GIL does not save you

If you have heard of Python's *global interpreter lock* (GIL), you might think
the problem cannot happen in Python. The GIL is a lock inside the standard
CPython interpreter. Only the thread that holds it can run Python bytecode, so
two Python threads never execute bytecode at the same instant. The interpreter
hands the GIL from one thread to another about every 5 milliseconds, and also
when a thread blocks on I/O.

The GIL protects the interpreter's own data. It does not protect yours. A
thread can lose the GIL between any two bytecode instructions, and `counter +=
1` is several of them. So the race is real.

It is also rare in simple code, and that surprises people. Running a plain
`counter += 1` loop in four threads on CPython 3.12 gave the correct answer in
every trial for the author. Since version 3.10, the interpreter checks for a
thread switch only at certain points, such as a function call or the end of a
loop iteration. A tiny update rarely gets split.

Add a function call between the read and the write, and the race appears at
once.

```python
import threading

total = 0

def add_one(a, b):
    return a + b

def work(n):
    global total
    for _ in range(n):
        v = total            # load
        v = add_one(v, 1)    # a call: the interpreter may switch threads here
        total = v            # store

threads = [threading.Thread(target=work, args=(200_000,)) for _ in range(4)]
for t in threads: t.start()
for t in threads: t.join()
print(total)                 # 800000 expected; CPython 3.12 prints far less
```

On the author's machine this printed about 400,000. The exact number differs on
every run. This is why the simulator matters: Python hides the bug most of the
time, but the model shows every schedule the bug could take. The free-threaded
builds of CPython 3.13 and later remove the GIL entirely, so races in Python
code become as likely as in any other language.

> [!WARNING]
> A test that passes a thousand times does not prove code is race-free. A race
> needs one unlucky schedule. Reason about all schedules, as the simulator does,
> or use a lock.

## Try it on your own machine

Run these on a Linux or macOS terminal.

1. List the threads of a real process. This is Linux-only.

   ```bash
   ls /proc/self/task
   ps -eLf | head
   ```

   Each entry in `/proc/<pid>/task` is a thread. `ps -eLf` adds an `LWP` column
   (light-weight process, the kernel's name for a thread) and an `NLWP` column
   with the thread count. A web browser shows dozens of threads.

2. Watch a Python process create threads.

   ```bash
   python3 -c "
   import threading, os, time
   ts = [threading.Thread(target=time.sleep, args=(1,)) for _ in range(3)]
   [t.start() for t in ts]
   print(sorted(os.listdir('/proc/self/task')))
   [t.join() for t in ts]
   "
   ```

   You should see four ids: the main thread and three sleepers. Linux-only
   again.

3. Reproduce the lost update with the snippet from the previous section. Try
   two, four, and eight threads, and watch the total drift.

4. Count the interleavings of two threads with `math.comb(6, 3)` in Python. It
   prints 20.

## Build it step by step

Open the exercise. The simulator's `Machine` class and the file's header
comment describe the step format. You write the rest.

1. **`Machine.step(tid)`** runs the next step of thread `tid` and advances that
   thread's `pc`. Look at `self.programs[tid][self.pc[tid]]`, read `op[0]`,
   and branch on `"load"`, `"add"`, `"store"`, and `"set"`. Registers live in
   `self.regs[tid]` and memory in `self.mem`. A cell never written reads as 0
   (use `dict.get(key, 0)`). Raise `ValueError` for a finished thread or an
   unknown operation. The usual mistake is one shared register dict: thread 1's
   `r` must not be thread 0's `r`.

2. **`increment_program(addr="counter")`** returns the three-step list for
   `counter += 1` on the given address. Use one register name.

3. **`run_schedule(programs, schedule, mem=None)`** makes a fresh `Machine`,
   runs each thread id in order, and returns the machine. If a thread is
   already finished, skip that entry. Do not modify the caller's `mem`; the
   `Machine` constructor already copies it.

4. **`interleavings(lengths)`** returns every schedule in which thread `i`
   appears `lengths[i]` times. Use recursion. Keep a list of remaining counts.
   For each thread with steps left, take one, recurse, then put it back.
   Looping over thread ids in ascending order gives lexicographic output. The
   common mistake is to generate all permutations of the list and filter out
   duplicates, which is thousands of times slower.

5. **`outcome_counts(programs, mem, addr)`** runs every interleaving and counts
   how often each final value of `addr` appears. It returns a dict from value
   to count. For two incrementers it is `{2: 2, 1: 18}`.

6. **`find_lost_update(programs, mem, addr, expected)`** returns the first
   interleaving whose final value is not `expected`, or `None`.

7. **`SafeCounter`** is a class with `increment()` and a `value` property. It
   makes a `threading.Lock` in `__init__` and uses it for both. Reading `value`
   under the lock is correct practice even though a plain read looks harmless.

8. **`increment_with_lock(n_threads, n_iters)`** starts real threads that each
   add 1 to a shared total `n_iters` times under one lock, joins them all, and
   returns the total. Create the lock once, before the threads. Pass `timeout`
   to `join`, and raise `RuntimeError` if a thread is still alive afterwards. A
   missed `join` returns the total too early.

## Where this breaks

Locks fix the race and cost something.

- **Speed.** Taking a lock is slower than a plain add, and threads waiting for a
  lock do no work. A program that locks everything runs no faster than one
  thread. Real systems keep critical sections short and shrink what is shared.
- **Forgotten locks.** The compiler cannot tell which variable a lock guards.
  Tools help: ThreadSanitizer (`-fsanitize=thread` in GCC and Clang) watches a
  running program and reports unsynchronised access.
- **Reordering.** Real CPUs and compilers reorder memory operations for speed.
  Your simulator runs steps in the order written, which is a simplification
  called *sequential consistency*. Real hardware is weaker. Locks also contain
  the memory barriers that stop the reordering.
- **Lock granularity.** One big lock is easy to get right and slow. Many small
  locks are fast and invite the deadlocks of lesson 21.
- **Testing.** You cannot test a race away. Design for correctness, then use
  stress tests with a small thread-switch interval, as this exercise's checks
  do, to give bugs a chance to appear.

## Further reading

- [OSTEP chapter 26, Concurrency: An introduction](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-intro.pdf) —
  the same counter example, with assembly and a full interleaving table.
- [OSTEP chapter 27, Thread API](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-api.pdf) —
  `pthread_create`, `pthread_join`, and locks in C.
- [Python `threading` documentation](https://docs.python.org/3/library/threading.html) —
  the `Thread`, `Lock`, and `join` API you use in the exercise.
- [pthreads(7)](https://man7.org/linux/man-pages/man7/pthreads.7.html) —
  the Linux overview of POSIX threads.
- [PEP 703](https://peps.python.org/pep-0703/) —
  the proposal that made CPython's GIL optional, with a clear account of what
  the GIL does and does not guarantee.

## The exercise

You build the interleaving simulator in `starter.py`. `Machine.step` executes
atomic steps, `run_schedule` runs a whole schedule, `interleavings` lists every
schedule, `outcome_counts` and `find_lost_update` expose the lost update, and
`increment_program` is the program under test.

You then fix the bug with real threads in `SafeCounter` and
`increment_with_lock`. The checks verify the simulator against hand-computed
tables: 20 interleavings, 2 good schedules and 18 lost updates, and the first
losing schedule `[0, 0, 1, 0, 1, 1]`. The thread checks lower the interpreter's
switch interval to make races likely, then require an exact total. They fail
rather than hang when a thread does not finish.
