"""Checks for the protection exercise: permissions, a toy hypervisor, and rlimits."""

import errno
import os
import resource
import signal
import tempfile
import time

from oscheck import check, equal, fail, has

R, W, X = 4, 2, 1


@check("describe_mode renders permission bits like ls -l, including setuid, setgid, and sticky")
def test_describe(sub):
    d = has(sub, "describe_mode")
    cases = {
        0o644: "rw-r--r--",
        0o755: "rwxr-xr-x",
        0o000: "---------",
        0o777: "rwxrwxrwx",
        0o4755: "rwsr-xr-x",  # setuid with owner x
        0o4644: "rwSr--r--",  # setuid without owner x
        0o2755: "rwxr-sr-x",  # setgid with group x
        0o2745: "rwxr-Sr-x",  # setgid without group x
        0o1777: "rwxrwxrwt",  # sticky with other x
        0o1666: "rw-rw-rwT",  # sticky without other x
        0o7777: "rwsrwsrwt",
    }
    for mode, want in cases.items():
        equal(d(mode), want, label=f"describe_mode({oct(mode)})")


@check("may_access picks exactly one class: owner, then group, then other")
def test_classes(sub):
    f = has(sub, "may_access")
    # mode 0o640: owner rw-, group r--, other ---. File owned by uid 1000, gid 100.
    equal(f(0o640, 1000, 100, 1000, {1000}, R | W), True, label="owner read+write on 0o640")
    equal(f(0o640, 1000, 100, 1000, {1000}, X), False, label="owner execute on 0o640")
    equal(f(0o640, 1000, 100, 2000, {100, 2000}, R), True, label="group member read on 0o640")
    equal(f(0o640, 1000, 100, 2000, {100, 2000}, W), False, label="group member write on 0o640")
    equal(f(0o640, 1000, 100, 3000, {3000}, R), False, label="stranger read on 0o640")
    # The owner class wins even when the group class is more generous: mode 0o070.
    equal(f(0o070, 1000, 100, 1000, {100, 1000}, R), False, label="owner of a 0o070 file is locked out")
    equal(f(0o070, 1000, 100, 2000, {100}, R | W | X), True, label="group member of a 0o070 file")
    # And the group class wins over other: mode 0o007.
    equal(f(0o007, 1000, 100, 2000, {100}, R), False, label="group member of a 0o007 file")
    equal(f(0o007, 1000, 100, 3000, {3000}, R | W | X), True, label="stranger on a 0o007 file")
    equal(f(0o755, 1000, 100, 3000, {3000}, R | X), True, label="stranger read+execute on 0o755")
    equal(f(0o755, 1000, 100, 3000, {3000}, R | W), False, label="stranger read+write on 0o755 (all bits must hold)")
    for bad in (0, 8, -1):
        try:
            f(0o644, 1, 1, 1, {1}, bad)
        except ValueError:
            continue
        fail(f"may_access with want={bad} should raise ValueError")


@check("root passes every read and write, but execute needs an x bit unless the target is a directory")
def test_root(sub):
    f = has(sub, "may_access")
    equal(f(0o000, 1000, 100, 0, {0}, R | W), True, label="root read+write on 0o000")
    equal(f(0o600, 1000, 100, 0, {0}, W), True, label="root write on 0o600")
    equal(f(0o644, 1000, 100, 0, {0}, X), False, label="root execute on 0o644 (no x bit anywhere)")
    equal(f(0o644, 1000, 100, 0, {0}, R | X), False, label="root read+execute on 0o644")
    equal(f(0o700, 1000, 100, 0, {0}, X), True, label="root execute on 0o700 (owner x only)")
    equal(f(0o001, 1000, 100, 0, {0}, R | W | X), True, label="root everything on 0o001")
    equal(f(0o644, 1000, 100, 0, {0}, X, is_dir=True), True, label="root searches a 0o644 directory")
    equal(f(0o000, 1000, 100, 1000, {100}, R, is_dir=True), False, label="owner is still limited on a directory")


