"""A toy kernel: user code traps into it with a system call number, and it answers with a result or -errno.

System call numbers and error numbers are the real Linux x86-64 values.
"""

import errno
import os

SYS_WRITE = 1
SYS_GETPID = 39
SYS_EXIT = 60

EBADF = 9     # bad file descriptor
EFAULT = 14   # bad address
EINVAL = 22   # invalid argument
ENOSYS = 38   # no such system call

ERRNO_NAMES = {EBADF: "EBADF", EFAULT: "EFAULT", EINVAL: "EINVAL", ENOSYS: "ENOSYS"}


def errno_name(result):
    """Name the error in a system call result.

    errno_name(-9) -> "EBADF"; errno_name(5) -> None (a non-negative result is not an error);
    errno_name(-99) -> "UNKNOWN".
    """
    raise NotImplementedError


def sys_getpid(kernel):
    """Return the process id of the calling process."""
    raise NotImplementedError


def sys_exit(kernel, status):
    """End the process. Store the low 8 bits of status, as a real exit status is one byte."""
    raise NotImplementedError


def sys_write(kernel, fd, addr, count):
    """Copy `count` bytes from user memory at `addr` to the file open as `fd`.

    Return the number of bytes written, or a negative error number:
      -EBADF  if fd is not an open file (a key of kernel.files)
      -EINVAL if count is negative
      -EFAULT if addr .. addr + count is not inside kernel.user_mem
    Check in that order.
    """
    raise NotImplementedError


class Kernel:
    """The kernel's state. __init__ is provided."""

    def __init__(self, pid=1234, user_mem_size=64):
        self.pid = pid
        self.user_mem = bytearray(user_mem_size)   # the user program's memory
        self.files = {1: bytearray(), 2: bytearray()}  # fd 1 = stdout, fd 2 = stderr
        self.mode = "user"                          # "user" or "kernel"
        self.exited = False
        self.exit_status = None
        self.syscall_count = 0
        # The system call table: number -> (handler, number of arguments).
        self.table = {
            SYS_WRITE: (sys_write, 3),
            SYS_GETPID: (sys_getpid, 0),
            SYS_EXIT: (sys_exit, 1),
        }

    def syscall(self, number, *args):
        """The trap handler: what runs when user code executes a system call.

        Count the trap, look `number` up in self.table, switch to kernel mode,
        run the handler as handler(self, *args), switch back to user mode, and
        return the handler's result. Return -ENOSYS for an unknown number and
        -EINVAL when len(args) does not match the table's argument count. In
        both of those cases the mode stays "user" and no handler runs.
        """
        raise NotImplementedError


def real_write_roundtrip(message):
    """Make two real system calls on a pipe you create, and read the data back.

    Create a pipe, os.write(message) into its write end, read the bytes back from
    its read end, close both ends. Return (bytes_written, os.getpid(), data_read).
    `message` is short (well under the 64 KiB pipe capacity).
    """
    raise NotImplementedError


def real_errno_name():
    """Provoke a real EBADF and return its name.

    Create a pipe, close both ends, then os.write to the closed write end.
    Catch the OSError and return errno.errorcode[e.errno] (which is "EBADF").
    """
    raise NotImplementedError


if __name__ == "__main__":
    kernel = Kernel(pid=1234)
    kernel.user_mem[0:5] = b"hello"
    print("write 5 bytes to fd 1 ->", kernel.syscall(SYS_WRITE, 1, 0, 5))
    print("what fd 1 now holds    ->", bytes(kernel.files[1]))
    print("getpid                 ->", kernel.syscall(SYS_GETPID))
    result = kernel.syscall(SYS_WRITE, 7, 0, 5)
    print("write to fd 7          ->", result, errno_name(result))
    result = kernel.syscall(SYS_WRITE, 1, 60, 10)
    print("write past user memory ->", result, errno_name(result))
    result = kernel.syscall(999)
    print("system call 999        ->", result, errno_name(result))
    print("exit(300)              ->", kernel.syscall(SYS_EXIT, 300), "status", kernel.exit_status)
    print("real pipe round trip   ->", real_write_roundtrip(b"real bytes"))
    print("real error             ->", real_errno_name())
