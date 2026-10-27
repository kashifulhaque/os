---
title: "Scheduling basics: FCFS, SJF, and SRTF"
slug: 10-scheduling-basics
part: "Part 3 — CPU scheduling"
summary: Simulate three classic CPU scheduling policies and score them with turnaround, waiting, and response time.
minutes: 50
gpu: false
objectives:
  - Draw a Gantt chart for FCFS, SJF, and SRTF on a list of jobs.
  - Compute turnaround time, waiting time, and response time for each job.
  - "Explain the convoy effect, and say why SRTF needs to know the future."
prereqs:
  - 04-what-an-operating-system-does
  - 06-processes
exercise: 10-scheduling-basics
---

# Scheduling basics: FCFS, SJF, and SRTF

A CPU core runs one thing at a time. Your laptop has dozens of processes that want to run. A browser, a music player, a compiler, and the operating system itself all line up for the same few cores. Someone has to decide who goes next.

That someone is the *scheduler*, a part of the kernel. Its job is to pick which ready process gets the CPU, and for how long. The rule it follows is called a *scheduling policy*. A good policy makes the machine feel fast, treats processes fairly, and keeps the CPU busy.

Think of a restaurant kitchen with one chef. Orders arrive on paper tickets. The chef can cook them in the order they came in, cook the quickest dish first, or put a long stew aside whenever a salad order arrives. Each choice makes some customers happy and others wait. In this lesson, you build simulators for three such choices and measure who waits.

## What you already know

- A process is a running program, and the kernel keeps a record for each one (lesson 06).
- A process is ready when it could run but is waiting for a CPU, running when it holds one, and blocked when it waits for something else (lesson 06).
- A timer interrupt lets the kernel take the CPU back from a running program (lesson 04).
- A dataclass groups named fields, and `min` accepts a `key` function that returns a tuple (lesson 01).
- A list of tuples can describe what happened over time.

## Model the problem: jobs, timelines, and three numbers

Real schedulers face messy input. To study policies, we shrink the problem to something you can compute by hand.

A *job* is a piece of CPU work. It has a `name`, an `arrival` time (when it becomes ready), and a `burst` (how many ticks of CPU it needs in total). A *tick* is one unit of time. Each job is a `Job` dataclass, which the exercise gives you.

```python
@dataclass(frozen=True)
class Job:
    name: str
    arrival: int
    burst: int
    io_every: int = 0   # used from lesson 11 on
    io_wait: int = 0
```

The simplifying assumptions are strong. Every job only computes. It never waits for a disk or a keyboard. The scheduler knows each burst in advance. Real systems do not know this, and we return to that problem at the end.

A scheduler's output is a *timeline*: a list of `(name, start, end)` tuples. The tuple `("B", 8, 12)` means job `B` held the CPU from tick 8 up to, but not including, tick 12. A gap between two tuples means the CPU was idle.

Here are four jobs that we reuse throughout the lesson.

| Job | Arrival | Burst |
|---|---|---|
| A | 0 | 8 |
| B | 1 | 4 |
| C | 2 | 9 |
| D | 3 | 5 |

A *Gantt chart* draws a timeline as a row of cells, one per tick. The next diagram shows what the chart for these jobs looks like when they run in arrival order. The top two lines are a ruler.

```text
tick  0         1         2
      0123456789012345678901234567
FCFS  AAAAAAAABBBBCCCCCCCCCDDDDD
```

How do you score a timeline? Three numbers matter. Each is measured per job, then averaged.

- *Turnaround time* is the completion time minus the arrival time. It is how long the job spent in the system from the moment it showed up.
- *Waiting time* is the turnaround time minus the burst. It is the time the job spent ready but not running.
- *Response time* is the first start minus the arrival time. It is how long you wait before anything happens.

Turnaround matters for batch work like compiling. Response time matters for anything a person is watching, like typing into a terminal. The two can pull a policy in opposite directions.

