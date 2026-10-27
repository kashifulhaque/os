---
title: Locks
slug: 19-locks
part: "Part 5 — Concurrency"
summary: Build spin locks, a ticket lock, and Peterson's algorithm from atomic steps, then prove mutual exclusion by exploring every state.
minutes: 60
gpu: false
objectives:
  - Say what a good lock must provide, and why checking a flag and then setting it is not a lock.
  - Build test-and-set, compare-and-swap, and ticket locks as step programs on the interleaving simulator.
  - Trace Peterson's algorithm, and say which hardware assumption it needs.
  - Prove or refute mutual exclusion by exploring every reachable state of a small program.
prereqs:
  - 18-threads-and-race-conditions
exercise: 19-locks
---

# Locks

Lesson 18 ended with a promise. A lock keeps two threads out of the same
critical section, but acquiring a lock reads and writes memory. What stops two
threads from taking the lock at the same time? If the answer is "another lock",
the explanation never ends.

The way out is hardware. CPUs offer a few instructions that read and write a
memory cell in one indivisible step. Every lock in every operating system is
built on one of them. In this lesson you build four locks on the simulator from
lesson 18, and you check each one against every schedule that can happen.

## What you already know

- A race condition means the result depends on how thread steps interleave
  (lesson 18).
- A critical section is the code that only one thread may run at a time. Keeping
  others out is called mutual exclusion.
- An atomic step happens all at once, and nobody sees it half done.
- The simulator runs threads as lists of steps, and a schedule is a list of
  thread ids.

## What a lock must provide

A correct lock gives three guarantees.

1. **Mutual exclusion.** At most one thread is inside the critical section at
   any moment. This is the point of a lock.
2. **Progress.** If the section is empty and a thread wants in, some thread gets
   in. Threads do not wait for an empty room forever.
3. **Fairness**, sometimes called bounded waiting. A thread that wants in
   eventually gets in. No thread is passed over forever.

Mutual exclusion is a *safety* property: something bad never happens. Progress
and fairness are *liveness* properties: something good eventually happens. Your
checker proves safety exactly. Liveness is harder, and the lesson explains what
the ticket lock adds.

## The lock that is not a lock

The obvious lock is one shared cell, `lock`. It holds 0 when free and 1 when
held. To acquire: wait until it is 0, then set it to 1. To release: set it to 0.

```text
0: load f, lock       # read the flag
1: jnz  f, 0          # if it is 1, go back and look again
2: set  lock, 1       # it was free: take it
3: ...critical section...
8: set  lock, 0       # release
```

This looks right, and it is wrong. Between step 1 (the flag was free) and step
2 (take it), another thread can also see the flag free. The check and the set
are two steps, and a thread can run between them.

The following table shows the shortest bad schedule, `[0, 0, 1, 0, 0, 1, 1, 1]`.
Both threads end up inside.

```text
idx  thread  step               result            lock  in critical section
---  ------  -----------------  ----------------  ----  -------------------
 0     T0    load f, lock       f = 0              0
 1     T0    jnz  f, 0          f is 0, fall through
 2     T1    load f, lock       f = 0              0
 3     T0    set  lock, 1                          1
 4     T0    cs_enter                              1     T0
 5     T1    jnz  f, 0          f is 0, fall through
 6     T1    set  lock, 1                          1
 7     T1    cs_enter                              1     T0 and T1   <-- broken
```

Thread 1 acted on a stale reading, as in lesson 18. The cure is the same idea
as before: make the check and the set one atomic step.

> [!KEY]
> A lock is only as good as the atomic instruction under it. Check-then-set must
> be one indivisible step, or two threads can both pass the check.

## Atomic instructions

Hardware provides read-modify-write instructions. Each does a read and a write
as a single step that no other CPU can interrupt. Your simulator has three.

| Instruction | What it does, atomically | x86-64 | ARM64 |
|---|---|---|---|
| `tas reg, addr` (test-and-set) | `reg = mem[addr]`, then `mem[addr] = 1` | `xchg` | `swp` |
| `cas reg, addr, old, new` (compare-and-swap) | if `mem[addr] == old`, set it to `new` and `reg = 1`; otherwise `reg = 0` | `lock cmpxchg` | `cas` |
| `faa reg, addr, n` (fetch-and-add) | `reg = mem[addr]`, then `mem[addr] += n` | `lock xadd` | `ldadd` |

On older ARM chips and on RISC-V, the same job is done by a pair of instructions
called load-linked and store-conditional. The store fails if anyone wrote the
cell in between. The effect is the same.

