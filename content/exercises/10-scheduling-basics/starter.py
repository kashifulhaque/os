"""Lesson 10: scheduling basics.

A *job* is a piece of CPU work: it arrives at some time and needs `burst`
ticks of CPU. A *timeline* is a list of `(name, start, end)` tuples in time
order, meaning "job `name` held the CPU from tick `start` up to (not
including) tick `end`". Idle time is not recorded: a gap between two
segments means the CPU had nothing to run.

Tie-breaking rule used by every function in this file, so that answers are
unambiguous: when two jobs compete on the same key, the one with the earlier
`arrival` wins, and if that also ties, the one whose `name` sorts first.
"""

from __future__ import annotations

from dataclasses import dataclass

Timeline = list  # list of (name, start, end) tuples


@dataclass(frozen=True)
class Job:
    """One job. Names are unique. `burst` is at least 1.

    `io_every` and `io_wait` describe I/O behaviour. Lessons 11 and 12 use
    them. Everything in this lesson ignores them.
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


def fcfs(jobs: list) -> Timeline:
    """First come, first served: run each job to completion in arrival order.

    Ties on arrival go to the smaller name. If the CPU is idle when the next
    job has not arrived, the clock jumps to its arrival.

    fcfs([Job("A", 0, 3), Job("B", 1, 2)]) == [("A", 0, 3), ("B", 3, 5)]
    """
    raise NotImplementedError


def sjf(jobs: list) -> Timeline:
    """Shortest job first, non-preemptive.

    Whenever the CPU is free, choose among the jobs that have already arrived
    the one with the smallest `burst` (ties: earlier arrival, then name) and
    run it to completion. A job that arrives later never interrupts.

    sjf([Job("A", 0, 8), Job("B", 1, 2)]) == [("A", 0, 8), ("B", 8, 10)]
    """
    raise NotImplementedError


def srtf(jobs: list) -> Timeline:
    """Shortest remaining time first: the preemptive version of SJF.

    At every tick, run the arrived, unfinished job with the smallest remaining
    time (ties: earlier arrival, then name). Return the merged timeline.

    srtf([Job("A", 0, 8), Job("B", 1, 2)]) == [("A", 0, 1), ("B", 1, 3), ("A", 3, 10)]
    """
    raise NotImplementedError


def metrics(jobs: list, timeline: Timeline) -> dict:
    """Per-job turnaround, waiting, and response time, read off a timeline.

    turnaround = completion - arrival
    waiting    = turnaround - burst
    response   = first start - arrival

    Returns {name: {"turnaround": int, "waiting": int, "response": int}}.

    metrics([Job("B", 1, 2)], [("B", 4, 6)])
      == {"B": {"turnaround": 5, "waiting": 3, "response": 3}}
    """
    raise NotImplementedError


def average_metrics(per_job: dict) -> dict:
    """Average each of the three measures over all jobs, as floats.

    average_metrics({"A": {"turnaround": 4, "waiting": 1, "response": 0},
                     "B": {"turnaround": 6, "waiting": 3, "response": 2}})
      == {"turnaround": 5.0, "waiting": 2.0, "response": 1.0}
    """
    raise NotImplementedError


if __name__ == "__main__":
    jobs = [Job("A", 0, 8), Job("B", 1, 4), Job("C", 2, 9), Job("D", 3, 5)]
    for policy in (fcfs, sjf, srtf):
        line = policy(jobs)
        avg = average_metrics(metrics(jobs, line))
        print(f"{policy.__name__:5} {gantt(line)}")
        print(f"      timeline={line}")
        print(f"      average turnaround={avg['turnaround']:.2f} "
              f"waiting={avg['waiting']:.2f} response={avg['response']:.2f}")
