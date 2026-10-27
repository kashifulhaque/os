---
title: Protection, virtual machines, and containers
slug: 26-protection-virtual-machines-and-containers
part: "Part 7 — Isolation"
summary: Decide file access from mode bits, build a trap-and-emulate hypervisor, limit a real process with setrlimit, and see how containers isolate.
minutes: 70
gpu: false
objectives:
  - Decide whether a user may read, write, or execute a file from its mode bits, owner, and group, including the root and sticky-bit rules.
  - Explain how trap-and-emulate lets a hypervisor run a guest operating system on a deprivileged CPU.
  - Limit a real child process with setrlimit and tell from its wait status how the limit stopped it.
  - Say what namespaces and cgroups each isolate, and how a container differs from a virtual machine.
prereqs:
  - 05-kernel-mode-and-system-calls
  - 09-signals
  - 23-files-and-directories
exercise: 26-protection-virtual-machines-and-containers
---

# Protection, virtual machines, and containers

A computer runs programs written by many people, and you trust few of them
completely. A browser tab runs code from a stranger. A cloud server runs
programs for thousands of customers at once. The operating system's last big
job is *isolation*: letting programs share one machine without reading each
other's secrets, wrecking each other's data, or using up all the resources.

Kernel mode and address spaces already keep programs apart. In this lesson, you
add three more layers. *Protection* decides who may touch which file.
*Virtualisation* gives each customer a whole pretend computer. *Containers* give
each group of processes its own view of the system. You build a permission
checker, a toy hypervisor, and a runner that limits a real child process. Then
you finish the course.

## What you already know

- The CPU has a privileged mode for the kernel and an unprivileged mode for programs. A privileged instruction in user mode causes a trap.
- A process ends either by exiting with a code or by being killed by a signal, and `waitpid` tells you which.
- A file has an owner, a group, and mode bits, and a directory is a file of names.
- `fork` makes a child that inherits the parent's open files and settings.
- A system call is how a program asks the kernel for something.

## Who may do what: Unix permissions

The kernel has to answer one question every time a process opens a file: *is
this process allowed?* Unix keeps the answer small. Each file has three facts:

- an *owner*, a user id (uid),
- a *group*, a group id (gid),
- a *mode*, a number whose bits say who can do what.

The mode has nine permission bits in three groups of three. Each group has *read*
(`r`, value 4), *write* (`w`, value 2), and *execute* (`x`, value 1). The groups
apply to the owner, to the group, and to everyone else (*other*).

```text
mode 0o640 in binary:   1 1 0   1 0 0   0 0 0
                        r w -   r - -   - - -
                        |       |       |
                        owner   group   other
                        6       4       0
```

`ls -l` shows this as `rw-r-----`. In octal, the owner digit is 6 (4 + 2, read
and write), the group digit is 4 (read), and the other digit is 0.

### The check

A process has a uid and a set of gids (its primary group plus any
supplementary groups). When it asks for access, the kernel picks *one* class and
looks only at that class:

1. If the process's uid equals the file's owner, use the **owner** bits.
2. Otherwise, if the file's group is among the process's groups, use the **group** bits.
3. Otherwise, use the **other** bits.

All the wanted permissions must be present in the chosen class.

The order has a consequence that surprises people. Take a file with mode
`0o070`: owner `---`, group `rwx`, other `---`. A group member can do everything.
The *owner*, even though also in the group, gets nothing, because the owner
class matches first and has no bits.

Take `/srv/report`, with mode `0o640`, owner uid 1000, and group 100. Uid 1000 uses the owner bits `rw-` and can read and write. Uid 2000 in group 100 uses the group bits `r--` and can read only. Uid 3000 in no relevant group uses the other bits `---` and gets nothing.

### Directories mean something different

Permissions apply to directories too, with different meanings:

- `r` lets you list the names in the directory.
- `x` lets you *search* it, which means open something by name inside it. Without `x` you cannot reach files below a directory, even ones that are open to you.
- `w` lets you create, rename, and delete names in the directory.

