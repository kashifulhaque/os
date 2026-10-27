---
title: Kernel mode, user mode, and system calls
slug: 05-kernel-mode-and-system-calls
part: "Part 1 — What an operating system is"
summary: Learn how the CPU keeps programs out of the kernel, and how they ask it for help through traps, a system call table, and errno.
minutes: 55
gpu: false
objectives:
  - Explain user mode and kernel mode, and why the CPU needs both.
  - Trace a system call from the trap instruction to the return to user mode.
  - Dispatch system calls through a table, validating every argument the kernel receives.
  - Read a negative return value as an errno, and make real system calls from Python.
prereqs:
  - 04-what-an-operating-system-does
exercise: 05-kernel-mode-and-system-calls
---

# Kernel mode, user mode, and system calls

Lesson 04 ended with a worry. Every program runs on the same CPU as the operating system. If a program may run any instruction and touch any memory, it can turn off the timer, rewrite the scheduler, or read another program's passwords. The OS cannot keep order if the programs it manages can break it.

The fix is built into the hardware. The CPU runs in one of at least two *modes*. In *user mode*, a program runs with restrictions. In *kernel mode*, the OS runs with full power. Programs cannot change the mode on their own. When a program needs something only the kernel can do, such as writing to a file, it asks, and the kernel decides.

This lesson explains the two modes, the controlled doorway between them, and the numbered menu of services behind that door. Then you build a toy kernel with its own doorway, menu, and error codes.

## What you already know

- A timer interrupt takes the CPU from a program and gives it to the OS, whatever the program is doing.
- A context is the registers and program counter that the OS saves and restores.
- A CPU raises a fault when it cannot run an instruction, and your toy CPU raises `CPUError`.
- A `bytearray` models memory, and an address is an index into it.
- A function can return a negative number to signal failure, and an exception can signal it too.

## Two modes

The CPU has a *mode* bit, a piece of state that says how much power the running code has.

- **User mode** is for ordinary programs. The CPU refuses some instructions, the *privileged instructions*. These include talking directly to devices, changing the page tables, turning interrupts off, and switching the mode. A program that tries one gets a fault, and the kernel usually ends the program.
- **Kernel mode** is for the OS. Every instruction is allowed. Kernel code can reach every byte of memory and every device.

An analogy: a bank has a lobby and a vault. Customers use the lobby, where they can fill in forms and talk to tellers. Only staff can enter the vault. A customer who wants cash does not walk in and take it. They hand a slip to a teller, who checks the slip and the account, and then fetches the money.

The names differ between chips. On x86-64 the modes are called *rings*: ring 0 is kernel mode and ring 3 is user mode. ARM uses *exception levels*: EL1 for the kernel and EL0 for programs. The idea is the same.

```text
        +--------------------------------------------+
USER    |  your program    browser    shell    ...   |   restricted
MODE    +--------------------------------------------+
                   |  system call (trap)  ^  return
                   v                      |
        +--------------------------------------------+
KERNEL  |  system call table, scheduler, drivers,    |   full power
MODE    |  file systems, memory manager              |
        +--------------------------------------------+
                         hardware
```

> [!KEY]
> User code cannot do anything dangerous by itself, and the hardware enforces this. A request for a protected service goes through the kernel, which checks it first.

## Traps: the only doorway in

If programs cannot enter kernel mode, how do they ask for anything? The CPU provides one instruction that does it in a controlled way. Running it is a *trap*. On x86-64, the instruction is `syscall`. On 64-bit ARM, it is `svc`.

A trap does three things in one step, and then kernel code runs:

1. The CPU switches to kernel mode.
2. It saves the program counter of the user program, so it can come back.
3. It jumps to a fixed address, the kernel's *entry point*. The kernel chose that address at boot, and the user program cannot pick a different one. The kernel code at that address starts running.

The fixed entry point is the heart of the safety. The program can knock on the door, but it can never decide where in the kernel it lands. If it could, it could jump into the middle of a kernel routine after the security check.

When the kernel is done, it executes a special return instruction (`sysret` on x86-64, `eret` on ARM). That instruction restores the program counter, switches back to user mode, and the program continues after the trap, as though a function had returned.

There are three reasons the CPU enters the kernel, and all three use the same trick of switching mode and jumping to a fixed place:

| Kind | Cause | Example |
|---|---|---|
| System call | The program asks on purpose. | Writing to a file. |
| Exception, or fault | The program does something illegal, or something the kernel must fix. | Dividing by zero, using an unmapped address. |
| Interrupt | Hardware needs attention. | The timer, a keystroke, a disk finishing. |

You have already seen the second and third. This lesson is about the first.

## The system call table

A kernel offers many services: write, read, open, close, create a process, get the process id, exit. To pick one, the program puts a number in a register before it traps. That number is the *system call number*. The kernel keeps an array called the *system call table*, and the number is the index into it. Each entry holds the address of the function that performs that service.

On Linux x86-64 the convention is:

- The system call number goes in register `rax`.
- Up to six arguments go in `rdi`, `rsi`, `rdx`, `r10`, `r8`, and `r9`.
- The result comes back in `rax`.

