"""A toy process table: PCBs, the state machine, parents and children, and reaping.

You fill in `can_transition` and the methods of `ProcessTable`. The data
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


def can_transition(old: str, new: str) -> bool:
    """Return True when the state machine allows moving from `old` to `new`.

    The arrows are: new -> ready; ready -> running; running -> ready, blocked,
    or zombie; blocked -> ready; zombie -> terminated. Nothing else.

    >>> can_transition("ready", "running")
    True
    >>> can_transition("blocked", "running")
    False
    """
    raise NotImplementedError


class ProcessTable:
    """A process table holding PCBs keyed by pid. Pid 1 is `init`, always present."""

    def __init__(self, max_procs: int = 64) -> None:
        self.max_procs = max_procs
        self.procs: dict[int, PCB] = {1: PCB(pid=1, ppid=0, name="init", state=READY)}
        self.next_pid = 2

    def get(self, pid: int) -> PCB:
        """Return the PCB for `pid`, or raise NoSuchProcess."""
        raise NotImplementedError

    def create(self, name: str, ppid: int = 1) -> int:
        """Create a child of `ppid` in state `new` and return its pid.

        Pids count up from 2 and are never reused. Raise NoSuchProcess when the
        parent is missing, a zombie, or terminated. Raise ProcessLimit when the
        number of processes that are not terminated has reached `max_procs`.
        Add the new pid to the parent's `children`.

        >>> t = ProcessTable(); t.create("shell")
        2
        """
        raise NotImplementedError

    def transition(self, pid: int, new_state: str) -> None:
        """Move `pid` to `new_state`, or raise IllegalTransition and change nothing.

        Refuse a move the state machine forbids. Refuse any move into `zombie`
        or `terminated`, which only `exit` and `wait` may do. Refuse a move
        into `running` while another process is already running (one CPU).
        """
        raise NotImplementedError

    def exit(self, pid: int, status: int) -> None:
        """End a running process: it becomes a zombie holding `status`.

        Raise IllegalTransition if the process is not running, or if it is
        pid 1. Every child of the exiting process is re-parented to pid 1.
        """
        raise NotImplementedError

    def wait(self, parent_pid: int, child_pid: Optional[int] = None):
        """Reap a zombie child of `parent_pid`.

        Return `(child_pid, exit_status)` and mark that child terminated and
        remove it from the parent's `children`. With `child_pid` given, look
        only at that child. Return None when the children are all still alive
        (a real wait would block). Raise NoChildren when there is no child to
        wait for.
        """
        raise NotImplementedError

    def descendants(self, pid: int) -> list:
        """Return the sorted pids of every child, grandchild, and so on of `pid`."""
        raise NotImplementedError

    def count_by_state(self) -> dict:
        """Return a dict with every state in STATES as a key and a process count as the value."""
        raise NotImplementedError


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