That last point surprises people. **Deleting a file needs write and execute on its
directory, not any permission on the file itself.** A file's mode does not
protect it from being unlinked. Think back to lesson 23: deleting removes a
*name* from a directory, and the directory is what changes.

### The sticky bit

Under that rule, everyone who can write to `/tmp` could delete everyone else's
files. The *sticky bit* fixes this. On a directory with the sticky bit (mode
`0o1000`), you may delete or rename a file only if you own the file, own the
directory, or are root. That is why `ls -ld /tmp` shows `drwxrwxrwt`: the final
`t` is the sticky bit.

### Root, and the special bits

User id 0, *root*, bypasses permission checks. It can read and write any file.
There is one exception for execute: even root cannot run a file that has no `x`
bit for anyone. Root can always search a directory.

Linux splits root's power into *capabilities*, such as `CAP_DAC_OVERRIDE` (skip file permission checks), so a process can hold a few instead of all.

Two more mode bits matter. A file with *setuid* (`0o4000`) runs with its
*owner's* uid, not the caller's. That is how `passwd` lets an ordinary user
change one line of a root-owned file. *Setgid* (`0o2000`) does the same for the
group. `ls -l` shows them as `s` in place of `x`, and as capital `S` when the
`x` bit is off. A setuid program is a deliberate hole in the wall, so a bug in
one is a security bug.

> [!KEY]
> A permission check picks one class, owner, group, or other, and tests the wanted bits against only that class. Root bypasses it, except that execute still needs an x bit somewhere.

## Virtual machines

Permissions isolate users inside one operating system. A *virtual machine* (VM)
isolates whole operating systems. A program called a *hypervisor*, or *virtual
machine monitor* (VMM), runs several *guest* operating systems on one physical
machine. Each guest believes it has the entire computer to itself: its own CPU,
memory, and devices. This is how a cloud provider rents you a "server" that is
one slice of a shared machine.

The guest operating system expects to run in kernel mode, executing privileged
instructions such as "disable interrupts" and "set the page table base." But the
hypervisor must stay in control. If a guest could really disable interrupts,
it could stop the machine from ever switching away from it.

### Trap and emulate

The classic solution uses a mechanism you already know. Run the guest, including
its kernel, in *user mode*. Ordinary instructions (adding, moving, jumping) run at
full speed on the real CPU. When the guest kernel runs a privileged instruction,
the CPU *traps* to the hypervisor, as it would for any user program. The
hypervisor looks at what the guest wanted and *emulates* it: it changes a
record of the guest's *virtual* state instead of the real hardware, then
resumes the guest after that instruction.

```text
          guest program                        hypervisor (VMM)
  +-----------------------------+      +---------------------------------+
  | mov a, 42      -- runs at full speed on the CPU                       |
  | cli            ----- TRAP ------>  | virtual interrupt flag of THIS  |
  |                                    | guest := off. Real flag untouched|
  |                <---- resume ------ |                                 |
  | out port1, a   ----- TRAP ------>  | check that this guest owns      |
  |                                    | port 1, then log the value in   |
  |                                    | this guest's console            |
  +-----------------------------+      +---------------------------------+
```

Each guest has its own saved copy of everything privileged: a virtual interrupt
flag, a virtual page-table base register, and virtual devices. When a guest
runs `cli`, only its flag changes, so guest A's `cli` never stops guest B.

Most instructions run directly, so a well-behaved guest runs near native speed. Each privileged instruction costs a trap of hundreds or thousands of cycles.

The hypervisor can also *refuse*. If a guest tries `out` on a port it does not
own, the monitor can halt that guest and record why. That is isolation: the guest
cannot reach a device it was not given.

### The x86 problem and hardware help

Trap and emulate works only if every instruction that touches privileged state traps in user mode. Popek and Goldberg stated this condition in 1974. The classic 32-bit x86 broke it: instructions such as `POPF` silently did something different in user mode instead of trapping. Early x86 hypervisors rewrote guest code on the fly (*binary translation*). In 2005 and 2006, Intel and AMD added hardware support (VT-x and AMD-V): a guest kernel runs in its own kernel mode, and the CPU traps to the hypervisor only on certain events, called *VM exits*. *Nested page tables* translate guest addresses to real ones in hardware. *Paravirtualisation* instead modifies the guest to make explicit hypercalls.