Real Linux x86-64 numbers include 0 for `read`, 1 for `write`, 2 for `open`, 3 for `close`, 39 for `getpid`, and 60 for `exit`. There are more than 300 in total. Other chips use different numbers, so a program built for one chip cannot run on another without changes. The `write` call takes three arguments: a *file descriptor* (a small number that names an open file), the address of the bytes in the caller's memory, and how many bytes.

```text
user program:                          kernel:

 rax = 1        (write)
 rdi = 1        (stdout)
 rsi = 0x7ffd.. (address of "hi\n")     entry point
 rdx = 3        (3 bytes)                  |
 syscall  ------ trap ------------------->  look up table[rax]
                                            run sys_write(1, 0x7ffd.., 3)
 rax = 3  <----- return to user mode ------ return 3
```

You rarely write `syscall` yourself. The C library has a wrapper named `write` that loads the registers and traps. Python's `os.write` calls that wrapper.

## Never trust the caller

Anything a user program hands the kernel could be wrong or hostile. A well-built kernel checks every argument before it acts. For `write`, the kernel asks three questions:

1. Is the file descriptor open? If not, fail with `EBADF`.
2. Is the byte count sensible? A negative count is `EINVAL`.
3. Is the whole range of addresses inside memory that belongs to the caller? If not, fail with `EFAULT`.

The last check matters most. If a program passes the address of kernel memory, a kernel that copies from it would hand the program a copy of its own secrets. Linux copies user memory through special routines (`copy_from_user` and `copy_to_user`) that check the address and survive a bad one.

Here is a worked example with a 64-byte user memory. The program stored `hello` at address 0 and calls `write(fd=1, addr=0, count=5)`.

| Call | Check that fails | Result |
|---|---|---|
| `write(1, 0, 5)` | none | 5, and fd 1 holds `hello` |
| `write(7, 0, 5)` | fd 7 is not open | -9 (`EBADF`) |
| `write(1, 0, -1)` | count is negative | -22 (`EINVAL`) |
| `write(1, 60, 10)` | 60 + 10 = 70 is past the end of 64 bytes | -14 (`EFAULT`) |
| `write(1, 60, 4)` | 60 + 4 = 64 is exactly the end | 4 |

The last row is the boundary case. A range that ends at exactly the end of memory is valid, because the addresses used are 60, 61, 62, and 63.

## Return values and errno

A system call has one return slot for its result, and it must carry both success and failure. The Linux kernel's convention is simple: a non-negative value is a success, and a small negative number is `-errno`, an *error number*. A write that fails because the descriptor is bad returns -9.

The C library then does a little more. It sees the negative number, stores its positive version in a global variable named `errno`, and returns -1 to the caller. Python goes a step further. It raises an `OSError` and puts the number in `exc.errno`. The same event is seen three ways: `-9` in the kernel, `-1` plus `errno == 9` in C, and an `OSError` in Python.

Some common values on Linux:

| Number | Name | Meaning |
|---|---|---|
| 1 | `EPERM` | Operation not permitted |
| 2 | `ENOENT` | No such file or directory |
| 9 | `EBADF` | Bad file descriptor |
| 14 | `EFAULT` | Bad address |
| 22 | `EINVAL` | Invalid argument |
| 38 | `ENOSYS` | Function not implemented |

`ENOSYS` is what a kernel returns for a system call number that is not in its table. A different system call's number means a different service, so an unknown number must never run anything.

## A trap in the toy kernel

Your toy `Kernel` keeps a `table` that maps a number to a pair: the handler function and how many arguments it takes. Its `syscall(number, *args)` method is the trap handler. Its steps match the real thing.

```python
def syscall(self, number, *args):
    # count the trap
    # look number up in self.table: unknown -> -ENOSYS
    # wrong number of arguments -> -EINVAL
    # self.mode = "kernel"
    # try: run the handler as handler(self, *args)
    # finally: self.mode = "user"
    ...
```

The `try` and `finally` matter. A real kernel bug that crashes mid-call must not leave the CPU in kernel mode and hand a program the keys. Python's `finally` runs even when the handler raises, so the mode always returns to `"user"`.

The three handlers take the kernel as their first argument, because they work on kernel state. `sys_getpid` returns the pid. `sys_exit` records that the process ended, with the low 8 bits of the status: a real process exit status is one byte, so `exit(300)` is reported as 44. `sys_write` does the three checks above and then copies bytes.

## Try it on your own machine

The first two use `strace`, a Linux tool that prints every system call a program makes. Install it from your package manager if it is missing. On macOS, `sudo dtruss` does a similar job.

1. Run `strace -e trace=write echo hello`. Look for a line like `write(1, "hello\n", 6) = 6`. That is the call, its three arguments, and the return value.
2. Run `strace -c ls > /dev/null`. Look at the summary table: a count of each system call that `ls` made. Even a small tool makes dozens.
3. Run `python3 -c "import os; os.write(99, b'x')"`. Look for `OSError: [Errno 9] Bad file descriptor`. That is the real `EBADF` coming back through Python. Then run `python3 -c "import errno; print(errno.errorcode[9], errno.errorcode[14])"` to map numbers to names.
4. Run `man 2 write`. Look at the `RETURN VALUE` and `ERRORS` sections: the same list of failures as in the table above, written by the kernel developers. `man 2 syscalls` lists every call.
5. Run `python3 -c "import os; print(os.getpid(), os.getppid())"` twice. Look for a first number that changes on each run, because each run is a separate process with its own id, and a second number that stays the same, the id of your shell that started it.