@check("may_delete needs write and execute on the directory, plus the sticky-bit ownership rule")
def test_delete(sub):
    f = has(sub, "may_delete")
    # args: dir_mode, dir_uid, dir_gid, file_uid, uid, gids
    equal(f(0o755, 0, 0, 1000, 1000, {1000}), False, label="owner of the file in a directory they cannot write")
    equal(f(0o775, 0, 50, 1000, 1000, {1000, 50}), True, label="group member with write+exec on the directory")
    equal(f(0o770, 0, 50, 1000, 1000, {1000, 50}), True, label="same, 0o770")
    equal(f(0o760, 0, 50, 1000, 1000, {1000, 50}), False, label="group has write but no execute on the directory")
    equal(f(0o777, 0, 0, 1000, 2000, {2000}), True, label="no sticky bit: anyone may delete anyone's file")
    equal(f(0o1777, 0, 0, 1000, 2000, {2000}), False, label="sticky: a stranger cannot delete")
    equal(f(0o1777, 0, 0, 1000, 1000, {1000}), True, label="sticky: the file's owner can")
    equal(f(0o1777, 500, 0, 1000, 500, {500}), True, label="sticky: the directory's owner can")
    equal(f(0o1777, 500, 0, 1000, 0, {0}), True, label="sticky: root can")
    equal(f(0o1755, 500, 0, 1000, 1000, {1000}), False, label="sticky: the file's owner without write on the directory")
    equal(f(0o000, 500, 0, 1000, 0, {0}), True, label="root can delete from a 0o000 directory")


def make_vm(sub, name, program, ports=()):
    return has(sub, "VM")(name, program, ports=set(ports))


@check("emulate_privileged updates the guest's virtual state and advances the program counter")
def test_emulate(sub):
    emu = has(sub, "emulate_privileged")
    vm = make_vm(sub, "g", [], ports={1, 2})
    emu(vm, ("cli",))
    equal((vm.vif, vm.pc), (False, 1), label="after cli")
    emu(vm, ("sti",))
    equal((vm.vif, vm.pc), (True, 2), label="after sti")
    vm.regs["a"] = 77
    emu(vm, ("out", 2, "a"))
    equal(vm.console, [(2, 77)], label="console after out")
    equal(vm.pc, 3, label="pc after out")
    emu(vm, ("wrbase", "a"))
    equal(vm.vbase, 77, label="vbase after wrbase a")
    emu(vm, ("rdbase", "b"))
    equal(vm.regs["b"], 77, label="register b after rdbase b")
    emu(vm, ("hlt",))
    equal((vm.halted, vm.pc), (True, 6), label="after hlt")
    bad = make_vm(sub, "x", [], ports={1})
    bad.regs["a"] = 5
    emu(bad, ("out", 9, "a"))
    equal((bad.halted, bad.fault, bad.console), (True, "bad port 9", []), label="out to a port the guest does not own")
    try:
        emu(make_vm(sub, "y", []), ("mov", "a", 1))
    except ValueError:
        return
    fail("emulate_privileged should raise ValueError for an unprivileged instruction")


@check("run_vm executes ordinary instructions directly and traps privileged ones")
def test_run_vm(sub):
    run_vm = has(sub, "run_vm")
    # a = 3; loop: out a; a = a - 1; jnz a, loop; hlt
    program = [
        ("mov", "a", 3),   # 0  direct
        ("out", 1, "a"),   # 1  trap
        ("add", "a", -1),  # 2  direct
        ("jnz", "a", 1),   # 3  direct
        ("hlt",),          # 4  trap
    ]
    vm = make_vm(sub, "loop", program, ports={1})
    direct, traps = run_vm(vm)
    # mov once; then 3 passes of out (trap), add, jnz; then hlt.
    equal((direct, traps), (1 + 3 * 2, 3 + 1), label="(direct, traps)")
    equal(vm.console, [(1, 3), (1, 2), (1, 1)], label="console output")
    equal((vm.halted, vm.regs["a"], vm.pc), (True, 0, 5), label="final (halted, a, pc)")
    equal(run_vm(vm), (0, 0), label="running a halted VM does nothing")
    short = make_vm(sub, "short", [("mov", "b", 9)])
    equal(run_vm(short), (1, 0), label="a program that runs off its end")
    equal((short.halted, short.regs["b"]), (True, 9), label="halted after falling off the end")
    spin = make_vm(sub, "spin", [("mov", "a", 1), ("jnz", "a", 1)])
    equal(run_vm(spin, max_steps=10), (10, 0), label="max_steps stops an endless loop")
    equal(spin.halted, False, label="an endless loop is not halted")
    prog = make_vm(sub, "bad", [("mov", "a", 1), ("out", 5, "a"), ("mov", "a", 2)], ports={1})
    equal(run_vm(prog), (1, 1), label="a faulting out stops the VM")
    equal((prog.fault, prog.regs["a"]), ("bad port 5", 1), label="fault and register after a bad out")


