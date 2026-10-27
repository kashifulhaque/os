---
title: Processes and the process table
slug: 06-processes
part: "Part 2 — Processes"
summary: See what the kernel keeps for every running program, and model the process table, its state machine, and zombie reaping.
minutes: 50
gpu: false
objectives:
  - Say the difference between a program and a process, and list what the kernel tracks for each process.
  - Move a process through new, ready, running, blocked, zombie, and terminated, and say which moves are legal.
  - "Explain what a zombie and an orphan are, and why the kernel keeps a zombie until its parent calls wait."
prereqs:
  - 05-kernel-mode-and-system-calls
exercise: 06-processes
---

# Processes and the process table

A program is a file. It sits on a disk and does nothing. When you start it, the
operating system turns that file into something alive: a thing that has a
place in memory, a spot in the code where it is up to, files it has open, and a
share of the CPU. That living thing is a *process*.

Your computer runs hundreds of processes at once, on a handful of CPU cores.
The kernel must keep each one apart from the others, remember where each one
stopped, and decide who runs next. To do that, it needs a record for every
process. This lesson is about that record and about the life cycle it tracks.

You call no system calls here. You will build a *simulation*: a
process table that you can poke, break, and check. The next three lessons use
the real kernel, and the model from this lesson is what makes them make sense.

## What you already know

- The kernel runs in kernel mode and user programs run in user mode.
- A system call is how a user program asks the kernel to do something for it.
- A timer interrupt lets the kernel take the CPU back and run something else.
- Saving and restoring registers lets one CPU serve two programs by turns.
- A Python class can hold fields, and a dict can map an id to an object.

## A program is not a process

A recipe is not a meal. The recipe is a list of steps on a card. The meal is
what happens when a cook follows the card in a real kitchen, with real
ingredients, at a particular step.

A program is the recipe. A process is the cooking. Two facts follow:

- One program can be many processes. Open two terminals, and you have two
  processes running the same `bash` file.
- One process can change which program it runs. The next lesson shows how.

> [!KEY]
> A process is a running program plus everything the kernel tracks about it.
> The program is a file. The process is the activity.

## What a process has

Every process owns a bundle of things. You met most of them in earlier lessons.

- An *address space*: the memory it can see, holding its code, data, heap, and
  stack.
- *Registers*, including the program counter that says which instruction is
  next.
- A list of *open files*. Each one has a small number called a file
  descriptor.
- A *process id*, or pid: a number that names the process.
- A *parent*: the process that created it.
- A *state*: what it is doing at this moment.

The first two live in the hardware while the process runs. When the kernel
switches to another process, it copies the registers into memory and loads the
other process's registers. Everything else lives in memory the kernel owns.

```text
 one process, as the kernel sees it

 +------------------------------------------+
 | pid 412   parent 1   state: ready        |   <- the PCB (kernel memory)
 | saved registers: pc=0x4011a0 sp=0x7ffe.. |
 | open files: 0 -> terminal, 1 -> terminal |
 | address space -> (page tables, lesson 14)|
 +------------------------------------------+
        |
        v
 +------------------------------------------+
 | code | data | heap ... free ... | stack  |   <- the process's memory
 +------------------------------------------+
```

## The process control block

The kernel keeps one record per process. Textbooks call it the *process
control block*, or *PCB*. Linux calls it a `task_struct`. It is a big
structure, with hundreds of fields. These are the ones to know:

| Field | What it holds | Linux name |
|---|---|---|
| Process id | The number that names the process | `pid` |
| Parent id | The pid of the creator | `ppid` |
| State | New, ready, running, blocked, zombie, terminated | `__state` |
| Saved registers | Copied out when the process stops running | kept in the kernel stack |
| Address space | Where its memory lives | `mm` |
| Open files | The file descriptor table | `files` |
| Exit status | The number it returned when it ended | `exit_code` |
| Children | Which processes it created | `children` |

In the exercise your PCB is a small Python dataclass with the fields you need:
`pid`, `ppid`, `name`, `state`, `exit_status`, and `children`.