> [!KEY]
> A scheduling policy is judged by numbers on a timeline. Turnaround measures how long a job takes from arrival to the end, and response measures how long it waits for its first turn.

## First come, first served

The simplest policy is *first come, first served* (FCFS), also called FIFO. Run jobs in the order they arrive. Run each one until it finishes. No job is ever interrupted, which is called *non-preemptive* scheduling.

Work through the four jobs. A arrives first and runs from 0 to 8. B runs from 8 to 12, C from 12 to 21, and D from 21 to 26. That gives the chart you saw above.

Next, score it. The table shows the arithmetic for each job.

| Job | Completion | Turnaround | Waiting | Response |
|---|---|---|---|---|
| A | 8 | 8 − 0 = 8 | 8 − 8 = 0 | 0 − 0 = 0 |
| B | 12 | 12 − 1 = 11 | 11 − 4 = 7 | 8 − 1 = 7 |
| C | 21 | 21 − 2 = 19 | 19 − 9 = 10 | 12 − 2 = 10 |
| D | 26 | 26 − 3 = 23 | 23 − 5 = 18 | 21 − 3 = 18 |

The averages are 61 / 4 = 15.25 for turnaround, and 35 / 4 = 8.75 for both waiting and response. FCFS has no preemption, so every job's response time equals its waiting time.

FCFS is fair in one sense, and easy to build. Its weakness is the *convoy effect*. When one long job is at the front, every short job stuck behind it waits for the whole thing, like a person buying one apple behind a full shopping cart.

Take three jobs that all arrive at tick 0. A needs 100 ticks, and B and C need 10 each. In FCFS order, A finishes at 100, B at 110, and C at 120. The average turnaround is (100 + 110 + 120) / 3 = 110. Move the long job to the end and the average drops sharply. That is the idea behind the next policy.

## Shortest job first

*Shortest job first* (SJF) picks, whenever the CPU is free, the arrived job with the smallest burst. It is still non-preemptive: once a job starts, it runs to completion.

Trace the four jobs. At tick 0 only A has arrived, so A runs 0 to 8. The scheduler does not wait for the shorter B, because it cannot see the future. At tick 8, the ready jobs are B (burst 4), C (9), and D (5). B is shortest, so B runs 8 to 12. Then D (5) beats C (9), so D runs 12 to 17. C runs last, from 17 to 26.

```text
tick  0         1         2
      0123456789012345678901234567
SJF   AAAAAAAABBBBDDDDDCCCCCCCCC
```

The turnarounds are A = 8, B = 11, D = 17 − 3 = 14, and C = 26 − 2 = 24. The average is 57 / 4 = 14.25, down from FCFS's 15.25.

Rerun the convoy. With B and C first, they finish at 10 and 20, and A finishes at 120. The average is (10 + 20 + 120) / 3 = 50, against 110 for FCFS. When all jobs arrive together, SJF gives the lowest possible average turnaround of any ordering. Moving a short job ahead of a long one always helps the short job more than it hurts the long one.

SJF has two catches. First, it needs burst times, which the kernel does not know. Second, when jobs arrive at different times, a short job can arrive right after a long one has started, and it must wait. Look at B in the chart above. B needs only 4 ticks, but it waits 7 ticks for A to finish.

## Shortest remaining time first

The fix is to allow preemption. *Shortest remaining time first* (SRTF) is the preemptive version of SJF. At every tick, run the arrived job that has the least work left. When a job arrives with less remaining time than the running job, it takes the CPU at once. The running job goes back to the ready queue with its remaining time saved.

Trace it. The checkpoints are the arrivals at ticks 1, 2, and 3.

- At tick 0, A runs. It has 8 left.
- At tick 1, B arrives with 4. A has 7 left, so B preempts A.
- At tick 2, C arrives with 9. B has 3 left, so B keeps going.
- At tick 3, D arrives with 5. B has 2 left, so B keeps going.
- B finishes at tick 5. The ready jobs hold A (7 left), C (9), and D (5). D runs 5 to 10.
- At tick 10, A (7) beats C (9). A runs 10 to 17. C runs 17 to 26.

