---
title: "Proportional share: lottery, stride, and CFS"
slug: 12-proportional-share-scheduling
part: "Part 3 — CPU scheduling"
summary: Share the CPU in proportion to tickets or weights, and build the virtual-runtime idea behind Linux's default scheduler.
minutes: 55
gpu: false
objectives:
  - Implement lottery scheduling with a seeded random generator and explain why its short-run shares are noisy.
  - Implement stride scheduling and show that it hits the ticket ratio exactly.
  - "Implement a CFS-style scheduler: weights from nice values, vruntime, and picking the smallest vruntime."
prereqs:
  - 11-round-robin-and-mlfq
exercise: 12-proportional-share-scheduling
---

# Proportional share: lottery, stride, and CFS

Lesson 10 asked who should finish first. Lesson 11 asked who should react first. A third question is more common on real machines: who deserves how much of the CPU?

Imagine a server shared by two customers. One pays for three quarters of the machine and the other for a quarter. Neither wants a promise about which job is shorter. They want a *share*: over a long time, the first gets about 75 percent of the CPU, and the second gets about 25 percent. A policy that delivers shares like these is called *proportional-share* or *fair-share* scheduling.

This lesson builds three such schedulers. Lottery scheduling uses chance. Stride scheduling gets the same result with a counter and no chance at all. The Completely Fair Scheduler, or CFS, is Linux's version of the counter idea, with weights taken from `nice` values.

## What you already know

- A job has a name, and a timeline lists `(name, start, end)` segments (lesson 10).
- Round robin hands out equal turns, and a quantum is the length of one turn (lesson 11).
- A seeded generator, `random.Random(seed)`, repeats the same numbers every run.
- A running sum over a list shows where a number falls among ranges.
- The `nice` command makes a process less eager for the CPU (lesson 10).

## Lottery scheduling

Give every job some *tickets*. Each time the scheduler needs to choose, it draws one ticket number at random. The job holding that ticket runs for one time slice.

Tickets are the share. If A holds 75 tickets and B holds 25, there are 100 tickets in total. A holds 75 percent of them, so over many draws it wins about 75 percent of the slices.

To find the winner, draw a number from 0 up to the total, exclusive. Then walk the jobs in a fixed order, keeping a running sum of tickets. The winner is the first job whose running sum goes past the drawn number. Here are the ranges for A and B.

```text
ticket number   0 ........................ 74 | 75 ........ 99
owner           A (75 tickets)                | B (25 tickets)
```

A draw of 74 picks A. A draw of 75 picks B. The exercise sorts job names so that the ranges are the same on every run.

In Python the shape is:

```python
winning = rng.randrange(total)
running = 0
for name in sorted(tickets):
    running += tickets[name]
    if running > winning:
        ...  # this job wins
```

The exercise passes in the generator as `rng`, a `random.Random`. That makes the scheduler testable. A check passes `random.Random(0)` and gets the same winners every time. Another check passes a stub that returns scripted numbers, so the expected winner of each draw is known by hand.

Lottery scheduling is simple, and it needs no per-job state beyond the ticket count. Adding a job means adding its tickets to the total. It has a flaw: chance. Over $n$ slices, the share of A has a standard deviation of

$$
\sqrt{\frac{p(1-p)}{n}}
$$

where $p$ is A's ticket fraction. For $p = 0.75$, that is about 4.3 percentage points after 100 slices, and 0.43 points after 10,000. In the long run, the lottery is fair. In the short run, a job can be unlucky several times in a row.

> [!KEY]
> Lottery scheduling is fair on average. Randomness gives it simplicity and costs it precision over short runs.

## Stride scheduling

Can we get the same shares without randomness? Yes. *Stride scheduling* replaces the lottery with a counter.

Each job gets a *stride*, which is a big constant divided by its tickets. More tickets mean a smaller stride. Each job also has a *pass* value, which starts at 0. The rule is:

1. Pick the job with the smallest pass.
2. Run it for one slice.
3. Add its stride to its pass.

A job with a small stride has its pass grow slowly, so it stays at the bottom and gets picked often. The exercise uses a constant of 10,000, called `STRIDE1`, and breaks ties by name.

Work an example. Jobs A, B, and C hold 100, 50, and 250 tickets. Their strides are 10,000 / 100 = 100, 10,000 / 50 = 200, and 10,000 / 250 = 40.

| Slice | Pick | A pass | B pass | C pass |
|---|---|---|---|---|
| start | — | 0 | 0 | 0 |
| 1 | A | 100 | 0 | 0 |
| 2 | B | 100 | 200 | 0 |
| 3 | C | 100 | 200 | 40 |
| 4 | C | 100 | 200 | 80 |
| 5 | C | 100 | 200 | 120 |
| 6 | A | 200 | 200 | 120 |
| 7 | C | 200 | 200 | 160 |
| 8 | C | 200 | 200 | 200 |

At slice 1, all three tie at 0, so A wins by name. At slice 2, B and C tie at 0, and B wins. After eight slices every pass equals 200. A ran twice, B once, and C five times. The ticket ratio 100 : 50 : 250 reduces to 2 : 1 : 5. The match is exact, and it repeats every eight slices.

The picks in order are `A B C C C A C C`. A lottery with the same tickets would match this ratio only on average.

Stride scheduling has a weakness. If a job arrives later, what pass value does it start with? Zero would let it run alone until it caught up with everyone else. The fix is to start it at the smallest pass among the others. That idea returns in CFS.

## The Completely Fair Scheduler

Linux merged the *Completely Fair Scheduler* (CFS) in version 2.6.23, in 2007. Its idea resembles stride scheduling. Instead of a pass that grows by a stride, each task has a *virtual runtime*, written `vruntime`, which grows as the task uses the CPU, and the task with the smallest value runs next.

CFS imagines an ideal machine. If four tasks are ready, an ideal CPU would run all four at once, each at a quarter speed. A real CPU cannot, so CFS tracks how far each task has fallen behind that ideal and runs the one that has had the least. That is the one with the smallest `vruntime`.

### Weights and nice values

Tasks differ in importance. A *nice value* ranges from −20 to 19. Nice 0 is normal. A higher number means a nicer task, which takes less. Linux turns each nice value into a *weight* with a fixed table. Nice 0 has weight 1024. Each step in nice changes the weight by a factor of about 1.25. A few entries are in the table below.

| Nice | Weight |
|---|---|
| −20 | 88761 |
| −5 | 3121 |
| 0 | 1024 |
| 5 | 335 |
| 19 | 15 |

The exercise's starter holds the whole 40-entry table, `NICE_TO_WEIGHT`, with nice −20 at index 0. You write `weight_for_nice(nice)`, which looks a weight up and rejects values outside −20 to 19.

### Virtual runtime

When a task runs for $t$ ticks, its `vruntime` grows by

$$
t \times \frac{1024}{\text{weight}}
$$

A nice-0 task has weight 1024, so its `vruntime` equals its real run time. A heavier task's `vruntime` grows more slowly, so it stays lowest more often and runs more. A lighter task's grows faster, and it runs less. Picking the smallest `vruntime` therefore produces shares in proportion to the weights.

> [!KEY]
> CFS always runs the task with the smallest virtual runtime. Weights scale how fast virtual runtime grows, and that turns an equal-looking rule into proportional shares.

### Worked example: nice 0 against nice 5

Task A has nice 0, so its `vruntime` grows by 1.00 per tick. Task B has nice 5, weight 335, so it grows by 1024 / 335 = 3.06 per tick. Both are CPU-bound. The decision at each tick picks the smaller `vruntime`, and ties go to the name that sorts first.