## Spin locks: test-and-set and compare-and-swap

Test-and-set fixes the broken lock directly. It writes 1 and tells you what was
there before. If the old value was 0, you took a free lock. If it was 1, someone
else holds it, and you changed nothing (1 was already 1).

```text
0: tas r, lock         # r = old lock value; lock = 1, in one step
1: jnz r, 0            # old value was 1: the lock was taken, try again
2..6: critical section
7: set lock, 0         # release
```

A thread that loops on step 0 and 1 is *spinning*. It burns CPU while it waits,
so this is called a *spin lock*.

The compare-and-swap version says the same thing in other words: "if the lock is
0, make it 1, and tell me whether you did".

```text
0: cas r, lock, 0, 1   # r = 1 if the swap happened, 0 if not
1: jz  r, 0            # r is 0: swap failed, try again
2..6: critical section
7: set lock, 0
```

CAS is more general. You can use it to build lock-free counters and stacks,
because it checks that nothing changed since you looked. Test-and-set can only
set a cell to 1.

## The ticket lock

A spin lock is not fair. When the lock frees, any spinner may win, and one
unlucky thread could lose every time. A *ticket lock* fixes that, like the
number dispenser at a deli counter.

There are two counters. `next_ticket` is the number on the next ticket to hand
out. `now_serving` is the number on the sign. To acquire, take a ticket with an
atomic fetch-and-add, then wait until the sign shows your number. To release,
add 1 to the sign.

```text
0: faa t, next_ticket, 1      # t = my ticket; next_ticket += 1
1: load s, now_serving
2: sub s, t                   # s = now_serving - my ticket
3: jnz s, 1                   # not my turn yet: look again
4..8: critical section
9: faa x, now_serving, 1      # call the next ticket
```

Threads enter in the order they took tickets. That is first come, first served,
so no thread waits forever. Linux used ticket spin locks in its kernel from
version 2.6.25. It later switched to queue-based locks (qspinlock, version 4.2
on x86), because all waiters watching one shared cell makes every CPU's cache
fight over it.

### Trace of two threads

Both threads start with `next_ticket = 0` and `now_serving = 0`.

```text
step  thread  action                         t0  t1  next  serving
----  ------  -----------------------------  --  --  ----  -------
  1    T1     faa: takes ticket 0            -   0     1      0
  2    T0     faa: takes ticket 1            1   0     2      0
  3    T0     serving - 1 = -1, not 0: spin  1   0     2      0
  4    T1     serving - 0 = 0: enter                   2      0
  5    T1     (critical section, release)              2      1
  6    T0     serving - 1 = 0: enter                   2      1
```

Thread 1 took ticket 0 first, so it entered first. Thread 0 held ticket 1 and went second.

## Peterson's algorithm

Before CPUs had atomic instructions, Gary Peterson found a way to share a
critical section between two threads using only plain loads and stores. It is
the classic example of why mutual exclusion is subtle.

Each thread has a flag that says "I want in". There is also a shared variable
`turn`. A thread that wants in sets its flag, then politely gives the turn to
the other thread. It waits only while the other thread both wants in and holds
the turn.

```text
 0: set  flag_me, 1      # I want in
 1: set  turn, other     # but you go first
 2: load f, flag_other
 3: jz   f, 8            # other does not want in: enter
 4: load t, turn
 5: add  t, -me          # t = turn - me
 6: jz   t, 8            # turn is mine: enter
 7: jmp  2               # otherwise wait and look again
8..12: critical section
13: set  flag_me, 0      # I am done
```

When both threads arrive together, both set their flag and both write `turn`.
The write that happens last wins, and that thread is the one that waits. The
following trace shows it.

```text
step  thread  action                    flag0  flag1  turn
----  ------  ------------------------  -----  -----  ----
  1    T0     set flag0, 1                1      0     0
  2    T0     set turn, 1                 1      0     1
  3    T1     set flag1, 1                1      1     1
  4    T1     set turn, 0                 1      1     0    <- T1 wrote last
  5    T0     flag1 is 1, turn is 0: T0's turn, enters
  6    T1     flag0 is 1, turn is 0: not T1's turn, waits
```

Peterson's algorithm is a pretty argument, but it needs a promise that real
hardware does not keep. It assumes every thread sees every store in program
order. Modern CPUs buffer stores and let loads pass them, so thread 0's flag
write may not be visible to thread 1 when thread 1 reads it. To make Peterson
work on x86 or ARM, you must add memory-ordering instructions (fences). The
simulator is *sequentially consistent*: steps happen in one global order, so
Peterson works there. Real code uses atomic instructions instead.

