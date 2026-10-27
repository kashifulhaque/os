---
title: What an operating system does
slug: 04-what-an-operating-system-does
part: "Part 1 — What an operating system is"
summary: "See why computers need an operating system, then build its first trick: sharing one CPU between programs with a timer and saved registers."
minutes: 55
gpu: false
objectives:
  - Explain the operating system's three jobs, virtualization, concurrency, and persistence.
  - Say what a timer interrupt is, and why the OS needs one to share the CPU.
  - Describe a context, and save and restore it to switch between programs.
  - Run two programs on one toy CPU by time slicing, and verify that neither notices.
prereqs:
  - 02-how-a-computer-runs-a-program
  - 03-bits-bytes-and-memory
exercise: 04-what-an-operating-system-does
---

# What an operating system does

In lesson 02, you built a CPU that runs one program from start to finish. That is not how your laptop works. It runs a browser, a music player, a terminal, and dozens of background programs. It has a handful of CPU cores, and at any instant each core runs one instruction of one program. Somehow every program behaves as if it has the machine to itself.

The software that makes this work is the *operating system*, or OS. It sits between programs and hardware. It decides who uses the CPU and for how long, hands out memory, and keeps files. It also keeps programs from damaging one another.

In this lesson, you see what the OS is for, and then you build the first and most important trick: making one CPU look like many. You use the toy CPU from lesson 02, with the same ten instructions.

## What you already know

- A CPU repeats fetch, decode, and execute, and the program counter says which instruction comes next.
- Registers are the CPU's own small fast storage. They hold what the program is working on.
- Memory is an array of boxes, each with an address, and the CPU copies values between memory and registers.
- A program is a list of instructions in the toy machine language, such as `LOADI`, `ADD`, `JZ`, and `HALT`.

## Why we need an operating system

Imagine a computer with no OS. Every program would have to talk to the hardware itself. A program that wants to save a file would need to know how the disk works. Two programs could not run together, because each would assume it owned the whole machine. One buggy program could overwrite another's memory, or the memory of the machine itself.

The OS solves this with three jobs. A well-known textbook, *Operating Systems: Three Easy Pieces*, names them as three themes.

- **Virtualization.** The OS turns each physical resource into a more general, easier virtual one. One CPU becomes many virtual CPUs. One block of memory becomes a private address space for every program. Each program sees a clean machine that it can believe is its own.
- **Concurrency.** Many things happen at once, and they must not trip over each other. The OS keeps many programs, and later many threads inside a program, running without corrupting shared data.
- **Persistence.** Memory forgets when the power goes off. The OS stores data on disks and SSDs and organises it into files and directories that survive a reboot.

An analogy: think of a hotel. The guests are programs. The building has a limited number of rooms, one kitchen, and one front door. The hotel staff is the OS. Staff give each guest a room, so that each guest feels at home. They schedule the kitchen so that everyone eats. They keep the guests out of each other's rooms. And they keep the guest records in a ledger that survives when the guests leave.

The OS also acts as a *standard library* for the hardware. A program asks to "write these bytes to a file", and the OS knows how to do it on any disk. Lesson 05 shows how the request crosses from a program to the OS.

> [!KEY]
> An operating system makes a computer's hardware safe, shared, and easy to use. It does this by virtualizing resources, managing concurrency, and storing data persistently.

The *kernel* is the core of the OS: the part that is always in memory and that runs with full power over the hardware. People also say "the OS" when they mean the kernel plus the tools around it, such as the shell and the file manager. Linux is, strictly, a kernel. This course uses "OS" and "kernel" in the way each makes sense, and says so when it matters.

## A single CPU, many programs

Take the CPU first. The goal is called *time sharing*: let each program run for a short while, then switch to another, over and over, so quickly that all of them seem to run at once.

```text
time ->
CPU:  | A | B | A | B | A | C | B | A |
        ^   ^   ^
        a program runs for a slice of time, then the OS switches
```

At any one instant, only one program is running on a core. But if the switch happens every few milliseconds, a person sees every program move forward. A film works the same way. It is a series of still pictures that look like motion.

This needs two things. First, a way to take the CPU away from a program, even a program that never gives it up. Second, a way to switch without losing anything.

## Taking the CPU back: the timer interrupt

Suppose a program runs `JMP 0` forever. If the OS only gets control when the program gives it back, nothing else ever runs. The OS needs a way to interrupt.

Computers have a small piece of hardware called a *timer*. The OS asks it to count down and then fire. When it fires, the CPU stops what it was doing, saves enough to return, and jumps into code the OS provided in advance. This event is a *timer interrupt*. The program has no say. It does not call the timer, and it cannot refuse.

An *interrupt* is any signal from hardware that makes the CPU stop its current work and run a *handler*, a routine that the OS registered for that signal. Timers, keyboards, disks, and network cards all use them. In Linux you can see them with `cat /proc/interrupts`.

How long should a slice be? The timer in a Linux system ticks at a rate set when the kernel is built, commonly 100, 250, or 1,000 times a second. A rate of 250 means one tick every 4 milliseconds. Lesson 11 covers how that choice shapes scheduling.

