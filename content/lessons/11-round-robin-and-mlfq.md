---
title: Round robin and the multi-level feedback queue
slug: 11-round-robin-and-mlfq
part: "Part 3 — CPU scheduling"
summary: Give every job a turn with time slices, then build a scheduler that learns which jobs are interactive from how they use the CPU.
minutes: 55
gpu: false
objectives:
  - Simulate round robin with a time quantum and a context-switch cost.
  - "Explain the trade-off in choosing a quantum: response time against wasted switching."
  - Simulate an MLFQ with demotion by allotment, I/O-bound jobs, and a periodic priority boost.
prereqs:
  - 10-scheduling-basics
exercise: 11-round-robin-and-mlfq
---

# Round robin and the multi-level feedback queue

Lesson 10 ended with a problem. SJF and SRTF give excellent turnaround, but they need to know how long each job will run. A kernel does not know. It also ignores a second goal: when you type a key, you want the screen to react at once, even if a long compile is running in the background.

Two ideas solve this. The first is *time slicing*: let each job run for a short fixed time, then move on to the next, and keep cycling. Nobody waits long for a first turn. The second is *learning from behaviour*: watch how each job uses the CPU, and give short, interactive jobs priority without being told which they are.

Picture a hair salon with one stylist. Round robin is a rule that says "ten minutes per customer, then the next in line gets a turn". The feedback queue is a receptionist who notices that people who only want a quick trim leave fast, and who lets them skip ahead of people who ask for a full colour.

## What you already know

- A job has an arrival time and a burst, and a timeline lists `(name, start, end)` segments (lesson 10).
- Turnaround is completion minus arrival, and response is first start minus arrival (lesson 10).
- A timer interrupt lets the kernel take the CPU back from a running program (lesson 04).
- A process can block while it waits for I/O, such as a disk read, and the CPU runs something else meanwhile (lesson 06).
- A `collections.deque` is a queue with fast push at one end and pop at the other.

## Round robin

*Round robin* (RR) keeps a first-in, first-out queue of ready jobs. The job at the head runs for at most one *time quantum*, also called a *time slice*. If it is not finished, it goes to the back of the queue. The next job runs. The quantum is a fixed number of ticks. The timer interrupt is what ends a slice: the hardware fires every few milliseconds, and the kernel decides whether to keep the same job or switch.

Work an example. Three jobs arrive at tick 0: A needs 5, B needs 3, C needs 2. The quantum is 2.

- The queue starts as A, B, C.
- A runs 0 to 2 and has 3 left. The queue is B, C, A.
- B runs 2 to 4 and has 1 left. The queue is C, A, B.
- C runs 4 to 6 and finishes. The queue is A, B.
- A runs 6 to 8 and has 1 left. The queue is B, A.
- B runs 8 to 9 and finishes. A runs 9 to 10 and finishes.

The Gantt chart shows one letter per tick.

```text
tick  0         1
      0123456789
RR    AABBCCAABA
```

Compare this with FCFS on the same jobs, running A, then B, then C. The table lists average response and turnaround.

| Policy | Completion times (A, B, C) | Avg response | Avg turnaround |
|---|---|---|---|
| FCFS | 5, 8, 10 | (0 + 5 + 8) / 3 = 4.33 | (5 + 8 + 10) / 3 = 7.67 |
| RR, quantum 2 | 10, 9, 6 | (0 + 2 + 4) / 3 = 2.00 | (10 + 9 + 6) / 3 = 8.33 |

Round robin cuts the average response time by more than half and loses on turnaround. That is the bargain. RR is excellent when you care about the first reaction, and poor when you care about the finish line. In the extreme, two jobs of 100 ticks each with a quantum of 1 finish at ticks 199 and 200. FCFS finishes them at 100 and 200. RR is one of the worst policies for turnaround when jobs are the same length.

> [!KEY]
> Round robin trades turnaround for response time. Every job gets a turn within a bounded wait, but every job also finishes later.

### Who goes first at a slice boundary

Ties need a rule. Suppose A's slice ends at tick 3, and B arrives at exactly tick 3. Which one is at the head of the queue?