> [!KEY]
> A hypervisor gives each guest virtual copies of the privileged state, and traps and emulates each privileged instruction against that copy. The guest cannot tell, and cannot affect any other guest.

## Resource limits

Isolation also means that one program cannot eat everything. A runaway loop
should not starve the other users, and a program that opens files in a loop
should not use every file handle on the machine.

The oldest tool is `setrlimit`. A process can have a *soft* limit and a *hard*
limit for each of many resources. The kernel enforces the soft limit. A process
may lower or raise its soft limit up to the hard limit. It may lower its hard limit
but, unless it is privileged, never raise it. The limits are inherited by
children, so a parent sets them before running untrusted code.

Here are the common ones, and how each one stops a process:

| Resource | Limits | What happens at the limit |
|---|---|---|
| `RLIMIT_CPU` | CPU seconds used | The kernel sends `SIGXCPU` at the soft limit, and `SIGKILL` at the hard limit |
| `RLIMIT_NOFILE` | Number of open file descriptors | `open` fails with `EMFILE` |
| `RLIMIT_FSIZE` | Largest file the process may write | The write is cut short at the limit. The next one gets `SIGXFSZ`, or `EFBIG` if the signal is ignored |
| `RLIMIT_AS` | Size of the address space | Memory allocation fails |
| `RLIMIT_NPROC` | Number of processes for the user | `fork` fails with `EAGAIN` |

Python ignores `SIGXFSZ` when it starts, so a Python program sees an `OSError`
with `EFBIG` instead of dying. This is one place where Python's behaviour
differs from a C program's.

You apply limits in the child between `fork` and the work: call `resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))`, then run the code to restrain. The parent calls `waitpid` and reads the status. A process killed by `RLIMIT_CPU` shows as "killed by signal 24". One that hit the file limit and handled the error exits with the code its handler chose.

## Containers

A VM gives each tenant a whole computer, kernel included. That is strong
isolation at a cost: every guest boots its own kernel, uses its own memory for
it, and traps through the hypervisor.

A *container* takes the opposite approach. All containers on a machine *share
one kernel*. The kernel gives each group of processes its own *view* of the
system and a *limit* on its resources, so the group behaves as if it were alone.
Two Linux features do this.

### Namespaces: what a process can see

A *namespace* wraps a global resource so that processes inside see their own
private copy. Linux has several kinds:

| Namespace | What it isolates |
|---|---|
| `pid` | Process ids. The first process inside sees itself as pid 1, and sees no others |
| `mnt` | The mount table, so the container sees its own file system tree |
| `net` | Network interfaces, addresses, routing tables, and ports |
| `uts` | The host name |
| `ipc` | Shared memory and message queues |
| `user` | User and group ids. Uid 0 inside can map to an ordinary uid outside |
| `cgroup` | The view of the cgroup tree |

A process is in one namespace of each kind, and `fork` copies the memberships.
`unshare` and `clone` create new ones. The `user` namespace is what lets an
ordinary user make a "root" inside a container without any real power outside it.

### Cgroups: what a process can use

A *control group* (cgroup) is a node in a tree of process groups, with limits
and accounting attached. Where `setrlimit` limits one process and its children, a
cgroup limits a whole group together, and can limit things `setrlimit` cannot.
In cgroup version 2, the files live under `/sys/fs/cgroup`:

- `memory.max` sets a memory ceiling for the group. Past it, the kernel reclaims memory and, if that fails, kills a process in the group.
- `cpu.max` sets a CPU share, written as a quota and a period in microseconds. `50000 100000` means 50 ms of CPU in every 100 ms, half of one CPU.
- `pids.max` caps the number of processes, stopping a fork bomb.
- `io.max` caps disk bandwidth or operations per device.