## Proving a lock correct by exploring all states

Lesson 18 listed every interleaving. That does not work for a spin lock, because
a spinning thread can run any number of steps. The set of schedules is infinite.

The set of *states* is finite. A *state* is everything that decides what happens
next: memory, each thread's registers, each thread's program counter, and who is
in the critical section. Two schedules that reach the same state have the same
future, so you need to visit each state once.

The method is a *breadth-first search*. Start at the initial state. For each
state you find, try one step of each unfinished thread. A step leads to a state.
If you have not seen that state, record it with the schedule that reached it and
put it on the queue. A spinning thread leads to a state you have seen already,
so the search stops.

```text
                 start (pc 0,0)
                  /          \
            T0 steps        T1 steps
            (pc 1,0)        (pc 0,1)
            /     \         /     \
          ...     ...     ...     ...
     a spin loop returns to a state already visited -> stop there
```

Breadth-first search finds the *shortest* schedule to every state. That makes
the counterexample for a broken lock short and readable, like the eight-step
schedule above.

Once you have every reachable state, two questions are one loop each:

- **Mutual exclusion**: does any state have two threads in the critical section?
  If so, return the shortest schedule that reaches one. If none does, the lock is
  correct for this program, with a proof by exhaustion.
- **Correct result**: in every state where all threads finished, what does the
  counter hold? For a working lock with two threads, the only answer is 2.

The state counts are small. With the counter starting at 0:

| Lock | 2 threads | 3 threads |
|---|---|---|
| Test-and-set | 65 states | 409 states |
| Compare-and-swap | 65 states | 409 states |
| Ticket | 119 states | 1,789 states |

Each of these has no violation, and the final counter always equals the number of
threads. A broken lock fails the same check. The naive check-then-set lock gives
the eight-step counterexample above. The checker proves a statement about *this*
program on *this* simulator. It does not prove a real CPU's behavior, because the
simulator is sequentially consistent.

> [!KEY]
> You can prove a small concurrent program correct by visiting every reachable
> state once. Loops are harmless, because a repeated state is not visited
> again.

## Spinning versus sleeping

A spin lock wastes the CPU while waiting. That is fine when the wait is a few
nanoseconds, because putting a thread to sleep and waking it again costs
microseconds. It is terrible when the holder was descheduled by the kernel: on
one core, a spinner burns its whole time slice waiting for a thread that cannot
run until the spinner stops.

Real mutexes mix the two. They try the atomic instruction first, spin briefly,
and then ask the kernel to put the thread to sleep. On Linux that request is the
`futex` system call. "Futex" stands for "fast userspace mutex". The lock lives
in user memory. An uncontended acquire is one atomic instruction and never
enters the kernel. Only a contended one calls `futex(FUTEX_WAIT)`, and the
release calls `futex(FUTEX_WAKE)`. Python's `threading.Lock` sits on a POSIX
semaphore, which glibc builds on `futex` on Linux.

## Try it on your own machine

1. Count the cost of an uncontended lock in Python.

   ```bash
   python3 -m timeit -s "import threading; l = threading.Lock()" "with l: pass"
   python3 -m timeit "pass"
   ```

   The first number is a fraction of a microsecond. It does not call the kernel when
   nobody else holds the lock.

2. See `futex` calls when threads contend. This is Linux-only and needs
   `strace` installed.

   ```bash
   strace -f -e trace=futex python3 -c "
   import threading, time
   l = threading.Lock()
   l.acquire()
   t = threading.Thread(target=lambda: (l.acquire(), l.release()))
   t.start(); time.sleep(0.1); l.release(); t.join()
   " 2>&1 | head -20
   ```

   Look for `futex(..., FUTEX_WAIT...)` when the second thread blocks, and
   `FUTEX_WAKE` when the first releases.

3. See the atomic instruction a compiler emits. In a C file, write
   `int x; void f(void){ __sync_fetch_and_add(&x, 1); }`, run
   `gcc -O1 -S -o - file.c`, and look for `lock xaddl` on x86-64 or `ldadd` on
   ARM64.

## Build it step by step

The starter provides the full `Machine`, `critical_section()`, and
`run_schedule`. The header comment lists every instruction. You write the lock
programs and the explorer.