The exercise uses the common convention: arrivals up to and including the slice's end tick join the queue first, then the preempted job goes to the back. With A of burst 4, B arriving at 3 with burst 2, and a quantum of 3, the timeline is A from 0 to 3, B from 3 to 5, and A from 5 to 6.

```text
tick  012345
RR    AAABBA
```

Real systems vary here. State the rule in the docstring, as the starter does.

## The cost of a context switch

A *context switch* is the work the kernel does to stop one process and start another. It saves the registers of the old one, loads the registers of the next, and switches the address space (lesson 04). On a modern machine, the direct cost is on the order of microseconds. The hidden cost is larger: the next process finds the CPU's caches full of the previous one's data.

The simulation models the cost as a number of ticks, `switch_cost`, during which no job makes progress. Take two jobs of burst 4, a quantum of 2, and a cost of 1. The next diagram marks switches with a dash.

```text
tick  0         1
      01234567890
RR    AA-BB-AA-BB
```

Eight ticks of work take 11 ticks. Three are overhead, so about 73 percent of the time is useful.

With quantum $q$ and switch cost $c$, and a switch after every slice, the fraction of time spent on real work is

$$
\frac{q}{q + c}
$$

A quantum of 1 with a cost of 1 wastes half the machine. A quantum of 10 ms with a switch cost of 10 microseconds wastes about 0.1 percent. That suggests a very long quantum. But a long quantum raises response time again: with ten ready jobs and a quantum of 100 ms, the last one waits a full second for its first turn. Choosing the quantum is a balance between the two.

Three details of the model matter:

- A switch costs time only when the next job differs from the one that ran last. A job that runs again because nobody else is ready pays nothing.
- A job that starts after an idle gap pays nothing, because the CPU was already doing nothing.
- The first job of the whole run pays nothing.

> [!WARNING]
> Do not charge a switch cost when a job continues alone. A single job with a quantum of 2 and a cost of 1 must run its full burst with no gaps.

## Learning from behaviour: the multi-level feedback queue

Round robin treats every job the same. But a text editor and a video encoder are not the same. The editor runs for a millisecond after each key press, then waits. The encoder wants every cycle it can get. A good scheduler gives the editor quick turns and gives the encoder long ones.

The *multi-level feedback queue* (MLFQ) discovers this without being told. It keeps several queues, each with its own priority. The idea is that a job's recent behaviour predicts its near future. A job that gave up the CPU early, probably for I/O, is likely interactive. A job that burned its whole slice is likely a hog.

The rules, as the exercise implements them, are these.

1. The scheduler runs a job from the highest non-empty queue.
2. Jobs in the same queue take turns round-robin, each for that queue's quantum.
3. A job that arrives starts in the top queue.
4. Each level has an *allotment*: the total CPU time a job may use there. When a job uses it all, the job drops one level. A job that blocks for I/O keeps its level and its used allotment.
5. After a fixed period, every job returns to the top queue. That is the *priority boost*.

The exercise configures MLFQ as a list of `(quantum, allotment)` pairs, one per level, highest priority first. For example `[(2, 4), (4, 8)]` means: at level 0, slices of 2 ticks and an allotment of 4. At level 1, slices of 4 and an allotment of 8. The bottom level never demotes further.

```text
level 0 (top)   quantum 2, allotment 4    queue: A B
level 1         quantum 4, allotment 8    queue: C
```

### Example: a hog and an I/O-bound job

Take a CPU hog `H` with 6 ticks of work, and an I/O-bound job `I` with 3 ticks of work that asks for I/O after every tick and waits 1 tick. The levels are `[(2, 4), (4, 8)]`. Both arrive at tick 0.

