"""Protection, virtual machines, and containers.

Three small models of isolation:
  1. Unix permission checks from mode bits, owner, group, and the sticky bit.
  2. A trap-and-emulate hypervisor: guests run on a deprivileged CPU, and a
     monitor emulates their privileged instructions against per-VM state.
  3. Resource limits, applied with setrlimit in a real child process.
"""

from __future__ import annotations

import os
import resource
import signal
import time
from dataclasses import dataclass, field

R, W, X = 4, 2, 1  # the permission bits within one rwx triple


# --- Part 1: Unix permissions -------------------------------------------------


def describe_mode(mode: int) -> str:
    """Render the low 12 bits of `mode` the way `ls -l` does, nine characters.

    setuid (0o4000) turns the owner's x slot into "s" (or "S" when x is off),
    setgid (0o2000) does the same for the group slot, and the sticky bit
    (0o1000) turns the other slot's x into "t" (or "T" when x is off).

    >>> describe_mode(0o755)
    'rwxr-xr-x'
    >>> describe_mode(0o1777)
    'rwxrwxrwt'
    """
    raise NotImplementedError("write this function")


def may_access(mode, owner_uid, owner_gid, uid, gids, want, is_dir=False) -> bool:
    """Can a process with user id `uid` and group ids `gids` get access `want`?

    `want` is a mix of R (4), W (2), and X (1), such as 6 for read and write.
    Raise ValueError unless 1 <= want <= 7.

    Ordinary users: exactly one class applies. The owner class if uid ==
    owner_uid (even when the group or other bits are more generous), else the
    group class if owner_gid is in `gids`, else the other class. All the wanted
    bits must be present in that class.

    Root (uid 0) passes every read and write. It passes execute only when the
    file has at least one x bit set in `mode`, or when `is_dir` is True
    (searching a directory).

    >>> may_access(0o640, 1000, 100, 1000, {100}, R | W)
    True
    """
    raise NotImplementedError("write this function")


def may_delete(dir_mode, dir_uid, dir_gid, file_uid, uid, gids) -> bool:
    """Can this process remove (unlink) a file from the directory?

    Deleting needs write and execute permission on the DIRECTORY (the file's
    own mode does not matter). If the directory has the sticky bit (0o1000),
    only root, the directory's owner, or the file's owner may delete.

    >>> may_delete(0o1777, 0, 0, 1000, 2000, {2000})   # /tmp, someone else's file
    False
    """
    raise NotImplementedError("write this function")


# --- Part 2: a trap-and-emulate hypervisor -----------------------------------

PRIVILEGED = {"cli", "sti", "out", "wrbase", "rdbase", "hlt"}


class PrivilegeTrap(Exception):
    """Raised by the 'hardware' when a deprivileged guest runs a privileged instruction."""

    def __init__(self, instr):
        super().__init__(f"privileged instruction {instr!r}")
        self.instr = instr


@dataclass
class VM:
    """One guest. Its program is a list of tuples such as ("mov", "a", 5).

    Unprivileged: ("mov", reg, imm), ("add", reg, imm), ("jnz", reg, target).
    Privileged:   ("cli",), ("sti",), ("out", port, reg), ("wrbase", reg),
                  ("rdbase", reg), ("hlt",).
    """

    name: str
    program: list
    ports: set = field(default_factory=set)  # I/O ports this guest owns
    regs: dict = field(default_factory=lambda: {"a": 0, "b": 0, "c": 0})
    pc: int = 0
    vif: bool = True  # the guest's VIRTUAL interrupt flag
    vbase: int = 0  # the guest's VIRTUAL page-table base register
    console: list = field(default_factory=list)  # (port, value) pairs the guest wrote
    halted: bool = False
    fault: str | None = None


def hw_execute(vm: VM, instr: tuple) -> None:
    """The deprivileged CPU. Runs mov, add, and jnz directly and advances vm.pc.

    Any privileged instruction raises PrivilegeTrap and changes nothing.
    """
    op = instr[0]
    if op in PRIVILEGED:
        raise PrivilegeTrap(instr)
    if op == "mov":
        vm.regs[instr[1]] = instr[2]
        vm.pc += 1
    elif op == "add":
        vm.regs[instr[1]] += instr[2]
        vm.pc += 1
    elif op == "jnz":
        vm.pc = instr[2] if vm.regs[instr[1]] != 0 else vm.pc + 1
    else:
        raise ValueError(f"unknown instruction {instr!r}")


