# Curriculum

Operating systems from zero. Twenty-six lessons in eight parts take a reader who
has never studied how a computer works to the point where they can explain, and
build small working models of, every major piece of a modern operating system:
processes, scheduling, virtual memory, concurrency, storage, file systems, and
isolation.

Every lesson ends in an exercise written in Python. Some exercises are
simulators: a scheduler, a page table, a memory allocator, a file system laid
out on a `bytearray` disk. Others call the real Linux kernel through Python's
`os` module: `fork`, `exec`, `wait`, `pipe`, `dup2`, signals, and file
descriptors. Python is the only language the reader writes, and Part 0 teaches
the Python the course needs.

The column "Exercise" sketches what the reader builds. Exact function names are
chosen by the lesson author and must match between the lesson's
`## Build it step by step`, the starter, and the checks.

## Part 0 — Getting started

| # | Slug | Title | Exercise |
|---|---|---|---|
| 01 | `01-python-you-need` | The Python you need for this course | Small functions over ints, lists, dicts, bytes, and classes: `count_words`, a tiny `Stack` class, `to_binary_string`, bytes slicing. Gentle, many early passes. |
| 02 | `02-how-a-computer-runs-a-program` | How a computer runs a program | A toy CPU emulator: registers, memory as a list, program counter, fetch-decode-execute over a ten-instruction ISA (`LOAD`, `ADD`, `JMP`, `JZ`, `HALT`…). |
| 03 | `03-bits-bytes-and-memory` | Bits, bytes, and memory | Binary and hex conversion, bit masks and shifts (`get_bits`, `set_bit`), two's complement, little vs big endian packing into `bytes`. |

## Part 1 — What an operating system is

| # | Slug | Title | Exercise |
|---|---|---|---|
| 04 | `04-what-an-operating-system-does` | What an operating system does | Extend a toy machine with an OS idea: a `Machine` that runs two tiny programs by time-slicing with a timer interrupt, saving and restoring registers. |
| 05 | `05-kernel-mode-and-system-calls` | Kernel mode, user mode, and system calls | A toy kernel with a syscall table: user code traps with a number and arguments, the kernel validates them, dispatches `write`, `getpid`, `exit`, and returns error codes like `-EBADF`. Plus a function that uses real `os.write`/`os.getpid` on a pipe. |

## Part 2 — Processes

| # | Slug | Title | Exercise |
|---|---|---|---|
| 06 | `06-processes` | Processes and the process table | A `ProcessTable` with PCBs and the state machine (new, ready, running, blocked, zombie, terminated); legal and illegal transitions; parent/child links; reaping. |
| 07 | `07-fork-exec-and-wait` | Creating processes: fork, exec, and wait | Real `os.fork`, `os.execvp`, `os.waitpid`: `run_and_wait(argv)` returning an exit status, `decode_status`, `fork_many(n)` collecting children's results through pipes. |
| 08 | `08-pipes-and-a-tiny-shell` | Pipes, file descriptors, and a tiny shell | Parse a command line with `|`, `<`, `>`; run a pipeline with `os.pipe` and `os.dup2`, capturing the final output. |
| 09 | `09-signals` | Signals | Install handlers with `signal.signal`, send signals with `os.kill` to a child, decode "killed by signal" statuses, implement `run_with_timeout` using `SIGALRM` or `SIGKILL`. |

## Part 3 — CPU scheduling

| # | Slug | Title | Exercise |
|---|---|---|---|
| 10 | `10-scheduling-basics` | Scheduling basics: FCFS, SJF, and SRTF | Simulate the three policies on job lists and compute turnaround, waiting, and response time; return Gantt timelines. |
| 11 | `11-round-robin-and-mlfq` | Round robin and the multi-level feedback queue | Round robin with a time quantum and context switch cost; an MLFQ with priority boost and allotments, I/O-bound jobs. |
| 12 | `12-proportional-share-scheduling` | Proportional share: lottery, stride, and CFS | Lottery with a seeded RNG, stride scheduling, and a CFS-style virtual runtime scheduler with weights from nice values. |

## Part 4 — Memory

| # | Slug | Title | Exercise |
|---|---|---|---|
| 13 | `13-address-spaces` | Address spaces, base and bounds, and segmentation | Translate virtual to physical addresses with base and bounds, then with segments (code, heap, stack growing down), raising `SegmentationFault`. |
| 14 | `14-paging` | Paging | Split addresses into page number and offset, translate through a linear page table with valid/protection bits, then a two-level page table; count memory used by each. |
| 15 | `15-tlbs` | Translation lookaside buffers | A TLB cache with LRU replacement in front of a page table; hit rate on array-walk access patterns; ASIDs and flushing on context switch. |
| 16 | `16-page-replacement` | Swapping and page replacement | FIFO, LRU, Clock, and OPT on reference strings; count faults; reproduce Belady's anomaly. |
| 17 | `17-heap-allocation` | Heap allocation: malloc and free | A free-list allocator over a fixed arena: first fit, best fit, splitting, coalescing on free, fragmentation stats. |

## Part 5 — Concurrency

| # | Slug | Title | Exercise |
|---|---|---|---|
| 18 | `18-threads-and-race-conditions` | Threads and race conditions | An interleaving simulator: threads as lists of atomic steps (`load`, `add`, `store`) on shared memory; enumerate all interleavings of `counter += 1` and find the lost update; then real `threading` with a `Lock`. |
| 19 | `19-locks` | Locks | Simulated atomic test-and-set and compare-and-swap; a spin lock and a ticket lock on the interleaving simulator; Peterson's algorithm and a check of mutual exclusion over all schedules. |
| 20 | `20-condition-variables-and-semaphores` | Condition variables and semaphores | A bounded buffer with `threading.Condition`; a semaphore built from a condition variable; reader-writer lock; producer/consumer checks with real threads. |
| 21 | `21-deadlock` | Deadlock | Wait-for graph cycle detection, the Banker's algorithm safety check, and lock ordering to fix a dining philosophers program. |

## Part 6 — Storage and file systems

| # | Slug | Title | Exercise |
|---|---|---|---|
| 22 | `22-disks-and-io` | Disks, SSDs, and I/O | Disk access time from seek, rotation, and transfer; disk schedulers FCFS, SSTF, SCAN, and C-LOOK with total head movement. |
| 23 | `23-files-and-directories` | Files, directories, and the file API | Real `os.open`/`os.read`/`os.write`/`os.lseek`, `os.stat`, hard and symbolic links, a `tree`-style directory walk, and normalising paths with `.` and `..`. |
| 24 | `24-building-a-file-system` | Building a file system | A very simple file system on a `bytearray` disk: superblock, inode and data bitmaps, inodes with direct pointers, directories, `mkfs`, `create`, `write`, `read`, `lookup` by path. |
| 25 | `25-crash-consistency-and-journaling` | Crash consistency and journaling | A write-ahead log: begin, log blocks, commit, checkpoint; simulate crashes at every point and recover correctly by replaying committed transactions. |

## Part 7 — Isolation

| # | Slug | Title | Exercise |
|---|---|---|---|
| 26 | `26-protection-virtual-machines-and-containers` | Protection, virtual machines, and containers | Unix permission checks from mode bits, owner, and group (including root and the sticky bit); a trap-and-emulate toy hypervisor; resource limits with `resource.setrlimit` in a child. |