- Tick 0 to 2: `H` runs. It uses its whole quantum of 2, so it goes to the back of level 0. The queue is `I`, `H`.
- Tick 2 to 3: `I` runs for 1 tick, asks for I/O, and blocks until tick 4. It stays at level 0.
- Tick 3 to 5: `H` runs. `I` wakes at tick 4, but it is in the same queue level as `H`, so `H` is not interrupted. `H` has used 4 ticks, which is its level-0 allotment, so it drops to level 1.
- Tick 5 to 6: `I` runs, asks for I/O, and blocks until tick 7. Only `H` is ready.
- Tick 6 to 7: `H` runs at level 1.
- Tick 7 to 8: `I` wakes at level 0, which outranks level 1. It preempts `H`, runs its third and last tick, and finishes.
- Tick 8 to 9: `H` runs its last tick.

```text
tick  012345678
MLFQ  HHIHHIHIH
```

The I/O-bound job stayed at the top and got the CPU the moment it woke. The hog sank. Nobody told the scheduler which job was which.

### Why the allotment exists

Suppose a scheduler demoted a job only when it used a full quantum. A hog could issue a trivial I/O request right before each quantum ends, look interactive, stay on top, and take most of the CPU. Counting total CPU time at the level, however the job gives it up, closes that hole.

### Why the boost exists

Two problems remain. A steady stream of interactive jobs can starve the jobs below forever. And a job can change behaviour, yet stay at the bottom.

The *priority boost* fixes both. Every `boost_every` ticks, every job returns to level 0 with its allotment reset. Starved jobs get a turn, and a job that changed its nature is reclassified.

Work a small case. Two hogs, A and B, with 6 ticks each, levels `[(1, 1), (2, 2)]`. Without a boost, both sink to level 1 after a tick each, and then alternate with a quantum of 2:

```text
tick      0         1
          012345678901
no boost  ABAABBAABBAB
```

With `boost_every=5`, the scheduler stops at tick 5. B is running, so it moves to the front of its queue, and then both jobs go to level 0 with allotment 0. B runs one tick at level 0 and drops again, then A runs one tick and drops, and so on:

```text
tick      0         1
          012345678901
boost 5   ABAABBABBAAB
```

The totals barely change in this tiny case, because both jobs are hogs. The point is the mechanism: every five ticks, every job gets another turn at the top.

> [!KEY]
> MLFQ guesses a job's nature from its past. Allotments make the guess hard to game, and the periodic boost keeps low-priority jobs from starving and lets a job change class.

### The per-tick order in the exercise

MLFQ has many small decisions, and the order matters. The simulator advances one tick at a time and always does these steps in this order:

1. Boost, if the clock is a positive multiple of `boost_every`.
2. Admit arrivals, and jobs whose I/O has finished, to the back of their queue, in name order.
3. Preempt the running job if a higher-priority queue is not empty. The preempted job goes to the front of its own queue.
4. If no job is running, pick the head of the highest non-empty queue, with a fresh quantum.
5. Run one tick, then handle the job: finished, demoted, blocked for I/O, or sent to the back of its queue when the quantum is used up.

The docstring in `starter.py` states each step precisely.

## Try it on your own machine

These commands are for Linux.

1. Read the default time slice of the real-time round-robin policy `SCHED_RR`. The value is in milliseconds, and the default is 100.

   ```bash
   cat /proc/sys/kernel/sched_rr_timeslice_ms
   ```

2. Count context switches system-wide. The `cs` column of `vmstat` shows switches per second. Run it while you do something heavy in another terminal, and watch it grow.

   ```bash
   vmstat 1 5
   ```

3. Measure the cost of a switch from Python. Two processes pass a byte back and forth through pipes, which forces the kernel to switch each time. Pin both to one core so that the switches are real:

   ```bash
   taskset -c 0 python3 -c "
   import os, time
   a_r, a_w = os.pipe(); b_r, b_w = os.pipe()
   if os.fork() == 0:
       os.close(a_w)
    while os.read(a_r, 1): os.write(b_w, b'x')
       os._exit(0)
   start = time.perf_counter()
   for _ in range(20000):
       os.write(a_w, b'x'); os.read(b_r, 1)
   elapsed = time.perf_counter() - start
   print(f'{elapsed / 40000 * 1e6:.1f} microseconds per switch, including the pipe calls')
   os.close(a_w); os.wait()
   "
   ```

   The number includes the pipe system calls and Python's own overhead, so it overstates the switch alone. Expect a few to a few tens of microseconds.

