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
    chars = [ch if mode & (0o400 >> i) else "-" for i, ch in enumerate("rwxrwxrwx")]
    for flag, slot, on, off in ((0o4000, 2, "s", "S"), (0o2000, 5, "s", "S"), (0o1000, 8, "t", "T")):
        if mode & flag:
            chars[slot] = on if chars[slot] == "x" else off
    return "".join(chars)


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
    if not 1 <= want <= 7:
        raise ValueError("want must be 1..7")
    if uid == 0:
        if want & X and not is_dir and not mode & 0o111:
            return False
        return True
    if uid == owner_uid:
        bits = (mode >> 6) & 7
    elif owner_gid in gids:
        bits = (mode >> 3) & 7
    else:
        bits = mode & 7
    return bits & want == want


def may_delete(dir_mode, dir_uid, dir_gid, file_uid, uid, gids) -> bool:
    """Can this process remove (unlink) a file from the directory?

    Deleting needs write and execute permission on the DIRECTORY (the file's
    own mode does not matter). If the directory has the sticky bit (0o1000),
    only root, the directory's owner, or the file's owner may delete.

    >>> may_delete(0o1777, 0, 0, 1000, 2000, {2000})   # /tmp, someone else's file
    False
    """
    if not may_access(dir_mode, dir_uid, dir_gid, uid, gids, W | X, is_dir=True):
        return False
    if dir_mode & 0o1000 and uid not in (0, dir_uid, file_uid):
        return False
    return True


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
    op = instr[0]
    if op == "cli":
        vm.vif = False
    elif op == "sti":
        vm.vif = True
    elif op == "out":
        port, reg = instr[1], instr[2]
        if port in vm.ports:
            vm.console.append((port, vm.regs[reg]))
        else:
            vm.halted = True
            vm.fault = f"bad port {port}"
    elif op == "wrbase":
        vm.vbase = vm.regs[instr[1]]
    elif op == "rdbase":
        vm.regs[instr[1]] = vm.vbase
    elif op == "hlt":
        vm.halted = True
    else:
        raise ValueError(f"not a privileged instruction: {instr!r}")
    vm.pc += 1


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
    direct = traps = 0
    while not vm.halted and direct + traps < max_steps:
        if not 0 <= vm.pc < len(vm.program):
            vm.halted = True
            break
        instr = vm.program[vm.pc]
        try:
            hw_execute(vm, instr)
            direct += 1
        except PrivilegeTrap:
            emulate_privileged(vm, instr)
            traps += 1
    return direct, traps


def run_vms(vms: list, quantum: int, max_slices: int = 10000) -> list:
    """Round-robin the guests, `quantum` instructions at a time, until all halt.

    Visit the VMs in list order each round, skipping halted ones. Return the
    list of (vm.name, instructions_executed) for every slice that executed at
    least one instruction. Stop after `max_slices` slices, in case a guest
    never halts.
    """
    log = []
    while any(not vm.halted for vm in vms) and len(log) < max_slices:
        for vm in vms:
            if vm.halted:
                continue
            direct, traps = run_vm(vm, quantum)
            if direct + traps:
                log.append((vm.name, direct + traps))
    return log


# --- Part 3: resource limits ----------------------------------------------------


def describe_outcome(status: int) -> tuple:
    """Decode a wait status: ("exited", code) or ("signaled", signal number).

    >>> describe_outcome(3 << 8)
    ('exited', 3)
    """
    if os.WIFSIGNALED(status):
        return ("signaled", os.WTERMSIG(status))
    return ("exited", os.WEXITSTATUS(status))


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
    pid = os.fork()
    if pid == 0:
        code = 70
        try:
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            for res, (soft, hard) in limits.items():
                resource.setrlimit(res, (soft, hard))
            func()
            code = 0
        except BaseException:  # noqa: BLE001 - a child must never escape
            code = 70
        finally:
            os._exit(code)
    deadline = time.monotonic() + timeout
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done:
            return describe_outcome(status)
        if time.monotonic() > deadline:
            os.kill(pid, signal.SIGKILL)
            _, status = os.waitpid(pid, 0)
            return describe_outcome(status)
        time.sleep(0.01)


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
