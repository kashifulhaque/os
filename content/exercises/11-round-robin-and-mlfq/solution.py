"""Lesson 11: round robin and the multi-level feedback queue.

Same vocabulary as lesson 10. A *job* needs `burst` ticks of CPU and arrives
at `arrival`. A *timeline* is a list of `(name, start, end)` tuples: job
`name` held the CPU from tick `start` up to (not including) tick `end`.
Gaps between segments are idle time or context-switch time.

Tie-breaking rule: when several jobs become ready at the same tick, they join
the queue in `name` order.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

Timeline = list  # list of (name, start, end) tuples


@dataclass(frozen=True)
class Job:
    """One job. Names are unique. `burst` is at least 1.

    If `io_every` is positive, the job asks for I/O after every `io_every`
    ticks of CPU it has used since its previous I/O (or since it started). It
    then leaves the CPU for `io_wait` ticks. A job that finishes at that very
    tick does not do I/O. Round robin ignores these two fields.
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


def round_robin(jobs: list, quantum: int, switch_cost: int = 0) -> Timeline:
    """Round robin with a fixed time quantum.

    * The ready queue is first in, first out. Jobs that arrive at the same
      tick join in name order.
    * The job at the head runs for min(quantum, remaining) ticks.
    * Before a job whose slice just ended is put at the back, every job with
      arrival <= the slice's end tick joins the queue first.
    * A context switch costs `switch_cost` ticks of nothing, charged when the
      next job to run differs from the job that ran just before it, and the
      CPU was not idle in between. The first job ever, a job that runs again
      with nobody else ready, and a job that starts after an idle gap pay
      nothing. Jobs that arrive during a switch join the queue at the end of
      the next slice, by the rule above.
    * quantum < 1 raises ValueError.
    * Return a merged timeline: touching segments of one job are one segment.

    round_robin([Job("A", 0, 3), Job("B", 0, 3)], quantum=2)
      == [("A", 0, 2), ("B", 2, 4), ("A", 4, 5), ("B", 5, 6)]
    """
    if quantum < 1:
        raise ValueError("quantum must be at least 1")
    arrivals = sorted(jobs, key=lambda j: (j.arrival, j.name))
    remaining = {j.name: j.burst for j in jobs}
    queue: deque = deque()
    next_arrival = 0
    clock = 0
    last_name = None  # who held the CPU last
    last_end = None   # and when they let go
    slices: list = []

    def admit(until: int) -> None:
        nonlocal next_arrival
        while next_arrival < len(arrivals) and arrivals[next_arrival].arrival <= until:
            queue.append(arrivals[next_arrival])
            next_arrival += 1

    while True:
        admit(clock)
        if not queue:
            if next_arrival == len(arrivals):
                break
            clock = arrivals[next_arrival].arrival  # idle until the next arrival
            continue
        job = queue.popleft()
        if last_name is not None and last_name != job.name and last_end == clock:
            clock += switch_cost  # back-to-back switch to a different job
        run = min(quantum, remaining[job.name])
        slices.append((job.name, clock, clock + run))
        clock += run
        remaining[job.name] -= run
        last_name, last_end = job.name, clock
        admit(clock)  # arrivals queue ahead of the job we are about to re-queue
        if remaining[job.name] > 0:
            queue.append(job)
    return merge_slices(slices)