| Tick | Pick | A vruntime after | B vruntime after |
|---|---|---|---|
| 0 | A | 1.00 | 0.00 |
| 1 | B | 1.00 | 3.06 |
| 2 | A | 2.00 | 3.06 |
| 3 | A | 3.00 | 3.06 |
| 4 | A | 4.00 | 3.06 |
| 5 | B | 4.00 | 6.11 |
| 6 | A | 5.00 | 6.11 |
| 7 | A | 6.00 | 6.11 |
| 8 | A | 7.00 | 6.11 |
| 9 | B | 7.00 | 9.17 |

The Gantt chart shows B getting a turn about once in every 3 or 4 ticks.

```text
tick  0123456789
CFS   ABAAABAAAB
```

In the long run, A gets 1024 / (1024 + 335), which is 75.3 percent, and B gets 24.7 percent. A check in the exercise runs 2,000 ticks and compares B's share with that fraction.

### Late arrivals and `min_vruntime`

A task that arrives at tick 5 has used no CPU, so its `vruntime` would be 0. The other task's `vruntime` is already 5. If the late arrival started at 0, it would run alone for 5 ticks to catch up. That would starve everyone else.

CFS avoids this with `min_vruntime`, a floor that tracks the smallest `vruntime` among runnable tasks and never decreases. A task that arrives, or wakes from a long sleep, starts at roughly that floor. In the exercise, the arriving job's `vruntime` is exactly `min_vruntime`.

Take A with 10 ticks of work, and B arriving at tick 5 with 3 ticks. Both have nice 0. A runs alone from 0 to 5 and has `vruntime` 5.0. B joins at 5.0 too. They tie, so A runs tick 5, then B runs tick 6, and they alternate.

```text
tick  0         1
      0123456789012
CFS   AAAAAABABABAA
```

Written without gaps, the exercise's timeline is A 0–6, B 6–7, A 7–8, B 8–9, A 9–10, B 10–11, and A 11–13.

### Real CFS is bigger than this

Real CFS keeps runnable tasks in a red-black tree ordered by `vruntime`, so the leftmost node is the next pick. It sizes each slice from a *target latency*, a window in which every runnable task should get a turn, divided in proportion to weights and bounded below by a minimum granularity. The exercise uses a fixed `slice_len`. The kernel also groups tasks with cgroups, balances load across cores, and treats real-time tasks separately.

Linux 6.6, released in 2023, replaced CFS's pick rule with EEVDF, which keeps weights and virtual time but adds a per-task deadline. A kernel from 6.6 on therefore picks tasks by a different rule than the one you build here. The weights, `nice` values, and virtual time carry over.

## Try it on your own machine

These commands are for Linux.

1. Run two CPU hogs on the same core, one at nice 0 and one at nice 5, and compare their CPU use. The ratio should land near 75 to 25.

   ```bash
   taskset -c 0 yes > /dev/null &
   taskset -c 0 nice -n 5 yes > /dev/null &
   sleep 10
   ps -o pid,ni,%cpu,comm -C yes
   kill %1 %2
   ```

   The `%cpu` column is an average over each process's lifetime. Pinning both to core 0 forces them to share it.

2. Read the scheduler's own record of a process. Here the process is `head` itself. Look for `se.vruntime` in the output. The fields vary by kernel version.

   ```bash
   head -20 /proc/self/sched
   ```

3. Check which kernel you run. The scheduler's rule changed at 6.6.

   ```bash
   uname -r
   ```

4. Change a running process's nice value from Python. `os.nice` adds to the current value and returns the result.

   ```python
   import os
   print(os.nice(0), os.nice(5), os.getpriority(os.PRIO_PROCESS, 0))
   ```

   A normal user can raise nice but cannot lower it again.

> [!RECAP]
> - Lottery draws a random ticket per slice. Shares are right on average and noisy in the short run.
> - Stride gives each job a stride and a pass value, runs the smallest pass, and hits the ratio exactly.
> - CFS runs the task with the smallest `vruntime`, which grows by `runtime * 1024 / weight`.
> - Nice 0 has weight 1024, and each nice step changes the weight by about 1.25 times.
> - A late arrival starts at `min_vruntime`, so it cannot monopolise the CPU.

