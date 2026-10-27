"""Locks: spin locks, a ticket lock, and Peterson's algorithm on the simulator.

The simulator is the one from lesson 18, extended with jumps, atomic hardware
operations, and a marker for the critical section. A *program* is a list of
steps. Each step is a tuple whose first item names the operation:

    ("load", reg, addr)             reg = mem[addr]
    ("add", reg, n)                 reg = reg + n
    ("sub", reg, reg2)              reg = reg - reg2
    ("store", addr, reg)            mem[addr] = reg
    ("set", addr, n)                mem[addr] = n
    ("tas", reg, addr)              ATOMIC: reg = mem[addr]; mem[addr] = 1
    ("cas", reg, addr, old, new)    ATOMIC: if mem[addr] == old: mem[addr] = new,
                                    reg = 1; otherwise reg = 0
    ("faa", reg, addr, n)           ATOMIC: reg = mem[addr]; mem[addr] += n
    ("jmp", target)                 pc = target
    ("jz", reg, target)             if reg == 0: pc = target
    ("jnz", reg, target)            if reg != 0: pc = target
    ("cs_enter",), ("cs_leave",)    mark the critical section

Jump targets are indexes into the program list. A thread is finished when its pc
runs off the end of its program. Mutual exclusion is violated in any state where
two threads are between `cs_enter` and `cs_leave`.
"""

from __future__ import annotations


class Machine:
    """Shared memory, plus a register file and program counter per thread."""

    def __init__(self, programs, mem=None):
        self.programs = programs
        self.mem = dict(mem or {})
        self.regs = [{} for _ in programs]
        self.pc = [0 for _ in programs]
        self.in_cs = set()

    def done(self, tid):
        return self.pc[tid] >= len(self.programs[tid])

    def copy(self):
        other = Machine(self.programs)
        other.mem = dict(self.mem)
        other.regs = [dict(r) for r in self.regs]
        other.pc = list(self.pc)
        other.in_cs = set(self.in_cs)
        return other

    def key(self):
        """A hashable snapshot of the whole machine state."""
        return (
            tuple(sorted(self.mem.items())),
            tuple(tuple(sorted(r.items())) for r in self.regs),
            tuple(self.pc),
            tuple(sorted(self.in_cs)),
        )

    def step(self, tid):
        """Run one atomic step of thread `tid`."""
        op = self.programs[tid][self.pc[tid]]
        regs, mem, name = self.regs[tid], self.mem, op[0]
        nxt = self.pc[tid] + 1
        if name == "load":
            regs[op[1]] = mem.get(op[2], 0)
        elif name == "add":
            regs[op[1]] = regs.get(op[1], 0) + op[2]
        elif name == "sub":
            regs[op[1]] = regs.get(op[1], 0) - regs.get(op[2], 0)
        elif name == "store":
            mem[op[1]] = regs.get(op[2], 0)
        elif name == "set":
            mem[op[1]] = op[2]
        elif name == "tas":
            regs[op[1]] = mem.get(op[2], 0)
            mem[op[2]] = 1
        elif name == "cas":
            _, reg, addr, old, new = op
            if mem.get(addr, 0) == old:
                mem[addr] = new
                regs[reg] = 1
            else:
                regs[reg] = 0
        elif name == "faa":
            _, reg, addr, n = op
            regs[reg] = mem.get(addr, 0)
            mem[addr] = regs[reg] + n
        elif name == "jmp":
            nxt = op[1]
        elif name == "jz":
            if regs.get(op[1], 0) == 0:
                nxt = op[2]
        elif name == "jnz":
            if regs.get(op[1], 0) != 0:
                nxt = op[2]
        elif name == "cs_enter":
            self.in_cs.add(tid)
        elif name == "cs_leave":
            self.in_cs.discard(tid)
        else:
            raise ValueError(f"unknown operation {name!r}")
        self.pc[tid] = nxt


def critical_section():
    """The five steps every lock protects: mark entry, counter += 1, mark exit."""
    return [
        ("cs_enter",),
        ("load", "c", "counter"),
        ("add", "c", 1),
        ("store", "counter", "c"),
        ("cs_leave",),
    ]


def run_schedule(programs, schedule, mem=None):
    """Run `schedule` on a fresh Machine and return it. Finished threads are skipped."""
    machine = Machine(programs, mem)
    for tid in schedule:
        if not machine.done(tid):
            machine.step(tid)
    return machine


# ---------------------------------------------------------------- lock programs


def spin_lock_program():
    """Test-and-set spin lock around the critical section. Lock cell: "lock".

    Return a list of steps: take the lock with an atomic `tas`, jump back to
    retry while the old value was 1, run critical_section(), then store 0.
    Run alone, it leaves mem["counter"] == 1 and mem["lock"] == 0.
    """
    raise NotImplementedError


def cas_lock_program():
    """Compare-and-swap spin lock. Lock cell: "lock".

    Like spin_lock_program, but take the lock with ("cas", reg, "lock", 0, 1)
    and retry while the register says the swap failed.
    """
    raise NotImplementedError


def ticket_lock_program():
    """Ticket lock. Cells: "next_ticket" and "now_serving", both starting at 0.

    Take a ticket with an atomic fetch-and-add on "next_ticket", spin until
    "now_serving" equals your ticket (use `sub` and `jnz`), run the critical
    section, then add 1 to "now_serving".
    """
    raise NotImplementedError


def peterson_program(tid):
    """Peterson's algorithm for thread `tid` (0 or 1). Cells: flag0, flag1, turn.

    Set your flag, give the turn to the other thread, then spin while the other
    thread's flag is set and the turn is theirs. Run the critical section, then
    clear your flag.
    """
    raise NotImplementedError


# ------------------------------------------------------------------ exploration


def reachable(programs, mem=None):
    """Every state the machine can reach, each with a shortest schedule to it.

    Returns a dict mapping Machine.key() to a list of thread ids. Search
    breadth-first, trying thread 0 before thread 1, so the answer is
    deterministic. Loops (a thread spinning forever) must not loop your search:
    visit each state once.

    Example: for two programs [("set", "x", 1)] the dict has 4 states, and the
    start state maps to [].
    """
    raise NotImplementedError


def find_violation(programs, mem=None):
    """The shortest schedule that puts two threads in the critical section, or None.

    A state violates mutual exclusion when machine.in_cs holds two thread ids.
    """
    raise NotImplementedError


def final_values(programs, mem, addr):
    """Sorted values of `addr` over every reachable state where all threads finished.

    Example: two unprotected increments can end with 1 or 2, so the answer is [1, 2].
    """
    raise NotImplementedError


if __name__ == "__main__":
    mem = {"counter": 0, "lock": 0}

    # A lock with a bug: check the flag, then set it. Two steps, not one.
    naive = [
        ("load", "f", "lock"),
        ("jnz", "f", 0),
        ("set", "lock", 1),
    ] + critical_section() + [("set", "lock", 0)]
    bad = find_violation([naive, naive], mem)
    print("naive lock breaks mutual exclusion with schedule:", bad)

    spin = spin_lock_program()
    states = reachable([spin, spin], mem)
    print("test-and-set lock: reachable states =", len(states))
    print("  violation:", find_violation([spin, spin], mem))
    print("  final counter values:", final_values([spin, spin], mem, "counter"))

    p = [peterson_program(0), peterson_program(1)]
    print("Peterson: violation:", find_violation(p, {"counter": 0}))
    print("  final counter values:", final_values(p, {"counter": 0}, "counter"))