def mlfq(jobs: list, levels: list, boost_every: int = 0) -> Timeline:
    """A multi-level feedback queue, simulated one tick at a time.

    `levels` is a list of `(quantum, allotment)` pairs, highest priority
    first. Each level has its own FIFO queue.

    Every tick, in this order:
      1. Boost. If boost_every > 0 and the clock is a positive multiple of it,
         the running job (if any) goes to the FRONT of its queue, then every
         job in every queue moves to level 0 (levels 0, 1, 2, ... in queue
         order), and every job's allotment use resets to 0. Blocked jobs also
         return to level 0 with allotment use 0.
      2. Admit. Jobs whose arrival <= clock, and blocked jobs whose I/O is
         done, join the BACK of the queue for their level, in name order.
      3. Preempt. If the running job's queue level is lower in priority than a
         non-empty queue, the running job goes to the FRONT of its own queue.
      4. Pick. If nothing runs, take the head of the highest non-empty queue,
         with a fresh quantum. If every queue is empty, the CPU idles this tick.
      5. Run one tick. Then, in this order:
         a. remaining burst reaches 0: the job is finished.
         b. allotment use reaches the level's allotment, and the level is not
            the last: demote one level, allotment use resets to 0.
         c. since_io reaches io_every: the job blocks for io_wait ticks and
            keeps its (possibly just-demoted) level. It re-enters at step 2
            when clock >= (tick end) + io_wait.
         d. otherwise, if this level's quantum is used up, or the job was
            demoted in (b): it goes to the BACK of its (new) queue.
    The last level's allotment is ignored. A job that is demoted or whose
    quantum expires has nothing left running, so the next tick picks again.

    Return a merged timeline. Idle ticks are gaps.

    mlfq([Job("A", 0, 3)], levels=[(1, 1), (2, 2)]) == [("A", 0, 3)]
    """
    last_level = len(levels) - 1
    queues = [deque() for _ in levels]
    # Per-job bookkeeping: level, ticks used at this level, ticks left, CPU
    # since the last I/O request.
    state = {
        j.name: {"job": j, "level": 0, "used": 0, "left": j.burst, "since_io": 0}
        for j in jobs
    }
    not_arrived = sorted(state, key=lambda n: (state[n]["job"].arrival, n))
    blocked: list = []  # (wake_time, name)
    current = None
    slice_used = 0
    clock = 0
    unfinished = len(jobs)
    ticks: list = []

    while unfinished > 0:
        # 1. Priority boost.
        if boost_every and clock > 0 and clock % boost_every == 0:
            if current is not None:
                queues[state[current]["level"]].appendleft(current)
                current = None
            everyone: list = []
            for q in queues:
                everyone.extend(q)
                q.clear()
            for name in everyone:
                state[name]["level"] = 0
                state[name]["used"] = 0
            queues[0].extend(everyone)
            for _, name in blocked:
                state[name]["level"] = 0
                state[name]["used"] = 0

        # 2. Admit arrivals and jobs whose I/O finished, in name order.
        arriving = [n for n in not_arrived if state[n]["job"].arrival <= clock]
        waking = [n for t, n in blocked if t <= clock]
        for name in sorted(arriving + waking):
            queues[state[name]["level"]].append(name)
        not_arrived = [n for n in not_arrived if n not in arriving]
        blocked = [(t, n) for t, n in blocked if n not in waking]

        # 3. A higher-priority arrival preempts the running job.
        if current is not None:
            level = state[current]["level"]
            if any(queues[higher] for higher in range(level)):
                queues[level].appendleft(current)
                current = None

        # 4. Pick the head of the highest non-empty queue.
        if current is None:
            for q in queues:
                if q:
                    current = q.popleft()
                    slice_used = 0
                    break
        if current is None:
            clock += 1  # idle tick
            continue

        # 5. Run one tick, then decide where the job goes.
        st = state[current]
        ticks.append((current, clock, clock + 1))
        clock += 1
        st["left"] -= 1
        st["used"] += 1
        st["since_io"] += 1
        slice_used += 1
        name = current

        if st["left"] == 0:
            unfinished -= 1
            current = None
            continue
        quantum, allotment = levels[st["level"]]
        demoted = False
        if st["used"] >= allotment and st["level"] < last_level:
            st["level"] += 1
            st["used"] = 0
            demoted = True
        job = st["job"]
        if job.io_every and st["since_io"] == job.io_every:
            st["since_io"] = 0
            blocked.append((clock + job.io_wait, name))
            current = None
        elif demoted or slice_used >= quantum:
            queues[st["level"]].append(name)
            current = None
    return merge_slices(ticks)


if __name__ == "__main__":
    jobs = [Job("A", 0, 5), Job("B", 0, 3), Job("C", 0, 2)]
    line = round_robin(jobs, quantum=2)
    print("round robin, quantum 2")
    print("  ", gantt(line))
    print("  ", line)
    slow = round_robin(jobs, quantum=2, switch_cost=1)
    print("with a one-tick context switch")
    print("  ", gantt(slow))

    mixed = [Job("hog", 0, 6), Job("io", 0, 3, io_every=1, io_wait=1)]
    line = mlfq(mixed, levels=[(2, 4), (4, 8)])
    print("mlfq: a CPU hog and an I/O-bound job")
    print("  ", gantt(line))
    print("  ", line)