```text
tick  0         1         2
      0123456789012345678901234567
SRTF  ABBBBDDDDDAAAAAAACCCCCCCCC
```

The scores are in the next table.

| Job | Completion | Turnaround | Waiting | Response |
|---|---|---|---|---|
| A | 17 | 17 | 9 | 0 |
| B | 5 | 4 | 0 | 0 |
| C | 26 | 24 | 15 | 15 |
| D | 10 | 7 | 2 | 2 |

Averages: turnaround 52 / 4 = 13.00, waiting 26 / 4 = 6.50, response 17 / 4 = 4.25.

The comparison across all three policies is below.

| Policy | Avg turnaround | Avg waiting | Avg response |
|---|---|---|---|
| FCFS | 15.25 | 8.75 | 8.75 |
| SJF | 14.25 | 7.75 | 7.75 |
| SRTF | 13.00 | 6.50 | 4.25 |

SRTF wins every column. It is provably optimal for average turnaround when burst times are known. It also has a cost. C waited 15 ticks before it first ran, and a steady stream of short jobs could keep a long job waiting forever. That is called *starvation*.

> [!KEY]
> SJF and SRTF lower average turnaround by running short jobs first, but they need to know burst times in advance and can starve long jobs.

## Break ties the same way every time

Two jobs often tie. Maybe both arrive at tick 0, or both have 3 ticks left. A simulator that breaks ties differently from yours produces a different timeline, and neither is wrong. So the exercise fixes one rule and uses it everywhere: the earlier arrival wins, and if the arrivals tie too, the name that sorts first wins.

In code, that rule is a tuple key. For SJF, the key is `(job.burst, job.arrival, job.name)`. For SRTF, it is `(remaining, job.arrival, job.name)`. Python compares tuples left to right, so `min` does the work.

One consequence is worth seeing. Suppose A has run for one tick of a 3-tick burst, and B arrives at tick 1 with a 2-tick burst. A has 2 left and B has 2 left. The tie goes to A, because A arrived first. A is not interrupted for an equal job.

> [!WARNING]
> Equal keys are not rare. Test with ties on arrival, on burst, and on remaining time, or your simulator will look right until the inputs get a little unlucky.

## Where the burst times come from

Every policy so far assumed that the scheduler knows how long a job runs. Linux does not. A kernel cannot read a program's mind. The usual workaround is to guess from the past. A scheduler can keep a running average of a process's recent CPU bursts and treat that as the next burst. Short recent bursts predict a short next one.

The next lessons take two other routes. Lesson 11 uses a time slice to give everyone a turn without any prediction. Lesson 12 shares the CPU in proportion to weights. Linux's real scheduler follows the second route.

## Try it on your own machine

These commands work on Linux. On macOS, `ps` and `nice` work, but `chrt` and `/proc` do not exist.

1. List the scheduling class, priority, and nice value of running processes. The `CLS` column shows `TS` for the normal time-sharing class.

   ```bash
   ps -eo pid,cls,pri,ni,comm | head -15
   ```

2. Ask which policy your shell uses, and which priorities each policy accepts. A normal process reports `SCHED_OTHER`.

   ```bash
   chrt -p $$
   chrt -m
   ```

3. Count how often the kernel switched your shell on and off the CPU. A voluntary switch happens when the process blocks. A nonvoluntary switch happens when the kernel preempts it.

   ```bash
   grep ctxt /proc/$$/status
   ```

4. Start a background job at lower priority and compare its nice value. A higher nice value means the process is nicer to others, so it gets less CPU.

   ```bash
   nice -n 10 sleep 30 &
   ps -o pid,ni,comm -p $!
   ```

5. Read the same information from Python. The values are numbers, and `os.SCHED_OTHER` names the default.

   ```python
   import os
   print(os.sched_getscheduler(0) == os.SCHED_OTHER)
   ```