You create a cgroup by making a directory and put a process in it by writing
its pid to `cgroup.procs`.

A container runtime such as Docker or Podman adds a separate root file system, `seccomp` filters that block dangerous system calls, and dropped capabilities. "Container" is not one kernel feature. It is a recipe of these pieces.

### The trade-off

| | Virtual machine | Container |
|---|---|---|
| Kernel | One per guest | Shared with the host |
| Start time | Seconds | Milliseconds |
| Isolation | A narrow hypervisor interface | The whole system-call interface of the host kernel |

A bug in the shared kernel can let a container escape. Services that run hostile code often put containers *inside* lightweight VMs.

## Try it on your own machine

1. See permissions, setuid, and the sticky bit (Linux or macOS):

   ```bash
   ls -l /etc/passwd /usr/bin/passwd
   ls -ld /tmp
   id
   ```

   `passwd` shows `-rwsr-xr-x`, the `s` being setuid. `/tmp` shows `drwxrwxrwt`, the `t` being the sticky bit. `id` lists your uid and groups.

2. Read the mode as a number (Linux, GNU `stat`):

   ```bash
   stat -c '%a %A %U %G %n' /etc/passwd /tmp
   ```

   `%a` is the octal mode, such as `644` and `1777`.

3. Look at and change your resource limits (Linux or macOS, in the shell):

   ```bash
   ulimit -a
   (ulimit -n 16; ulimit -n)
   ```

   The first command lists the soft limits. The second lowers the limit inside a subshell and prints 16, and your own shell keeps its limit.

4. Create new namespaces without being root (Linux only):

   ```bash
   unshare --user --map-root-user --pid --fork --mount-proc bash
   id
   ps aux
   exit
   ```

   Inside, `id` reports uid 0, and `ps` shows only a couple of processes with `bash` as pid 1. You have root in a namespace and nothing outside. Some distributions turn off unprivileged user namespaces, so this may be refused.

5. List the namespaces of your shell and the cgroup tree (Linux only):

   ```bash
   ls -l /proc/self/ns
   cat /proc/self/cgroup
   cat /sys/fs/cgroup/cgroup.controllers
   ```

   Each entry in `/proc/self/ns` is a namespace identifier. Two processes in the same namespace show the same number. The controllers file lists what cgroup v2 can limit, such as `cpu memory io pids`.

## Build it step by step

The first two parts are pure Python. The third forks real child processes.

1. `describe_mode(mode)` renders the nine bits as `rwxr-xr-x`, with `s`/`S` for setuid and setgid and `t`/`T` for sticky. A lowercase letter means the `x` bit is also set.
2. `may_access(mode, owner_uid, owner_gid, uid, gids, want, is_dir=False)` checks root first: root passes everything except execute on a non-directory with no `x` bit. Everyone else gets one class, picked by owner, then group, then other. Test `bits & want == want`. Raise `ValueError` unless `want` is 1 to 7. The mistake is falling through to the group class when the owner is denied.
3. `may_delete(dir_mode, dir_uid, dir_gid, file_uid, uid, gids)` requires write and execute on the *directory*, then applies the sticky-bit rule.
4. `emulate_privileged(vm, instr)` is the monitor's trap handler. It updates the VM's virtual `vif`, `console`, `vbase`, and `halted`, and halts with `fault` set on an `out` to a port the VM does not own. It adds 1 to `vm.pc`, because the hardware did not.
5. `run_vm(vm, max_steps)` tries `hw_execute` on each instruction, calls your emulator on `PrivilegeTrap`, and returns `(direct, traps)`.
6. `run_vms(vms, quantum)` runs each live VM for up to `quantum` instructions per round and returns the `(name, executed)` log.
7. `describe_outcome(status)` returns `("exited", code)` or `("signaled", signum)`.
8. `run_limited(func, limits, timeout)` forks. The child sets `RLIMIT_CORE` to zero, applies the limits, calls `func`, and ends with `os._exit` inside `try`/`finally`. The parent polls `os.waitpid(pid, os.WNOHANG)` and sends `SIGKILL` after the timeout. The mistake is letting the child return, which runs the remaining checks a second time.