Linux does not use a classic MLFQ for ordinary processes. Solaris, the BSD family, and Windows use ideas from it. Lesson 12 covers Linux's scheduler.

## Build it step by step

`Job`, `merge_slices`, and `gantt` are given. You write two functions, `round_robin` and `mlfq`.

1. **`round_robin(jobs, quantum, switch_cost=0)`** returns a timeline. Sort jobs by `(arrival, name)`. Write a small `admit(until)` helper that moves every job with `arrival <= until` into a `deque`. Loop: admit up to the clock, jump to the next arrival if the queue is empty (or stop), pop the head, run it for `min(quantum, remaining)`, admit again, and only then push the job back if it has work left. The most common mistake is to push the job back before admitting arrivals, which puts it ahead of jobs that arrived during its slice.
2. **Add the switch cost** to the same function. Remember the last job to run and the tick it stopped. When the next job has a different name and starts exactly at that tick, add `switch_cost` to the clock before the slice. Raise `ValueError` when `quantum < 1`.
3. **`mlfq(jobs, levels, boost_every=0)`**, part one: the plain version. Keep one `deque` per level and a dictionary of per-job state: level, ticks used at this level, ticks left, and CPU since the last I/O. Run one tick per loop and apply the five steps in order. Leave out boost and I/O at first. The mistake to avoid is to demote and re-queue in the wrong order: check "finished" before "demote".
4. **Add I/O.** A job with `io_every` blocks when its CPU use since the last I/O reaches that number. Keep a list of `(wake_time, name)` pairs. In step 2, move jobs whose wake time has arrived to the back of their level's queue. A job that finishes on the same tick does no I/O.
5. **Add the boost.** At the start of the tick, when `clock % boost_every == 0`, push the running job to the front of its queue, move every queued job to level 0, and zero every allotment, including those of blocked jobs.

At the end, return `merge_slices(ticks)` so that one-tick segments join. The `__main__` block prints the hog and I/O example, `HHIHHIHIH`.

## Where this breaks

- **The quantum has no right answer.** A short one hurts throughput, and a long one hurts response. Real systems pick values from experience, and MLFQ uses short slices on top and long ones below.
- **Gaming.** A program can still try to trick a scheduler, such as yielding right before a slice ends. Allotments close the simplest trick, and others remain.
- **Many knobs.** The number of levels, the quanta, the allotments, and the boost period all change behaviour. Real systems tune them from tables, and some let an administrator adjust them.
- **Not proportional.** MLFQ says who goes first. It does not say that one job should get twice the share of another. Lesson 12 covers that.
- **Multiple cores.** Our model has one CPU. A real kernel keeps queues per core and moves tasks between cores to balance the load.

## Further reading

- [OSTEP, chapter 8: Multi-level feedback queue](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-mlfq.pdf) develops the five rules in this lesson step by step, including gaming and the boost.
- [OSTEP, chapter 7: CPU scheduling](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf) introduces round robin and shows the quantum trade-off.
- [sched(7)](https://man7.org/linux/man-pages/man7/sched.7.html) explains Linux's policies, including `SCHED_RR` and its default time slice.
- [sched_rr_get_interval(2)](https://man7.org/linux/man-pages/man2/sched_rr_get_interval.2.html) shows how a program asks for its round-robin quantum.
- [chrt(1)](https://man7.org/linux/man-pages/man1/chrt.1.html) sets a process's policy and priority from the shell.

## The exercise

You write `round_robin(jobs, quantum, switch_cost=0)` and `mlfq(jobs, levels, boost_every=0)`. Both return a timeline of `(name, start, end)` tuples. Touching segments of one job are merged.

Six checks cover round robin: rotation, arrivals queued ahead of the preempted job, an arrival at the exact end of a slice, a lone job, the switch cost, and the error for a quantum below 1. Four checks cover MLFQ: demotion, preemption of a hog by a short arrival, an I/O-bound job that stays on top, and the priority boost. The comments in each check work out the expected timeline by hand.