@check("run_vms time-slices guests round-robin and keeps their virtual state separate")
def test_run_vms(sub):
    run_vms = has(sub, "run_vms")
    a = make_vm(sub, "A", [("mov", "a", 1), ("cli",), ("out", 1, "a"), ("hlt",)], ports={1})
    b = make_vm(sub, "B", [("mov", "a", 2), ("out", 1, "a"), ("wrbase", "a"), ("sti",), ("hlt",)], ports={1})
    log = run_vms([a, b], quantum=2)
    # A has 4 instructions and B has 5. Each round gives each live VM up to 2 of them.
    equal(log, [("A", 2), ("B", 2), ("A", 2), ("B", 2), ("B", 1)], label="slice log")
    equal((a.vif, a.vbase, a.console), (False, 0, [(1, 1)]), label="VM A's virtual state")
    equal((b.vif, b.vbase, b.console), (True, 2, [(1, 2)]), label="VM B's virtual state")
    equal((a.halted, b.halted), (True, True), label="both halted")
    spin = make_vm(sub, "S", [("mov", "a", 1), ("jnz", "a", 1)])
    log = run_vms([spin], quantum=5, max_slices=4)
    equal(log, [("S", 5)] * 4, label="max_slices stops a VM that never halts")


@check("describe_outcome decodes wait statuses into ('exited', code) or ('signaled', signal)")
def test_outcome(sub):
    d = has(sub, "describe_outcome")
    equal(d(0), ("exited", 0), label="status 0")
    equal(d(3 << 8), ("exited", 3), label="exit code 3")
    equal(d(70 << 8), ("exited", 70), label="exit code 70")
    equal(d(signal.SIGKILL), ("signaled", signal.SIGKILL), label="killed by SIGKILL")
    equal(d(signal.SIGXCPU), ("signaled", 24), label="killed by SIGXCPU")
    equal(d(signal.SIGSEGV | 0x80), ("signaled", signal.SIGSEGV), label="SIGSEGV with the core-dump flag")


@check("run_limited reports normal exits, exceptions, and RLIMIT_NOFILE and RLIMIT_FSIZE limits")
def test_limits_files(sub):
    run_limited = has(sub, "run_limited")

    def fine():
        os._exit(5)

    equal(run_limited(fine, {}), ("exited", 5), label="child that exits with 5")
    equal(run_limited(lambda: None, {}), ("exited", 0), label="child that returns normally")

    def boom():
        raise RuntimeError("child failure")

    equal(run_limited(boom, {}), ("exited", 70), label="child that raises")

    def open_many():
        try:
            for _ in range(200):
                os.open("/dev/null", os.O_RDONLY)
        except OSError as e:
            os._exit(7 if e.errno == errno.EMFILE else 8)
        os._exit(9)

    equal(run_limited(open_many, {resource.RLIMIT_NOFILE: (16, 16)}), ("exited", 7), label="open 200 files with a limit of 16")
    equal(run_limited(open_many, {}), ("exited", 9), label="open 200 files with the default limit")

    tmp = tempfile.mkdtemp(prefix="oscheck26-")
    path = os.path.join(tmp, "big")

    def write_big():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        try:
            for _ in range(5):  # the first write is cut short at 1000 bytes; the next fails
                os.write(fd, b"x" * 1000)
        except OSError as e:  # Python ignores SIGXFSZ, so the write fails with EFBIG
            os._exit(7 if e.errno == errno.EFBIG else 8)
        os._exit(9)

    try:
        equal(run_limited(write_big, {resource.RLIMIT_FSIZE: (1000, 1000)}), ("exited", 7), label="write 5000 bytes with a 1000-byte file size limit")
        if os.path.getsize(path) != 1000:
            fail(f"the file should hold the 1000 bytes allowed before the failure, but it holds {os.path.getsize(path)}")
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        os.rmdir(tmp)


@check("run_limited kills a CPU hog with SIGXCPU at its limit, and kills a sleeper after the timeout")
def test_limits_cpu(sub):
    run_limited = has(sub, "run_limited")

    def spin():
        # Burn CPU for up to 5 CPU-seconds. With no limit this ends normally with exit 9.
        while time.process_time() < 5:
            pass
        os._exit(9)

    got = run_limited(spin, {resource.RLIMIT_CPU: (1, 3)})
    equal(got, ("signaled", signal.SIGXCPU), label="busy loop with RLIMIT_CPU soft=1 second")

    def sleeper():
        time.sleep(30)
        os._exit(9)

    t0 = time.monotonic()
    got = run_limited(sleeper, {}, timeout=0.3)
    elapsed = time.monotonic() - t0
    equal(got, ("signaled", signal.SIGKILL), label="sleeping child with timeout=0.3")
    if elapsed > 5:
        fail(f"run_limited took {elapsed:.1f} seconds with timeout=0.3; it must kill the child and return promptly")
    try:
        pid, _ = os.waitpid(-1, os.WNOHANG)
    except ChildProcessError:
        return
    fail(f"a child process was left unreaped (os.waitpid returned {pid}); reap every child")
