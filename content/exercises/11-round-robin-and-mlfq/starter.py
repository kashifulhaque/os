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
    raise NotImplementedError


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
    raise NotImplementedError


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
