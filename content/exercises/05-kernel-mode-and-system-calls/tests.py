"""Checks for the toy kernel and system call exercise."""

import os

from oscheck import check, equal, fail, has

# Real Linux values, written out so the checks do not depend on the reader's constants.
SYS_WRITE, SYS_GETPID, SYS_EXIT = 1, 39, 60
EBADF, EFAULT, EINVAL, ENOSYS = 9, 14, 22, 38


def new_kernel(sub, text=b""):
    kernel = has(sub, "Kernel")(pid=42, user_mem_size=32)
    kernel.user_mem[0:len(text)] = text
    return kernel


@check("errno_name turns a negative result into an error name")
def test_errno_name(sub):
    errno_name = has(sub, "errno_name")
    equal(errno_name(-9), "EBADF", label="errno_name(-9)")
    equal(errno_name(-14), "EFAULT", label="errno_name(-14)")
    equal(errno_name(-22), "EINVAL", label="errno_name(-22)")
    equal(errno_name(-38), "ENOSYS", label="errno_name(-38)")
    equal(errno_name(-99), "UNKNOWN", label="errno_name(-99)")
    equal(errno_name(0), None, label="errno_name(0)")
    equal(errno_name(5), None, label="errno_name(5)")


@check("sys_write copies bytes from user memory to the file")
def test_write_ok(sub):
    sys_write = has(sub, "sys_write")
    kernel = new_kernel(sub, b"hello world")
    equal(sys_write(kernel, 1, 0, 5), 5, label="sys_write(fd 1, addr 0, count 5)")
    equal(bytes(kernel.files[1]), b"hello", label="contents of fd 1")
    equal(sys_write(kernel, 1, 6, 5), 5, label="second write, addr 6, count 5")
    equal(bytes(kernel.files[1]), b"helloworld", label="fd 1 after two writes (writes append)")
    equal(sys_write(kernel, 2, 0, 2), 2, label="write to fd 2")
    equal(bytes(kernel.files[2]), b"he", label="contents of fd 2")
    equal(sys_write(kernel, 1, 0, 0), 0, label="a write of 0 bytes")
    equal(sys_write(kernel, 1, 32, 0), 0, label="a 0-byte write at the very end of memory is valid")
    equal(sys_write(kernel, 1, 27, 5), 5, label="a write that ends exactly at the end of memory")


@check("sys_write reports EBADF, EINVAL, and EFAULT as negative errno values")
def test_write_errors(sub):
    sys_write = has(sub, "sys_write")
    kernel = new_kernel(sub, b"hello")
    equal(sys_write(kernel, 7, 0, 5), -EBADF, label="unknown fd 7")
    equal(sys_write(kernel, 0, 0, 5), -EBADF, label="fd 0 is not open for writing")
    equal(sys_write(kernel, 1, 0, -1), -EINVAL, label="negative count")
    equal(sys_write(kernel, 1, 30, 5), -EFAULT, label="addr 30 + 5 bytes passes the end of 32 bytes")
    equal(sys_write(kernel, 1, -1, 2), -EFAULT, label="negative address")
    equal(sys_write(kernel, 1, 0, 33), -EFAULT, label="count larger than all of memory")
    equal(sys_write(kernel, 7, 0, -1), -EBADF, label="bad fd wins over bad count (check order)")
    equal(sys_write(kernel, 1, 99, -1), -EINVAL, label="bad count wins over bad address (check order)")
    equal(bytes(kernel.files[1]), b"", label="failed writes must not change fd 1")


@check("sys_getpid returns the pid, and sys_exit stores the low 8 bits of the status")
def test_exit(sub):
    sys_exit = has(sub, "sys_exit")
    kernel = new_kernel(sub)
    equal(has(sub, "sys_getpid")(kernel), 42, label="sys_getpid")
    equal(kernel.exited, False, label="exited before sys_exit")
    sys_exit(kernel, 3)
    equal(kernel.exited, True, label="exited after sys_exit")
    equal(kernel.exit_status, 3, label="exit_status")
    other = new_kernel(sub)
    sys_exit(other, 300)
    equal(other.exit_status, 44, label="exit_status after sys_exit(300)")  # 300 mod 256