Linux also offers `SCHED_FIFO` and `SCHED_RR`, policies for real-time work, where a high-priority task runs until it blocks or yields. Setting them needs root, so try them only on a machine you own.

> [!RECAP]
> - A job has an arrival time and a burst. A timeline lists `(name, start, end)` segments.
> - Turnaround is completion minus arrival. Waiting is turnaround minus burst. Response is first start minus arrival.
> - FCFS runs in arrival order and suffers from the convoy effect.
> - SJF picks the shortest arrived job. SRTF also preempts when a shorter job arrives.
> - Ties break by arrival, then by name, so every answer is unambiguous.

## Build it step by step

Open the starter. `Job`, `merge_slices`, and `gantt` are given. You write five functions.

1. **`fcfs(jobs)`** takes a list of `Job` and returns a timeline. Sort by `(arrival, name)`. Keep a clock. Before each job, set `clock = max(clock, job.arrival)` so that an idle CPU waits. The usual mistake is to start a job before it arrives.

2. **`sjf(jobs)`** returns a timeline. Loop while jobs remain. Build the list of arrived jobs, pick one with `min` and the tie-break key, and run it to completion. When no job has arrived, jump the clock to the earliest arrival. The usual mistake is to pick the shortest job overall, including jobs that have not arrived.

3. **`srtf(jobs)`** returns a timeline. Keep a `remaining` dictionary. At each tick, pick from the arrived, unfinished jobs, run it for one tick, and record `(name, clock, clock + 1)`. At the end, call `merge_slices` so that touching one-tick segments become one. The usual mistake is to forget the merge, or to loop forever when everything unfinished lies in the future.

4. **`metrics(jobs, timeline)`** returns `{name: {"turnaround": ..., "waiting": ..., "response": ...}}`. A job can appear in several segments. Its completion is the largest end, and its first start is the smallest start. The usual mistake is to use the first segment's end as the completion.

5. **`average_metrics(per_job)`** returns the three averages as floats. Divide by the number of jobs.

The `__main__` block prints all three policies on the jobs from this lesson. When the functions work, the numbers match the tables above.

## Where this breaks

- **Burst times are unknown.** Real kernels estimate them or avoid needing them. Lesson 12 shows how.
- **Jobs do not only compute.** A real process alternates between CPU work and waiting for I/O. Each CPU burst is a short job, and the scheduler sees another one every time the process wakes up. Lesson 11 builds a scheduler for this.
- **Starvation.** SJF and SRTF can leave a long job waiting without end. A real system needs some form of aging.
- **Switching has a price.** The simulators move between jobs for free. On real hardware, each switch costs microseconds of kernel work and lost cache contents. SRTF's frequent preemption would pay that bill many times.
- **Response time can stay poor.** In the SRTF chart, C waits 15 ticks for its first turn. A time slice (lesson 11) bounds how long any job waits for its first turn.

## Further reading

- [OSTEP, chapter 7: CPU scheduling](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf) covers FCFS, SJF, STCF, and the metrics, with the same convoy example.
- [OSTEP, chapter 6: Limited direct execution](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf) explains the timer interrupt and the context switch that make preemption possible.
- [sched(7)](https://man7.org/linux/man-pages/man7/sched.7.html) describes Linux's scheduling policies and how they interact.
- [chrt(1)](https://man7.org/linux/man-pages/man1/chrt.1.html) shows how to read and set a process's policy and priority.
- [nice(1)](https://man7.org/linux/man-pages/man1/nice.1.html) documents the `nice` command used above.

## The exercise

You build a small scheduling laboratory. `fcfs`, `sjf`, and `srtf` each take a list of `Job` and return a timeline of `(name, start, end)` tuples. `metrics` reads a timeline and returns turnaround, waiting, and response time for each job. `average_metrics` averages them.

The checks verify each policy against hand-computed timelines. They cover idle gaps, ties on arrival, burst, and remaining time, and a check that the input list stays unchanged. Another check runs the convoy example through the whole pipeline and expects an average turnaround of 110 for FCFS and 50 for SJF and SRTF.
