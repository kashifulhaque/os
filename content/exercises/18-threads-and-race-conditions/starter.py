"""Threads and race conditions: an interleaving simulator, then real threads.

A *program* is a list of atomic steps. A step is a tuple whose first item names
the operation:

    ("load", reg, addr)    reg = mem[addr]
    ("add", reg, n)        reg = reg + n
    ("store", addr, reg)   mem[addr] = reg
    ("set", addr, n)       mem[addr] = n

Memory (`mem`) is shared by every thread. Registers belong to one thread each.
A *schedule* is a list of thread ids: [0, 1, 0] means "run one step of thread 0,
then one step of thread 1, then one more step of thread 0".
"""

from __future__ import annotations

import threading


class Machine:
    """Shared memory, one register file and program counter per thread."""

    def __init__(self, programs, mem=None):
        self.programs = programs
        self.mem = dict(mem or {})
        self.regs = [{} for _ in programs]  # regs[tid] maps register name -> int
        self.pc = [0 for _ in programs]  # pc[tid] is the index of tid's next step

    def done(self, tid):
        """True once thread `tid` has run every step of its program."""
        return self.pc[tid] >= len(self.programs[tid])

    def step(self, tid):
        """Run the next step of thread `tid`, then move its program counter on.

        Registers and memory cells that were never written read as 0. Raise
        ValueError for a finished thread or an unknown operation name.

        Example: with programs [[("set", "x", 4)]], machine.step(0) leaves
        machine.mem == {"x": 4} and machine.pc == [1].
        """
        raise NotImplementedError


def increment_program(addr="counter"):
    """The three atomic steps of `counter += 1`: load, add, store.

    Example: increment_program("hits") loads hits into a register, adds 1, and
    stores the register back into hits.
    """
    raise NotImplementedError


def run_schedule(programs, schedule, mem=None):
    """Run `schedule` on a fresh Machine and return the Machine.

    Scheduling a thread that has already finished does nothing.

    Example: run_schedule([increment_program()] * 2, [0, 0, 0, 1, 1, 1],
    {"counter": 0}).mem["counter"] is 2.
    """
    raise NotImplementedError


def interleavings(lengths):
    """Every schedule that runs `lengths[i]` steps of thread i, in order.

    Schedules come out in lexicographic order. interleavings([1, 1]) is
    [[0, 1], [1, 0]]. The count is the multinomial coefficient, so
    interleavings([3, 3]) has 20 schedules.
    """
    raise NotImplementedError


def outcome_counts(programs, mem, addr):
    """Map each final value of `addr` to the number of interleavings producing it.

    Example: two `set x` programs with values 1 and 2 give {2: 1, 1: 1}.
    """
    raise NotImplementedError


def find_lost_update(programs, mem, addr, expected):
    """The first interleaving whose final `addr` differs from `expected`, or None.

    "First" means first in the order `interleavings` returns.
    """
    raise NotImplementedError


class SafeCounter:
    """A counter that many real threads can increment without losing updates.

    `increment()` adds 1. The `value` property reads the current total.
    """

    def __init__(self):
        raise NotImplementedError

    def increment(self):
        raise NotImplementedError

    @property
    def value(self):
        raise NotImplementedError


def increment_with_lock(n_threads, n_iters):
    """Start `n_threads` threads that each add 1 to a shared total `n_iters` times.

    A threading.Lock guards the read-modify-write. Join every thread (use a
    timeout and raise RuntimeError if one is still alive). Return the total.

    Example: increment_with_lock(4, 1000) returns 4000.
    """
    raise NotImplementedError


if __name__ == "__main__":
    programs = [increment_program(), increment_program()]
    mem = {"counter": 0}

    print("Two threads each run: load, add 1, store.")
    print("Schedules to try:", len(interleavings([3, 3])))
    print("Final counter -> number of schedules:", outcome_counts(programs, mem, "counter"))

    bad = find_lost_update(programs, mem, "counter", 2)
    print("First schedule that loses an update:", bad)
    final = run_schedule(programs, bad, mem)
    print("It leaves counter =", final.mem["counter"], "instead of 2")

    print("Real threads with a lock:", increment_with_lock(4, 2000), "(expected 8000)")