1. **`spin_lock_program()`** returns the eight-step list for the test-and-set
   lock. Use `("tas", "r", "lock")`, then `("jnz", "r", 0)`, then
   `critical_section()`, then `("set", "lock", 0)`. The usual mistake is a wrong
   jump target. Targets are list indexes, and the critical section takes five
   slots.

2. **`cas_lock_program()`** is the same shape with `("cas", "r", "lock", 0, 1)`
   and `("jz", "r", 0)`. The mistake is to jump on the wrong register value.
   `cas` sets the register to 1 on success.

3. **`ticket_lock_program()`** takes a ticket with `faa`, loads `now_serving`,
   subtracts your ticket (`sub`), and jumps back while the difference is not
   zero. Release with another `faa` on `now_serving`.

4. **`peterson_program(tid)`** follows the listing above for thread `tid`, with
   cells `flag0`, `flag1`, and `turn`. The other thread is `1 - tid`. The usual
   mistake is to write the turn before the flag, or to give the turn to
   yourself. Give it to the other thread.

5. **`reachable(programs, mem=None)`** runs the breadth-first search. It returns
   a dict from `Machine.key()` to the shortest schedule that reaches that state.
   For each machine in the frontier and each unfinished thread, `copy()` it, call
   `step`, and record the child only if its key is unseen. Forgetting to `copy()`
   changes the parent's state and breaks everything.

6. **`find_violation(programs, mem=None)`** returns the shortest schedule that
   leads to a state where `machine.in_cs` holds two or more thread ids, or
   `None`. Rebuild each state's machine with `run_schedule`.

7. **`final_values(programs, mem, addr)`** returns the sorted list of distinct
   values of `addr` over reachable states in which every thread is done.

## Where this breaks

- **Fairness.** Test-and-set and CAS locks can starve a thread, because nothing
  orders the waiters. The ticket lock cures that at the price of more shared
  cells.
- **Cache traffic.** Each failed `tas` is a write, so spinning threads bounce the
  lock's cache line between CPUs. Real spin locks first read the cell with a
  plain load, and try the atomic instruction only when it looks free
  (test-and-test-and-set). Queue locks give each waiter its own cell to watch.
- **Priority inversion.** A low-priority thread holds a lock, a high-priority
  thread spins for it, and the scheduler keeps preempting the holder for
  middle-priority work. The 1997 Mars Pathfinder lander reset itself repeatedly
  because of this. Real systems use priority inheritance: the holder temporarily
  runs at the waiter's priority.
- **Memory ordering.** As above, Peterson's algorithm fails on real hardware
  without fences. Real lock implementations include the right barriers, so use
  the lock from your language and do not write your own.
- **Interrupts.** A spin lock taken by a thread and also by an interrupt handler
  on the same CPU can deadlock itself. Kernels disable interrupts while holding
  such a lock.
- **Two threads only.** Peterson's algorithm handles two threads. For more, the
  filter and bakery algorithms exist, but they are slower than one atomic
  instruction. This is why hardware support matters.

## Further reading

- [OSTEP chapter 28, Locks](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-locks.pdf) —
  test-and-set, compare-and-swap, ticket locks, and futexes with the same
  evaluation criteria used here.
- [futex(2)](https://man7.org/linux/man-pages/man2/futex.2.html) —
  the Linux system call that blocks and wakes threads on a user-space word.
- [Peterson's algorithm on Wikipedia](https://en.wikipedia.org/wiki/Peterson%27s_algorithm) —
  the proof of mutual exclusion, progress, and bounded waiting, and the note on why it needs memory barriers today.
- [Linux kernel memory barriers](https://www.kernel.org/doc/Documentation/memory-barriers.txt) —
  a long, careful account of how real CPUs reorder memory operations and what fences do.
- [Linux kernel documentation: locking](https://www.kernel.org/doc/html/latest/locking/index.html) —
  how the kernel's spin locks, mutexes, and ticket and queued variants work.

## The exercise

You write four lock programs as lists of simulator steps: `spin_lock_program`,
`cas_lock_program`, `ticket_lock_program`, and `peterson_program`. You then write
the explorer: `reachable` enumerates every reachable machine state,
`find_violation` finds the shortest schedule that breaks mutual exclusion, and
`final_values` lists what the counter can end as.

The checks run each program alone, and then explore two- and three-thread
versions of each lock. They require no violation and a final counter equal to
the number of threads. They also require that the naive check-then-set lock
produces an eight-step counterexample, and that an unprotected counter can end
as either 1 or 2.