In this lesson, you model the timer as a *quantum*: the number of instructions a program may run before the timer fires. A quantum of 2 means the CPU runs two instructions of one program, then the OS takes over.

## Switching without losing anything: the context

When the OS takes the CPU from program A and gives it to B, what has to be remembered about A? Everything that A will need to continue exactly where it stopped.

In your toy CPU, that is two things: the four registers and the program counter. Nothing else inside the CPU is private to a program. The set of these values is the program's *context*, also called its *CPU state*. A real CPU has more to save, such as 16 general-purpose registers on x86-64, plus flags and floating-point registers, but the idea is the same.

A *context switch* does two steps:

1. **Save** the running program's context from the CPU into a record that belongs to that program.
2. **Restore** the next program's saved context from its record into the CPU.

After the restore, the CPU holds exactly what the next program's registers held when it was last stopped, and its program counter points at the instruction it would have run next. The program carries on as though nothing happened.

The record the OS keeps for each program is the start of what lesson 06 calls a *process*: a running program plus everything the OS tracks about it. In this lesson, a `Process` holds the program, its private memory, its saved context, its output, and a flag for whether it has finished.

## Worked example: two programs, quantum 2

Program A adds 1 and 2, prints the answer, and stops. Program B prints 7 and stops.

```text
A (5 instructions)              B (3 instructions)
 0  LOADI 0, 1                   0  LOADI 0, 7
 1  LOADI 1, 2                   1  OUT 0
 2  ADD 0, 1                     2  HALT
 3  OUT 0
 4  HALT
```

Run them with a quantum of 2. Each row is one *time slice*, a turn on the CPU. The CPU's registers at the end of each slice are in square brackets.

| Slice | Process | Instructions run | CPU registers, pc at the end | What happens next |
|---|---|---|---|---|
| 1 | A | `LOADI 0,1`, `LOADI 1,2` | `[1, 2, 0, 0]`, pc 2 | Timer fires. Save A. Restore B. |
| 2 | B | `LOADI 0,7`, `OUT 0` | `[7, 0, 0, 0]`, pc 2 | Timer fires. Save B. Restore A. |
| 3 | A | `ADD 0,1`, `OUT 0` | `[3, 2, 0, 0]`, pc 4 | Timer fires. Save A. Restore B. |
| 4 | B | `HALT` (1 instruction) | halted | B finished before the timer fired. |
| 5 | A | `HALT` (1 instruction) | halted | A finished. Nothing is left. |

The schedule, as `(process, instructions run)` pairs, is `[(0, 2), (1, 2), (0, 2), (1, 1), (0, 1)]`. Three slices ended with a timer interrupt, and two ended because the program halted.

Look at the start of slice 3. A's saved context is `[1, 2, 0, 0]` with pc 2. The CPU held `[7, 0, 0, 0]` after B ran. The restore overwrote the CPU with A's saved values, so A's `ADD 0, 1` computes 1 + 2 = 3.

Imagine the OS forgot to restore. B's `7` would still sit in R0, and A's `ADD 0, 1` would compute 7 + 0 = 7. A would print 7 instead of 3. The program would have no way to know. Saving and restoring carefully is the whole trick, and a bug in it breaks programs that have nothing wrong with them.

The outputs are `{0: [3], 1: [7]}`, the same as if each program had run alone.

> [!KEY]
> Time slicing must be invisible. A program's results with other programs running must be identical to its results alone, whatever the quantum.

The exercise tests exactly that, with quantum values from 1 to 50.

## Dispatching in code

The loop the OS runs is called the *dispatcher*. In Python, one pass through it has this shape:

```python
restore_context(cpu, proc.ctx)        # load the process's registers and pc
ran = 0
while ran < quantum and not cpu.halted:
    cpu.step(proc.program, proc.mem, proc.output)
    ran += 1
proc.ctx = save_context(cpu)          # store them back
```

The dispatcher repeats this for each process in turn, going back to the first after the last. This order is *round robin*. It skips any process that has halted. When all of them have halted, the machine is done. Lessons 10 and 11 explore other orders.

Two details matter. When the quantum runs out, the program might be unfinished, so the dispatcher counts a timer interrupt. If the program halts first, the CPU was returned by the program itself. That is not a timer interrupt.

> [!WARNING]
> Copy the registers when you save and when you restore. If your saved context holds the same list object as the CPU, the next program's work changes it. This is the same trap as two names for one list, from lesson 01.

## What the toy leaves out

Your machine shows the mechanism, but three things it does not do are the topic of the next lessons.

First, your timer is a counter in a Python loop. Real timers are hardware, and a real program cannot tell it from magic. The CPU takes the interrupt at any instruction boundary, and the handler runs in a more privileged mode. The next lesson is about that privilege.

Second, your processes have separate memory because each has its own Python list. In a real machine, all programs share one physical memory. The OS and hardware cooperate to give each program its own *address space*, which Part 4 builds.

