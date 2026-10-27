"""A toy process table: PCBs, the state machine, parents and children, and reaping.

Reference solution. You fill in `can_transition` and the methods of `ProcessTable`. The data
classes, the exceptions, and `__init__` are given.
"""

from dataclasses import dataclass, field
from typing import Optional

NEW, READY, RUNNING, BLOCKED, ZOMBIE, TERMINATED = (
    "new",
    "ready",
    "running",
    "blocked",
    "zombie",
    "terminated",
)
STATES = (NEW, READY, RUNNING, BLOCKED, ZOMBIE, TERMINATED)


class IllegalTransition(Exception):
    """A state change the state machine does not allow."""


class NoSuchProcess(Exception):
    """A pid that is not in the table (or a parent that can no longer fork)."""


class NoChildren(Exception):
    """wait() was called by a process that has nothing to wait for (ECHILD)."""


class ProcessLimit(Exception):
    """The table is full, like fork failing with EAGAIN."""


@dataclass
class PCB:
    """The process control block: everything the kernel tracks for one process."""

    pid: int
    ppid: int
    name: str
    state: str = NEW
    exit_status: Optional[int] = None
    children: list = field(default_factory=list)


# The state machine as data: each state maps to the states it may move to.
_ALLOWED = {
    NEW: {READY},
    READY: {RUNNING},
    RUNNING: {READY, BLOCKED, ZOMBIE},
    BLOCKED: {READY},
    ZOMBIE: {TERMINATED},
    TERMINATED: set(),
}


def can_transition(old: str, new: str) -> bool:
    """Return True when the state machine allows moving from `old` to `new`.

    >>> can_transition("ready", "running")
    True
    >>> can_transition("blocked", "running")
    False
    """
    return new in _ALLOWED.get(old, set())


class ProcessTable:
    """A process table holding PCBs keyed by pid. Pid 1 is `init`, always present."""

    def __init__(self, max_procs: int = 64) -> None:
        self.max_procs = max_procs
        self.procs: dict[int, PCB] = {1: PCB(pid=1, ppid=0, name="init", state=READY)}
        self.next_pid = 2

    def get(self, pid: int) -> PCB:
        try:
            return self.procs[pid]
        except KeyError:
            raise NoSuchProcess(f"no process with pid {pid}") from None

    def _live_count(self) -> int:
        # Zombies still occupy a slot; only terminated entries are free.
        return sum(1 for p in self.procs.values() if p.state != TERMINATED)

    def create(self, name: str, ppid: int = 1) -> int:
        parent = self.get(ppid)
        if parent.state in (ZOMBIE, TERMINATED):
            raise NoSuchProcess(f"pid {ppid} is {parent.state} and cannot create children")
        if self._live_count() >= self.max_procs:
            raise ProcessLimit(f"process table is full ({self.max_procs})")
        pid = self.next_pid
        self.next_pid += 1
        self.procs[pid] = PCB(pid=pid, ppid=ppid, name=name)
        parent.children.append(pid)
        return pid

    def transition(self, pid: int, new_state: str) -> None:
        pcb = self.get(pid)
        if not can_transition(pcb.state, new_state):
            raise IllegalTransition(f"pid {pid}: {pcb.state} -> {new_state} is not allowed")
        if new_state in (ZOMBIE, TERMINATED):
            raise IllegalTransition(f"pid {pid}: use exit() or wait() to enter {new_state}")
        if new_state == RUNNING:
            for other in self.procs.values():
                if other.state == RUNNING:
                    raise IllegalTransition(
                        f"pid {pid}: pid {other.pid} is already running (one CPU)"
                    )
        pcb.state = new_state

    def exit(self, pid: int, status: int) -> None:
        pcb = self.get(pid)
        if pid == 1:
            raise IllegalTransition("init never exits")
        if pcb.state != RUNNING:
            raise IllegalTransition(f"pid {pid} is {pcb.state}; only a running process can exit")
        pcb.state = ZOMBIE
        pcb.exit_status = status
        # Orphans are adopted by init, which will reap them.
        init = self.procs[1]
        for child_pid in pcb.children:
            self.procs[child_pid].ppid = 1
            init.children.append(child_pid)
        pcb.children = []

    def wait(self, parent_pid: int, child_pid: Optional[int] = None):
        parent = self.get(parent_pid)
        if child_pid is None:
            candidates = list(parent.children)
        elif child_pid in parent.children:
            candidates = [child_pid]
        else:
            raise NoChildren(f"pid {child_pid} is not a child of {parent_pid}")
        if not candidates:
            raise NoChildren(f"pid {parent_pid} has no children")
        for pid in candidates:
            child = self.procs[pid]
            if child.state == ZOMBIE:
                child.state = TERMINATED
                parent.children.remove(pid)
                return (pid, child.exit_status)
        return None  # children exist, but none has exited yet

    def descendants(self, pid: int) -> list:
        found = []
        stack = list(self.get(pid).children)
        while stack:
            current = stack.pop()
            found.append(current)
            stack.extend(self.procs[current].children)
        return sorted(found)

    def count_by_state(self) -> dict:
        counts = {state: 0 for state in STATES}
        for pcb in self.procs.values():
            counts[pcb.state] += 1
        return counts


if __name__ == "__main__":
    table = ProcessTable()
    shell = table.create("shell")
    table.transition(shell, READY)
    table.transition(shell, RUNNING)
    worker = table.create("worker", ppid=shell)
    table.transition(worker, READY)
    table.transition(shell, BLOCKED)
    table.transition(worker, RUNNING)
    table.exit(worker, 0)
    print("after worker exits:")
    for pcb in table.procs.values():
        print(f"  pid={pcb.pid} ppid={pcb.ppid} {pcb.name:<7} {pcb.state}")
    print("count:", table.count_by_state())
    print("reaped:", table.wait(shell))
    print("worker is now", table.get(worker).state)