## Where this breaks

- **Mode bits are coarse.** One owner, one group, and everyone else. Linux adds access control lists (`getfacl`, `setfacl`), and SELinux and AppArmor add rules that even the owner cannot override.
- **Setuid is dangerous.** A privileged program that trusts its input or its environment can be turned against the system. Modern systems prefer capabilities and small helpers.
- **Trap and emulate is slow for chatty guests.** A guest that touches page tables constantly spends its time in the monitor. Hardware support and paravirtual drivers reduce this.
- **Shared hardware leaks.** Guests on one CPU can observe each other through caches and speculation, as Spectre showed.
- **Containers share a kernel.** One kernel bug is everyone's bug, and a container with too many capabilities can break out.
- **Limits are blunt.** `RLIMIT_CPU` counts CPU time, not wall time, so a sleeping program is never stopped. `RLIMIT_AS` counts address space, not memory in use. Cgroups limit the real thing.

## Further reading

- [OSTEP chapter 53: Introduction to Operating System Security](https://pages.cs.wisc.edu/~remzi/OSTEP/security-intro.pdf) — protection goals, access control, and the principle of least privilege.
- [credentials(7) manual page](https://man7.org/linux/man-pages/man7/credentials.7.html) — user ids, group ids, and how the kernel checks them.
- [namespaces(7) manual page](https://man7.org/linux/man-pages/man7/namespaces.7.html) — every namespace type and how to create and enter one.
- [cgroups(7) manual page](https://man7.org/linux/man-pages/man7/cgroups.7.html) — the control group hierarchy, controllers, and the v2 interface.
- [setrlimit(2) manual page](https://man7.org/linux/man-pages/man2/getrlimit.2.html) — each resource limit and the signal or error it produces.
- Popek and Goldberg, "Formal Requirements for Virtualizable Third Generation Architectures" (1974) — the paper that says when trap and emulate works.

## The exercise

You write three isolation models in one module. The permission functions are `describe_mode`, `may_access`, and `may_delete`. The hypervisor functions are `emulate_privileged`, `run_vm`, and `run_vms`, with `VM`, `PrivilegeTrap`, and `hw_execute` provided. The limits functions are `describe_outcome` and `run_limited`.

The checks test every rule above, including the owner-shadows-group case and the sticky bit. They compare per-VM state and instruction counts. Then they fork real children: one runs out of file descriptors, one hits `RLIMIT_FSIZE`, a busy loop dies of `SIGXCPU`, and a sleeper is killed after a timeout. They confirm that no child is left unreaped.

## Where to go next

You started this course not knowing what a kernel was. You have built a toy CPU, a system call table, a process table, a shell with pipes, schedulers, page tables, a TLB, page replacement, a heap allocator, locks, a deadlock detector, disk schedulers, a file system, a journal, and a hypervisor. That is the outline of a real operating system. To go deeper:

1. **Read *Operating Systems: Three Easy Pieces*.** It is free at [pages.cs.wisc.edu/~remzi/OSTEP](https://pages.cs.wisc.edu/~remzi/OSTEP/). This course followed its structure, and its chapters on security and distributed systems go further than we could.
2. **Do the xv6 labs.** MIT's 6.1810 at [pdos.csail.mit.edu/6.828](https://pdos.csail.mit.edu/6.828/) works through *xv6*, a small Unix-like kernel in under ten thousand lines of C. You add system calls, copy-on-write fork, and file system features, and you watch your changes boot. It is the best next step.
3. **Read the Linux kernel source.** Start at [kernel.org](https://www.kernel.org/) with small subsystems: `kernel/sched/` for scheduling, `mm/` for memory, and `fs/` for the file system layer. Use `man 2 <syscall>` to connect each system call to its code.
4. **Poke at your own machine.** Run `strace` on programs you use, read `/proc`, and try `unshare` and cgroups until nothing in the process list surprises you.
