"""Lesson 12: proportional-share scheduling.

Same job and timeline vocabulary as lessons 10 and 11. A *timeline* is a list
of `(name, start, end)` tuples: job `name` held the CPU from tick `start` up
to (not including) tick `end`.

Tie-breaking rule: when two jobs tie on the key a scheduler minimises, the one
whose `name` sorts first wins.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

Timeline = list  # list of (name, start, end) tuples

STRIDE1 = 10_000  # the numerator for stride = STRIDE1 // tickets

# Linux's sched_prio_to_weight table. Index 0 is nice -20, index 20 is nice 0
# (weight 1024), index 39 is nice 19. Each step is about 1.25 times the next.
NICE_TO_WEIGHT = [
    88761, 71755, 56483, 46273, 36291,
    29154, 23254, 18705, 14949, 11916,
    9548, 7620, 6100, 4904, 3906,
    3121, 2501, 1991, 1586, 1277,
    1024, 820, 655, 526, 423,
    335, 272, 215, 172, 137,
    110, 87, 70, 56, 45,
    36, 29, 23, 18, 15,
]


@dataclass(frozen=True)
class Job:
    """One job. Names are unique. `burst` is at least 1.

    `io_every` and `io_wait` are used by lesson 11. This lesson ignores them.
    """

    name: str
    arrival: int
    burst: int
    io_every: int = 0
    io_wait: int = 0


def merge_slices(slices: list) -> Timeline:
    """Join touching segments of the same job into one (provided).

    merge_slices([("A", 0, 1), ("A", 1, 2), ("B", 2, 3)]) == [("A", 0, 2), ("B", 2, 3)]
    """
    merged: list = []
    for name, start, end in slices:
        if merged and merged[-1][0] == name and merged[-1][2] == start:
            merged[-1] = (name, merged[-1][1], end)
        else:
            merged.append((name, start, end))
    return merged


def gantt(timeline: Timeline) -> str:
    """One character per tick: the first letter of the job, or '.' when idle (provided).

    gantt([("A", 0, 2), ("B", 3, 4)]) == "AA.B"
    """
    if not timeline:
        return ""
    cells = ["."] * max(end for _, _, end in timeline)
    for name, start, end in timeline:
        for t in range(start, end):
            cells[t] = name[0]
    return "".join(cells)


def lottery(tickets: dict, slices: int, rng: random.Random) -> list:
    """Lottery scheduling: hold one drawing per time slice.

    `tickets` maps job name to a positive ticket count. For each of `slices`
    slices, draw `winning = rng.randrange(total)` (exactly one call, where
    `total` is the sum of all tickets). Walk the jobs in sorted name order,
    keeping a running sum of tickets. The winner is the first job whose
    running sum is greater than `winning`. Return the list of winners.

    With tickets {"A": 75, "B": 25} the draws 0..74 pick A and 75..99 pick B.
    """
    names = sorted(tickets)
    total = sum(tickets.values())
    winners = []
    for _ in range(slices):
        winning = rng.randrange(total)
        running = 0
        for name in names:
            running += tickets[name]
            if running > winning:  # the winning ticket lies in this job's range
                winners.append(name)
                break
    return winners


def weight_for_nice(nice: int) -> int:
    """Look up the CFS weight for a nice value from -20 to 19.

    weight_for_nice(0) == 1024. Outside -20..19, raise ValueError.
    """
    if not -20 <= nice <= 19:
        raise ValueError(f"nice must be in -20..19, got {nice}")
    return NICE_TO_WEIGHT[nice + 20]


def vruntime_delta(runtime: float, weight: int) -> float:
    """How much virtual runtime `runtime` ticks of real CPU adds for a task of this weight.

    vruntime_delta(10, 1024) == 10.0. vruntime_delta(3, 2048) == 1.5.
    """
    return runtime * 1024 / weight  # weight 1024 (nice 0) is the yardstick


def stride_schedule(tickets: dict, slices: int) -> list:
    """Stride scheduling: deterministic proportional share.

    Each job has stride = STRIDE1 // tickets and a pass value that starts at 0.
    For each slice: pick the job with the smallest (pass, name), record its
    name, and add its stride to its pass. Return the list of picks.
    Any ticket count below 1 raises ValueError.

    stride_schedule({"A": 1, "B": 1}, 4) == ["A", "B", "A", "B"]
    """
    if any(count < 1 for count in tickets.values()):
        raise ValueError("every job needs at least one ticket")
    stride = {name: STRIDE1 // count for name, count in tickets.items()}
    passes = {name: 0 for name in tickets}
    picks = []
    for _ in range(slices):
        name = min(passes, key=lambda n: (passes[n], n))
        picks.append(name)
        passes[name] += stride[name]  # more tickets, smaller stride, picked more often
    return picks


def cfs(jobs: list, nice: dict, slice_len: int = 1) -> Timeline:
    """A tiny Completely Fair Scheduler.

    Every job is CPU-bound: it runs until `burst` ticks are used up.
    `nice` maps name to nice value (a job missing from it has nice 0).

    State: each job has a `vruntime` (float). `min_vruntime` starts at 0.
    Time advances in decisions. At each decision at clock `t`:
      1. If any job has arrived (arrival <= t) and is unfinished, raise
         `min_vruntime` to max(min_vruntime, smallest vruntime among those
         runnable jobs that already have one). It never decreases.
      2. A job that arrives for the first time at this decision (arrival <= t,
         not yet seen) gets vruntime = min_vruntime.
      3. Pick the runnable job with the smallest (vruntime, name). Run it for
         min(slice_len, remaining) ticks, and add
         vruntime_delta(ran, weight_for_nice(nice)) to its vruntime.
      4. If nobody is runnable, the clock jumps to the next arrival.
    Return the merged timeline.

    cfs([Job("A", 0, 2), Job("B", 0, 2)], {}) == [("A", 0, 1), ("B", 1, 2), ("A", 2, 3), ("B", 3, 4)]
    """
    remaining = {j.name: j.burst for j in jobs}
    arrival = {j.name: j.arrival for j in jobs}
    vruntime: dict = {}  # filled in when a job is first seen
    min_vruntime = 0.0
    clock = 0
    slices: list = []
    while any(left > 0 for left in remaining.values()):
        runnable = [n for n in remaining if arrival[n] <= clock and remaining[n] > 0]
        if not runnable:
            clock = min(arrival[n] for n in remaining if remaining[n] > 0)
            continue
        seen = [vruntime[n] for n in runnable if n in vruntime]
        if seen:
            min_vruntime = max(min_vruntime, min(seen))
        for n in runnable:
            vruntime.setdefault(n, min_vruntime)  # late arrivals start at the floor
        name = min(runnable, key=lambda n: (vruntime[n], n))
        ran = min(slice_len, remaining[name])
        slices.append((name, clock, clock + ran))
        clock += ran
        remaining[name] -= ran
        vruntime[name] += vruntime_delta(ran, weight_for_nice(nice.get(name, 0)))
    return merge_slices(slices)


if __name__ == "__main__":
    tickets = {"A": 100, "B": 50, "C": 250}
    picks = lottery(tickets, 12, random.Random(7))
    print("lottery (seed 7):", "".join(picks))
    print("stride          :", "".join(stride_schedule(tickets, 12)))

    jobs = [Job("A", 0, 40), Job("B", 0, 40)]
    line = cfs(jobs, {"A": 0, "B": 5})
    print("cfs nice 0 vs nice 5:")
    print("  ", gantt(line))
    for name in ("A", "B"):
        total = sum(e - s for n, s, e in line if n == name)
        print(f"   {name} weight {weight_for_nice({'A': 0, 'B': 5}[name])}: ran {total} ticks")