## The process table

The kernel keeps all the PCBs in one collection called the *process table*. In
your model it is a dict from pid to PCB. A pid is how every other part of the
system refers to a process, so it must be unique at any moment.

Pid 1 is special. The kernel starts exactly one process by itself, and that
process starts everything else. On a modern Linux system it is called `init`
or `systemd`. It never exits. You will see why it matters in a moment.

The table has a fixed size. On Linux, `cat /proc/sys/kernel/pid_max` shows the
largest pid. A system with no free slot cannot create a process, and
`fork` fails with the error `EAGAIN`. Your table models this with a
`max_procs` limit and a `ProcessLimit` exception.

## The state machine

At any moment a process is doing one of a few things. The kernel records which
one in the *state* field. The standard model has six states:

- `new`: the PCB exists, but the process is not yet admitted to run.
- `ready`: the process could run, and is waiting for a CPU.
- `running`: the process has the CPU at this moment.
- `blocked`: the process waits for something, such as a disk read or a key
  press. It cannot use a CPU even if one is free.
- `zombie`: the process has ended, but its record stays so the parent can read
  its exit status.
- `terminated`: the parent has read the status, and the record is free.

Only some moves between states make sense. A blocked process cannot jump
straight to running, because the thing it waits for has not been delivered.
Here are the legal moves as a picture.

```text
            admit             scheduler picks
   new ----------> ready ---------------------> running
                     ^   <---------------------   |  |
                     |     timer interrupt        |  |
                     |     (time slice ends)      |  |
                     |                            |  |
                     |  event arrives             |  | waits for
                     +------- blocked <-----------+  | disk, key, ...
                                                     |
                                       exit(status)  v
                                                   zombie
                                                     |
                                       parent waits  v
                                                terminated
```

And as a table you can code from. Each row says where a process can go next.

| From | To | What causes it |
|---|---|---|
| new | ready | The kernel admits the process. |
| ready | running | The scheduler gives it the CPU. |
| running | ready | The timer interrupt ends its time slice. |
| running | blocked | It asks for something that is not ready yet. |
| running | zombie | It calls `exit`. |
| blocked | ready | The thing it waited for arrives. |
| zombie | terminated | Its parent calls `wait`. |

That is seven arrows. Everything else is illegal.

> [!KEY]
> A blocked process never goes straight to running. It becomes ready first,
> and the scheduler decides when it runs. Scheduling is the subject of Part 3.

The model has one more rule, because we model one CPU. At most one process is
`running` at a time. A second process that tries to run must wait until the
first one gives up the CPU.

Linux simplifies this. It does not keep a `new` state you can observe, and it
does not show a separate `terminated`. It also reports `ready` and `running`
as one state, `R`. The `ps` command prints the state in a column called `STAT`:

| `STAT` | Meaning |
|---|---|
| `R` | Running, or ready to run |
| `S` | Sleeping, waiting for an event (our blocked) |
| `D` | Sleeping in a way a signal cannot interrupt, often waiting for a disk |
| `T` | Stopped by a signal |
| `Z` | Zombie |

## A worked example

Follow three processes in a table with `max_procs=4`. Pid 1 is `init`. Pids
count up from 2 and are never reused.

1. `create("shell")` makes pid 2, a child of init, in state `new`. Init's
   `children` list becomes `[2]`.
2. The shell moves `new -> ready -> running`.
3. The shell creates a child, `create("worker", ppid=2)`. This is pid 3.
4. The shell blocks: `running -> blocked`. This frees the CPU. Pid 3 moves
   `new -> ready -> running`.
5. The worker finishes with `exit(3, status=0)`. It is a zombie.

Here is the table after step 5.

```text
 pid  ppid  name    state     exit_status  children
  1     0   init    ready     None         [2]
  2     1   shell   blocked   None         [3]
  3     2   worker  zombie    0            []
```