## Build it step by step

Open the starter. The constants, `Kernel.__init__`, and the `__main__` demo are given. You write the functions below in this order.

1. **`errno_name(result)`.** Return `None` for a result of 0 or more. For a negative result, return the name for its positive value from `ERRNO_NAMES`, or `"UNKNOWN"` if it is not in there. The common mistake is looking up the negative number.
2. **`sys_getpid(kernel)` and `sys_exit(kernel, status)`.** One returns `kernel.pid`. The other sets `kernel.exited` to `True`, stores `status & 0xFF` in `kernel.exit_status`, and returns 0.
3. **`sys_write(kernel, fd, addr, count)`.** Check in the order `EBADF`, `EINVAL`, `EFAULT`, and return a negative number on a failure. A failed call must change nothing. Then append `bytes(kernel.user_mem[addr:addr + count])` to `kernel.files[fd]` and return `count`. The common mistake is checking only `addr + count <= len(...)` and forgetting that a negative `addr` is also out of range.
4. **`Kernel.syscall(number, *args)`.** Increment `syscall_count` first, on every trap. Look up the table entry, return `-ENOSYS` when it is missing, and `-EINVAL` when `len(args)` differs from the entry's argument count. Switch `self.mode` to `"kernel"`, call the handler with `self` and the arguments inside `try`, and set the mode back to `"user"` in `finally`.
5. **`real_write_roundtrip(message)`.** This one calls the real kernel. Create a pipe with `os.pipe()`. It returns two descriptors: one to read, one to write. Write `message` into the write end with `os.write`, and read it back from the read end with `os.read`. Close both descriptors, even if something goes wrong. Return `(bytes_written, os.getpid(), data)`. Never print to stdout in this exercise. The harness uses it to talk to the app.
6. **`real_errno_name()`.** Make a pipe, close both ends, and then try `os.write` to the closed write end. Catch the `OSError` and return `errno.errorcode[exc.errno]`.

## Where this breaks

- **Traps cost time.** A system call is far more expensive than a function call. It costs from around a hundred nanoseconds to over a microsecond, depending on the chip and on the defences the kernel applies against attacks such as Meltdown. That is why programs batch their work into large reads and writes rather than one byte at a time.
- **Some calls avoid the trap.** Reading the clock is so common that Linux maps a small piece of kernel code and data into every program, called the *vDSO*, so `clock_gettime` can run in user mode without a trap.
- **Checking then using is risky.** A kernel that checks a user pointer and then uses it must take care that another thread cannot change the memory between the check and the use. This kind of bug is called a *time-of-check to time-of-use* race, and real kernels have had it.
- **A wrong check is a security hole.** Every unchecked number in a system call is a way for a program to attack the kernel. Much of kernel security work is about argument checks.
- **Your toy has no hardware behind it.** Your `mode` is a string that the Python code changes politely. On a real CPU, the mode is a bit that no program can set, and a privileged instruction in user mode makes the hardware fault.

## Further reading

- [Operating Systems: Three Easy Pieces, Chapter 6: Mechanism: Limited Direct Execution](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf) explains user mode, kernel mode, traps, and trap tables.
- [syscalls(2) man page](https://man7.org/linux/man-pages/man2/syscalls.2.html) lists the Linux system calls and how they are invoked.
- [write(2) man page](https://man7.org/linux/man-pages/man2/write.2.html) documents the arguments, return value, and every error of `write`.
- [errno(3) man page](https://man7.org/linux/man-pages/man3/errno.3.html) lists the error numbers and their names.
- [strace(1) man page](https://man7.org/linux/man-pages/man1/strace.1.html) shows how to watch a program's system calls.
- [MIT 6.1810 (xv6) course page](https://pdos.csail.mit.edu/6.1810/) links lectures and a small teaching kernel with chapters on system calls and traps.

## The exercise

You build a toy kernel and also touch the real one. The toy has a system call table with three entries, `write`, `getpid`, and `exit`, numbered 1, 39, and 60 as on Linux x86-64. You write `errno_name`, the handlers `sys_getpid`, `sys_exit`, and `sys_write`, and the trap handler `Kernel.syscall`. The handlers check their arguments and return a negative errno on failure. `syscall` switches to kernel mode and back, counts traps, and rejects unknown numbers and wrong argument counts.

Then you write two functions that make real system calls: `real_write_roundtrip(message)` writes to a pipe it creates and reads the bytes back, and `real_errno_name()` provokes a genuine `EBADF` and returns its name. The ten checks cover errno names, `getpid` with `exit`, writes that succeed, each error code and the order of checks, dispatch by number, unknown and malformed requests, mode switching (including a handler that raises), trap counting, and the two real calls. Click Run to watch the demo kernel serve a write, reject three bad requests, and exit.