@check("Kernel.syscall dispatches by number through the table")
def test_dispatch(sub):
    kernel = new_kernel(sub, b"hi")
    equal(kernel.syscall(SYS_GETPID), 42, label="syscall(39)")
    equal(kernel.syscall(SYS_WRITE, 1, 0, 2), 2, label="syscall(1, 1, 0, 2)")
    equal(bytes(kernel.files[1]), b"hi", label="fd 1 after the write")
    equal(kernel.syscall(SYS_EXIT, 7), 0, label="syscall(60, 7)")
    equal((kernel.exited, kernel.exit_status), (True, 7), label="exit state")


@check("Kernel.syscall returns -ENOSYS and -EINVAL for bad requests")
def test_bad_requests(sub):
    kernel = new_kernel(sub, b"hi")
    equal(kernel.syscall(999), -ENOSYS, label="unknown system call 999")
    equal(kernel.syscall(-1), -ENOSYS, label="system call -1")
    equal(kernel.syscall(SYS_GETPID, 1), -EINVAL, label="getpid given one argument")
    equal(kernel.syscall(SYS_WRITE, 1, 0), -EINVAL, label="write given two arguments")
    equal(kernel.syscall(SYS_WRITE, 9, 0, 2), -EBADF, label="errors from the handler pass through")
    equal(bytes(kernel.files[1]), b"", label="no bad request may write anything")
    equal(kernel.exited, False, label="no bad request may exit the process")


@check("the trap switches to kernel mode, and back to user mode afterwards")
def test_modes(sub):
    kernel = new_kernel(sub)
    seen = []

    def spy(k):
        seen.append(k.mode)
        return 123

    def crash(k):
        seen.append(k.mode)
        raise RuntimeError("handler bug")

    kernel.table[500] = (spy, 0)
    kernel.table[501] = (crash, 0)
    equal(kernel.mode, "user", label="mode before the trap")
    equal(kernel.syscall(500), 123, label="result of the handler")
    equal(seen, ["kernel"], label="mode seen inside the handler")
    equal(kernel.mode, "user", label="mode after the trap")
    try:
        kernel.syscall(501)
    except RuntimeError:
        pass
    else:
        fail("an exception inside a handler should not be swallowed by syscall()")
    equal(kernel.mode, "user", label="mode after a handler that raised (use try/finally)")
    kernel.syscall(999)
    equal(kernel.mode, "user", label="mode after an unknown system call")


@check("syscall_count counts every trap, including failed ones")
def test_count(sub):
    kernel = new_kernel(sub, b"hi")
    equal(kernel.syscall_count, 0, label="count at the start")
    kernel.syscall(SYS_GETPID)
    kernel.syscall(999)
    kernel.syscall(SYS_WRITE, 5, 0, 1)
    kernel.syscall(SYS_GETPID, 1, 2)
    equal(kernel.syscall_count, 4, label="count after 4 traps (1 ok, 3 failed)")


@check("real_write_roundtrip writes to and reads from a pipe it creates")
def test_real_pipe(sub):
    real_write_roundtrip = has(sub, "real_write_roundtrip")
    before = set(os.listdir("/proc/self/fd")) if os.path.isdir("/proc/self/fd") else None
    written, pid, data = real_write_roundtrip(b"real bytes")
    equal(written, 10, label="bytes written")
    equal(pid, os.getpid(), label="pid")
    equal(data, b"real bytes", label="data read back")
    written, pid, data = real_write_roundtrip(b"")
    equal((written, data), (0, b""), label="an empty message")
    if before is not None:
        after = set(os.listdir("/proc/self/fd"))
        extra = after - before
        # listdir itself opens one descriptor, which may differ between the two calls.
        if len(extra) > 1:
            fail(f"real_write_roundtrip left {len(extra)} file descriptors open; close both ends of the pipe")


@check("real_errno_name provokes a real EBADF")
def test_real_errno(sub):
    real_errno_name = has(sub, "real_errno_name")
    equal(real_errno_name(), "EBADF", label="real_errno_name()")