The worker is over, but its row stays. It holds the exit status `0`, which the
shell may want. Next, the shell wakes up (`blocked -> ready`) and calls
`wait(2)`. The call finds the zombie child 3, returns `(3, 0)`, and moves it to
`terminated`. The shell's `children` list becomes `[]`. The table is full of
history that no one needs, so the slot is free for reuse.

## Zombies and orphans

Why does the kernel keep a dead process around? Because the parent may ask how
the child ended. "Did the compile succeed?" is an exit status. If the kernel
threw the record away at once, the answer would be lost. So the record stays,
shrunk to the pid and the status, until the parent calls `wait`.

A process in that state is a *zombie*: dead, but still listed. A zombie uses
no CPU and almost no memory. It does hold a slot in the table. A parent that
never calls `wait` leaks one slot per child, and in the end the table fills.

The opposite problem is a parent that exits first. Its children become
*orphans*. Nobody is left to wait for them. The kernel solves this by
re-parenting every orphan to pid 1. Init's job includes calling `wait` in a
loop, so orphans are reaped when they end.

```text
 before the shell exits         after the shell exits

     init (1)                       init (1)
       |                           /   |    \
     shell (2)                shell(2) a(4)  b(5)
      /     \                  zombie
   a (4)   b (5)
```

In the picture, the shell becomes a zombie, and init adopts `a` and `b`. Init
reaps the shell's zombie when it next calls `wait`.

> [!KEY]
> A zombie is a finished process waiting to be reaped. An orphan is a running
> process whose parent has died. The kernel hands orphans to init.

## Try it on your own machine

Run these in a Linux terminal. Most also work on macOS, but `/proc` and the
`STAT` letters are Linux details.

1. List processes with their parents and states.

   ```bash
   ps -eo pid,ppid,stat,comm | head -20
   ```

   Find pid 1 and look at the `ppid` column of everything near it. Most
   processes trace back to pid 1 through their parents.

2. Draw the whole family tree.

   ```bash
   pstree -p | head -30
   ```

   Each line is a parent and its children, with pids in brackets. If `pstree`
   is missing, `ps -ejH` prints a similar indented list.

3. Read your own shell's PCB through `/proc`.

   ```bash
   cat /proc/$$/status | head -12
   ```

   `$$` is the pid of your shell. Look at `Name`, `State`, `Pid`, and `PPid`.
   These are the fields from the table above, as the kernel reports them.

4. Make a zombie on purpose (Linux).

   ```bash
   python3 -c "import os, time; pid = os.fork(); os._exit(0) if pid == 0 else time.sleep(20)" &
   sleep 1; ps -o pid,ppid,stat,comm --ppid $!
   ```

   The child exits at once. The parent sleeps and never calls `wait`. The
   `ps` line shows state `Z` and a name ending in `<defunct>`. After 20
   seconds the parent exits, init adopts the zombie, and it disappears.

5. See how many processes you can have.

   ```bash
   cat /proc/sys/kernel/pid_max; ulimit -u
   ```

   The first number is the pid ceiling. The second is your per-user process
   limit, if one is set.

## Build it step by step

You write `can_transition` and the methods of `ProcessTable`. The starter gives
you the state names, the exceptions, the `PCB` dataclass, and `__init__`.
`__init__` creates pid 1, `init`, in state `ready`, and sets `next_pid` to 2.

1. **`can_transition(old, new)`** takes two state names and returns a bool. Hold
   the seven arrows in a dict from each state to the set of states it may
   reach, and look `new` up in the set for `old`. A common mistake is to
   forget that `terminated` has no exits. Give it an empty set.
2. **`get(pid)`** returns the PCB or raises `NoSuchProcess`. Catch the
   `KeyError` here, once. Every later method calls `get`, so none of them
   repeats the error handling.
3. **`create(name, ppid=1)`** makes a PCB in state `new`, gives it the next pid,
   and appends it to the parent's `children`. It first checks three things. The
   parent must exist. The parent must not be a zombie or terminated. The count
   of processes that are not `terminated` must be below `max_procs`. The
   mistake to avoid is to skip zombies in that count. A zombie still holds its
   slot.