## Build it step by step

`Job`, `merge_slices`, `gantt`, `STRIDE1`, and `NICE_TO_WEIGHT` are given. You write five functions in the order the checks test them.

1. **`weight_for_nice(nice)`** returns the table entry at index `nice + 20`. Raise `ValueError` outside −20 to 19. The usual mistake is an off-by-twenty index.
2. **`vruntime_delta(runtime, weight)`** returns `runtime * 1024 / weight` as a float.
3. **`lottery(tickets, slices, rng)`** returns a list with one winner name per slice. Call `rng.randrange(total)` exactly once per slice. A check counts the calls. Walk `sorted(tickets)` so that the ranges do not depend on dictionary order.
4. **`stride_schedule(tickets, slices)`** returns a list of picks. Compute each stride as `STRIDE1 // tickets[name]`. Raise `ValueError` for a job with fewer than 1 ticket. The usual mistake is to update the pass before recording the pick, or to break ties without the name.
5. **`cfs(jobs, nice, slice_len=1)`** returns a timeline. Keep `remaining`, `vruntime`, and `min_vruntime`. At each decision, collect the arrived, unfinished jobs, raise `min_vruntime` to the smallest `vruntime` among those already seen, give each unseen job `min_vruntime`, pick with `min` on `(vruntime, name)`, run for `min(slice_len, remaining)`, and add `vruntime_delta`. If nobody has arrived, jump the clock. Finish with `merge_slices`. The usual mistake is to start a late arrival at 0.

## Where this breaks

- **Chance is rough.** Lottery shares wander in the short run. A job can wait many slices in a row, and no scheduler built on it can promise latency.
- **Integer strides drift.** With 300 tickets, `10_000 // 300` is 33, not 33.33, so that job gets about 1 percent more than its share. Real implementations use larger constants and fixed-point arithmetic.
- **Weights set shares, not delays.** A task with a huge weight still waits for its turn behind others unless the slice is short. Real kernels add latency targets, and EEVDF's deadlines address this directly.
- **Sleepers.** A task that sleeps for an hour has a very low `vruntime`. Without the floor, it would run alone when it wakes. With the floor, it gets only a mild head start.
- **Many cores.** Each core keeps its own tree. Moving tasks between cores to balance the load is a hard problem, and a single `vruntime` order does not exist across the machine.
- **Fairness is a policy choice.** Equal shares per process lets a user who runs 100 processes beat one who runs 1. Linux can group tasks with cgroups, so that fairness applies between groups first.

## Further reading

- [OSTEP, chapter 9: Proportional share](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched-lottery.pdf) covers lottery, stride, and CFS, with the weight table and the red-black tree.
- [The CFS scheduler design document](https://docs.kernel.org/scheduler/sched-design-CFS.html) is the Linux kernel's own explanation of virtual runtime and the ideal fair CPU.
- [The EEVDF scheduler document](https://docs.kernel.org/scheduler/sched-eevdf.html) describes the rule that replaced CFS's pick in Linux 6.6.
- [sched(7)](https://man7.org/linux/man-pages/man7/sched.7.html) lists Linux's policies and how `nice` interacts with them.
- [nice(1)](https://man7.org/linux/man-pages/man1/nice.1.html) documents the command used above.

## The exercise

You write `weight_for_nice`, `vruntime_delta`, `lottery`, `stride_schedule`, and `cfs`.

The checks use hand-computed answers. The lottery check passes a stub generator with scripted draws, so each winner is known in advance, and a second check uses `random.Random(0)` and compares the share of A with 75 percent. The stride checks expect the exact sequence `ABCCCACCAB` and the exact counts over 80 slices. The CFS checks cover equal weights, the nice 0 against nice 5 timeline above, the long-run share, and the late arrival that starts at `min_vruntime`.