Third, each program gets the same quantum and takes turns in a fixed order. A real scheduler decides who runs next based on how long a program has run, whether it waits for the disk, and how important it is. Part 3 covers that.

## Try it on your own machine

1. Run `uname -a`. Look for the kernel name (`Linux` or `Darwin`), its version, and the CPU type.
2. Run `cat /proc/interrupts | head` on Linux. Look for one row per kind of interrupt and one column per CPU. The timer and keyboard are in there, and the counts increase while you work.
3. Run `grep ctxt /proc/self/status` on Linux. Look for the two lines `voluntary_ctxt_switches` and `nonvoluntary_ctxt_switches`, the number of times the kernel switched away from the `grep` process because it waited, and because its time ran out.
4. Run `vmstat 1 5` on Linux. Look at the `cs` column: the count of context switches across the whole machine each second. Idle laptops often show hundreds or thousands.
5. Run `ps -e | wc -l`. Look at how many programs the kernel is juggling, and compare it with the handful of cores in `nproc`.

## Build it step by step

Open the starter. `CPU`, `Context`, and `Process` are given. The CPU's `step(program, mem, output)` runs one instruction of the program you hand it. The instructions are the same as in lesson 02. The one difference is that registers and the program counter live on the CPU, and the program and memory belong to whoever is running.

1. **`save_context(cpu)`.** Return a `Context` with a copy of `cpu.regs` and the value of `cpu.pc`. Copy the list with `list(cpu.regs)`. The common mistake is storing `cpu.regs` itself.
2. **`restore_context(cpu, ctx)`.** Write the saved registers and pc into the CPU, copying the list. Set `cpu.halted = False`. If you forget, a halted CPU refuses to run the next program.
3. **`next_runnable(procs, current)`.** Return the index of the next process after `current` that is not done, wrapping around, or `None` if all are done. Check `len(procs)` positions starting from `current + 1`, with `% len(procs)`. The current process is the last one considered. The call `next_runnable(procs, -1)` finds the first process.
4. **`Machine.__init__(programs, quantum)`.** Create a `CPU`, store the quantum, and make one `Process` per program with pids 0, 1, 2, and so on. Set `schedule` to an empty list and `timer_interrupts` to 0. Raise `ValueError` if `quantum < 1`.
5. **`Machine.run(max_slices)`.** Follow the code sketch above in a loop over `next_runnable`. After each slice, append `(pid, ran)` to `self.schedule`. Mark the process done if the CPU halted, or else add 1 to `timer_interrupts`. Raise `CPUError` after `max_slices` slices, so an infinite loop does not hang. Return `self.schedule`.
6. **`Machine.outputs()`.** Return a dict from pid to the list of values that the process printed.

## Where this breaks

- **Context switches cost time.** Saving and restoring registers, and the other work around a switch, takes on the order of microseconds on a real machine. A switch that happens every instruction would waste nearly all the time. A quantum that is too long makes a program wait. Choosing it is a trade-off.
- **A timer does not pick who runs next.** It only returns control to the OS. Part 3 is about the choice.
- **Saved state is bigger in real machines.** Real contexts include more registers and the page table pointer. Restoring them dirties the CPU's caches, which makes the next program slower for a while.
- **Nothing here protects programs from each other.** Any program in a real machine could overwrite the OS if the hardware allowed it. The next lesson introduces the hardware feature that stops it.

## Further reading

- [Operating Systems: Three Easy Pieces, Chapter 2: Introduction to Operating Systems](https://pages.cs.wisc.edu/~remzi/OSTEP/intro.pdf) describes the three themes: virtualization, concurrency, and persistence.
- [Operating Systems: Three Easy Pieces, Chapter 6: Mechanism: Limited Direct Execution](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf) covers the timer interrupt and the context switch in the detail this lesson builds toward.
- [Operating Systems: Three Easy Pieces, Chapter 4: The Abstraction: The Process](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-intro.pdf) introduces the idea of a process and its machine state.
- [proc(5) man page](https://man7.org/linux/man-pages/man5/proc.5.html) documents `/proc/interrupts` and `/proc/<pid>/status`.
- [vmstat(8) man page](https://man7.org/linux/man-pages/man8/vmstat.8.html) explains the `cs` column and the rest of the tool's output.

## The exercise

You build the first piece of an operating system. `save_context` and `restore_context` copy the CPU's private state out and back in. `next_runnable` chooses whose turn it is, round robin. `Machine` ties them together: `Machine(programs, quantum)` holds one CPU and a `Process` per program, `run()` time-slices them with a simulated timer, and `outputs()` reports what each program printed.

The nine checks go from the small to the whole. They check that saved contexts are copies, that a restore clears the halted flag, the round-robin order with finished processes skipped, the constructor, a program that fits in one quantum, the schedule `[(0, 2), (1, 2), (0, 2), (1, 1), (0, 1)]` worked above, the key property that outputs match solo runs for every quantum, the one-instruction-at-a-time case with totals, and that a program that never halts raises `CPUError`. Click Run to see the worked example print its schedule, interrupt count, and outputs.