4. **`transition(pid, new_state)`** changes a state or raises
   `IllegalTransition` and changes nothing. Check three things before you
   touch the PCB. The move must be legal under `can_transition`. A move into
   `zombie` or `terminated` is refused, because only `exit` and `wait` may do
   those. A move into `running` is refused when any process is already
   running.
5. **`exit(pid, status)`** ends a running process. Refuse pid 1 and refuse a
   process that is not `running`. Set the state to `zombie` and store the
   status. Then give every child to init: set its `ppid` to 1 and append it to
   init's `children`. Empty the exiting process's own `children` list.
6. **`wait(parent_pid, child_pid=None)`** reaps. It returns `(pid, status)` for
   a zombie child, marks it `terminated`, and removes it from the parent's
   `children`. When children exist but none is a zombie, it returns `None`.
   That stands for "a real `wait` would block here". When the parent has no
   children, or `child_pid` is not one of them, it raises `NoChildren`.
7. **`descendants(pid)`** returns every child, grandchild, and so on, as a
   sorted list. A loop with a stack of pids to visit is enough. **`count_by_state()`**
   returns a dict with all six states as keys, including those with a count of
   zero.

## Where this breaks

The model is clean. Real systems are messier in these ways.

- **The process table fills up.** A runaway program that calls `fork` in a loop
  is a *fork bomb*. It eats every slot, and nothing else can start, including
  the shell you would use to stop it. Real systems limit processes per user
  (`ulimit -u`) and per container (a control group setting called
  `pids.max`).
- **Zombies pile up.** A long-running server that forgets to call `wait` leaks
  a slot per child. You can see it as a growing list of `Z` entries in `ps`.
  The fix is in the parent: call `wait`, or tell the kernel you do not care,
  which the next lesson mentions.
- **Pids are reused.** Your model never reuses a pid. Linux does, once the
  counter wraps around. A program that remembers a pid and sends it a
  signal later might hit a different process. Newer kernels offer *pidfds*,
  file descriptors that name one specific process, to close this gap.
- **Pid 1 is not always init.** Inside a container, the first process of the
  container is pid 1 for that container. Many programs are not written to
  reap orphans, and zombies pile up. Small init programs exist for that
  reason.
- **Threads change the picture.** In Linux each thread has its own
  `task_struct`. Part 5 returns to this.
- **The `D` state can hang for a long time.** A process waiting on a broken
  network disk sits in uninterruptible sleep, and even `kill -9` waits until
  the disk answers.

## Further reading

- [Operating Systems: Three Easy Pieces, chapter 4, The Abstraction: The Process](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-intro.pdf)
  introduces the process, its states, and the process list.
- [Operating Systems: Three Easy Pieces, chapter 5, Process API](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf)
  motivates `fork`, `exec`, and `wait`, which the next lesson uses.
- [The ps(1) manual page](https://man7.org/linux/man-pages/man1/ps.1.html)
  lists every process state code in the "PROCESS STATE CODES" section.
- [The proc(5) manual page](https://man7.org/linux/man-pages/man5/proc.5.html)
  explains each file under `/proc/<pid>/`, including `status`.
- [xv6: a simple, Unix-like teaching operating system](https://pdos.csail.mit.edu/6.828/2023/xv6/book-riscv-rev3.pdf)
  shows a real, small process table in chapter 7, Scheduling.

## The exercise

You build `can_transition`, which encodes the state machine, and
`ProcessTable`, with `get`, `create`, `transition`, `exit`, `wait`,
`descendants`, and `count_by_state`. The checks start with the state machine
alone, so you see progress after the first function.

The later checks drive the table through full lives: creating processes and
linking parents, refusing illegal moves, running one process at a time, making
a zombie, reaping it with `wait`, and re-parenting orphans to init. One check
confirms that a zombie keeps its table slot until `wait` frees it. Each failure
message shows the value you returned next to the value it expected.