def emulate_privileged(vm: VM, instr: tuple) -> None:
    """The monitor's trap handler: do what the instruction means, to the VM's virtual state.

    cli / sti       set vm.vif to False / True
    out port, reg   append (port, value of reg) to vm.console, but only if
                    port is in vm.ports; otherwise halt the VM and set
                    vm.fault to "bad port <port>"
    wrbase reg      vm.vbase = value of reg
    rdbase reg      reg = vm.vbase
    hlt             vm.halted = True
    Every emulated instruction advances vm.pc by one. Raise ValueError for an
    instruction that is not privileged.
    """
    raise NotImplementedError("write this function")


def run_vm(vm: VM, max_steps: int = 1000) -> tuple:
    """Run the guest for at most `max_steps` instructions. Return (direct, traps).

    Each step fetches vm.program[vm.pc] and tries hw_execute. On PrivilegeTrap,
    call emulate_privileged instead. `direct` counts instructions that ran
    without a trap, `traps` counts the emulated ones (including hlt and a
    faulting out). Stop when the VM halts. If pc leaves the program, set
    vm.halted = True and stop; that step does not count.

    >>> run_vm(VM("g", [("mov", "a", 1), ("cli",)]))
    (1, 1)
    """
    raise NotImplementedError("write this function")


def run_vms(vms: list, quantum: int, max_slices: int = 10000) -> list:
    """Round-robin the guests, `quantum` instructions at a time, until all halt.

    Visit the VMs in list order each round, skipping halted ones. Return the
    list of (vm.name, instructions_executed) for every slice that executed at
    least one instruction. Stop after `max_slices` slices, in case a guest
    never halts.
    """
    raise NotImplementedError("write this function")


# --- Part 3: resource limits ----------------------------------------------------


def describe_outcome(status: int) -> tuple:
    """Decode a wait status: ("exited", code) or ("signaled", signal number).

    >>> describe_outcome(3 << 8)
    ('exited', 3)
    """
    raise NotImplementedError("write this function")


def run_limited(func, limits: dict, timeout: float = 10.0) -> tuple:
    """Run `func()` in a forked child under resource limits, and report how it ended.

    `limits` maps a resource constant to a (soft, hard) pair, for example
    {resource.RLIMIT_NOFILE: (16, 16)}. In the child: set RLIMIT_CORE to (0, 0)
    first, apply each limit, call func(), and exit with status 0. If func raises
    or a limit cannot be set, exit with status 70. The child always leaves
    with os._exit. In the parent: wait for the child, but if it runs longer
    than `timeout` seconds of wall time, send SIGKILL. Always reap the child.
    Return describe_outcome of the wait status.
    """
    raise NotImplementedError("write this function")


if __name__ == "__main__":
    print("permissions:")
    print("  0o640 as text:", describe_mode(0o640))
    print("  owner reads 0o640:", may_access(0o640, 1000, 100, 1000, {100}, R))
    print("  stranger reads 0o640:", may_access(0o640, 1000, 100, 2000, {2000}, R))
    print("  root executes a 0o644 file:", may_access(0o644, 1000, 100, 0, {0}, X))
    print("  delete in /tmp (sticky) someone else's file:", may_delete(0o1777, 0, 0, 1000, 2000, {2000}))

    guest = VM("guest", [("mov", "a", 42), ("cli",), ("out", 1, "a"), ("wrbase", "a"), ("hlt",)], ports={1})
    direct, traps = run_vm(guest)
    print(f"hypervisor: {direct} direct, {traps} trapped; console={guest.console}, vif={guest.vif}, vbase={guest.vbase}")

    def spend_file_handles():
        try:
            for _ in range(100):
                os.open("/dev/null", os.O_RDONLY)
        except OSError:
            os._exit(7)  # ran out of file descriptors

    how = run_limited(spend_file_handles, {resource.RLIMIT_NOFILE: (16, 16)})
    print("child with 16 file descriptors allowed:", how, "(exit 7 means the limit stopped it)")
