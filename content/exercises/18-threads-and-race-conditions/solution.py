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
        self.regs = [{} for _ in programs]
        self.pc = [0 for _ in programs]

    def done(self, tid):
        """True once thread `tid` has run every step of its program."""
        return self.pc[tid] >= len(self.programs[tid])

    def step(self, tid):
        """Run the next step of thread `tid`, then move its program counter on."""
        if self.done(tid):
            raise ValueError(f"thread {tid} has already finished")
        op = self.programs[tid][self.pc[tid]]
        regs = self.regs[tid]
        name = op[0]
        if name == "load":
            _, reg, addr = op
            regs[reg] = self.mem.get(addr, 0)
        elif name == "add":
            _, reg, n = op
            regs[reg] = regs.get(reg, 0) + n
        elif name == "store":
            _, addr, reg = op
            self.mem[addr] = regs.get(reg, 0)
        elif name == "set":
            _, addr, n = op
            self.mem[addr] = n
        else:
            raise ValueError(f"unknown operation {name!r}")
        self.pc[tid] += 1


def increment_program(addr="counter"):
    """The three atomic steps of `counter += 1`: load, add, store."""
    return [("load", "r", addr), ("add", "r", 1), ("store", addr, "r")]


def run_schedule(programs, schedule, mem=None):
    """Run `schedule` on a fresh Machine and return the Machine.

    Scheduling a thread that has already finished does nothing.
    """
    machine = Machine(programs, mem)
    for tid in schedule:
        if not machine.done(tid):
            machine.step(tid)
    return machine


def interleavings(lengths):
    """Every schedule that runs `lengths[i]` steps of thread i, in order.

    Schedules come out in lexicographic order. interleavings([1, 1]) is
    [[0, 1], [1, 0]].
    """
    remaining = list(lengths)
    schedules = []
    current = []

    def build():
        if sum(remaining) == 0:
            schedules.append(list(current))
            return
        for tid in range(len(remaining)):
            if remaining[tid] > 0:
                # Choose thread `tid` for the next slot, explore, then undo.
                remaining[tid] -= 1
                current.append(tid)
                build()
                current.pop()
                remaining[tid] += 1

    build()
    return schedules


def outcome_counts(programs, mem, addr):
    """Map each final value of `addr` to the number of interleavings producing it."""
    counts = {}
    for schedule in interleavings([len(p) for p in programs]):
        value = run_schedule(programs, schedule, mem).mem.get(addr, 0)
        counts[value] = counts.get(value, 0) + 1
    return counts


def find_lost_update(programs, mem, addr, expected):
    """The first interleaving whose final `addr` differs from `expected`, or None."""
    for schedule in interleavings([len(p) for p in programs]):
        if run_schedule(programs, schedule, mem).mem.get(addr, 0) != expected:
            return schedule
    return None


class SafeCounter:
    """A counter that many real threads can increment without losing updates."""

    def __init__(self):
        self._lock = threading.Lock()
        self._value = 0

    def increment(self):
        with self._lock:
            self._value += 1

    @property
    def value(self):
        with self._lock:
            return self._value


def increment_with_lock(n_threads, n_iters):
    """Start `n_threads` threads that each add 1 to a shared total `n_iters` times.

    A lock guards the read-modify-write. Returns the final total.
    """
    total = [0]
    lock = threading.Lock()

    def work():
        for _ in range(n_iters):
            with lock:
                total[0] += 1

    threads = [threading.Thread(target=work) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        if t.is_alive():
            raise RuntimeError("a worker thread did not finish")
    return total[0]


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
