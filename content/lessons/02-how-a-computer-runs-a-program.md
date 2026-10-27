---
title: How a computer runs a program
slug: 02-how-a-computer-runs-a-program
part: "Part 0 — Getting started"
summary: Build a toy CPU with registers, memory, and a program counter, and watch it fetch, decode, and execute a program one instruction at a time.
minutes: 55
gpu: false
objectives:
  - Name the CPU's parts, registers and program counter, and say what memory holds.
  - Trace the fetch-decode-execute cycle by hand, instruction by instruction.
  - Implement a ten-instruction CPU in Python with jumps, memory access, and errors.
  - Write a small loop in the toy machine language.
prereqs:
  - 01-python-you-need
exercise: 02-how-a-computer-runs-a-program
---

# How a computer runs a program

When you run a program, something has to do the work. That something is the *CPU*, the central processing unit. The CPU is a chip that does very simple things, very fast: add two numbers, copy a value, jump to a different place in the program. Everything your computer does, from drawing a web page to playing a song, is billions of these simple steps per second.

You cannot understand an operating system until you know what it manages. The operating system decides which program gets the CPU, where programs live in memory, and what happens when a program misbehaves. Each of those jobs makes sense only once you see what the CPU does on its own.

In this lesson, you build a tiny CPU in Python. It has ten instructions, four registers, and a small memory. It is far simpler than a real chip, but it runs on the same idea. The next lesson looks at the numbers inside it. Lesson 04 reuses this exact instruction set to show what an operating system adds.

## What you already know

- A Python function takes inputs and returns a result.
- A list holds items in order, and you read item `i` with `items[i]`.
- A loop repeats a block of code until a condition changes.
- You raise an exception to say that code cannot continue.

## The parts of a machine

A computer that runs programs has three parts that matter here.

The *CPU* does the work. It can run one instruction at a time. (Real CPUs have several *cores*, each of which does this, but one core is the right picture to start with.)

*Memory* holds data and programs. Think of it as a very long row of numbered boxes. Each box holds one value, and its number is its *address*. Box 0 comes first, then box 1, and so on. Memory is big and fairly slow.

*Registers* are a handful of boxes inside the CPU itself. They are tiny and very fast. The CPU does arithmetic on registers, not on memory directly. To add two numbers from memory, the CPU copies them into registers, adds them there, and copies the result back.

An analogy helps. Picture a cook at a counter. The counter holds the few ingredients the cook is using: those are the registers. The pantry down the hall holds everything else: that is memory. A trip to the pantry takes far longer than reaching for something on the counter.

```text
        +-----------------------------+            +--------------------+
        |            CPU              |            |       MEMORY       |
        |                             |            | addr | value       |
        |  R0  R1  R2  R3  (registers)|  <-----    |   0  |  0          |
        |                             |  copies    |   1  |  0          |
        |  PC  (program counter)      |  ----->    |   2  | 77          |
        |                             |            |  ... |  ...        |
        +-----------------------------+            +--------------------+
```

A real machine has the same shape. A modern 64-bit x86 chip has 16 general-purpose registers, each holding a 64-bit number. Reading a register takes about one *clock cycle*. At 3 GHz a cycle lasts about a third of a nanosecond. Reading main memory takes on the order of 100 nanoseconds, hundreds of times longer. Chips hide part of that cost with small fast memories called caches. You will see why in the lessons on memory.

## What a program is

A *program* is a list of *instructions*. An instruction is one small command that the CPU knows how to do. The list of every instruction a CPU understands, and what each one means, is its *instruction set*. Real instruction sets include x86-64, which most laptops and servers use, and ARM, which phones and Apple silicon Macs use. A real instruction is a number stored in memory. A *machine language* is the form where each instruction is such a number.

Writing numbers by hand is miserable, so people write *assembly language* instead: one readable line per instruction, such as `add rax, rbx`. Your toy CPU takes instructions as Python tuples, which is the same idea in a friendlier shape.

Here is the instruction set you will implement. `R` is a register number from 0 to 3. `A` is a memory address. `T` is a *target*, the index of an instruction in the program.

| Instruction | Meaning |
|---|---|
| `("LOADI", R, value)` | Put the number `value` into register `R`. |
| `("LOAD", R, A)` | Copy memory address `A` into register `R`. |
| `("STORE", R, A)` | Copy register `R` into memory address `A`. |
| `("ADD", Rd, Rs)` | `Rd = Rd + Rs` |
| `("SUB", Rd, Rs)` | `Rd = Rd - Rs` |
| `("JMP", T)` | Continue at instruction `T`. |
| `("JZ", R, T)` | If register `R` holds 0, continue at instruction `T`. Otherwise carry on. |
| `("OUT", R)` | Append register `R` to the output list. |
| `("NOP",)` | Do nothing. |
| `("HALT",)` | Stop the machine. |

Ten instructions are enough to write loops, tests, and real calculations. The trick is the pair `JMP` and `JZ`, which let a program choose and repeat.

One honest simplification: in a real computer, the program sits in memory beside the data, as numbers. In your toy, the program is a separate Python list. This keeps the model small. Everything else in the lesson carries over.

## The program counter

How does the CPU know which instruction to run? It keeps a number called the *program counter*, or *PC*. The PC holds the index of the next instruction. Real chips call it `RIP` on x86-64 and `PC` on ARM.

The PC starts at 0. After each instruction it moves to the next one, so the program runs from top to bottom. A *jump* instruction changes the PC to a different value, which makes the program skip ahead or go back. Going back is how loops work: a jump to an earlier instruction repeats everything after it.

Without the PC, a CPU would run one instruction and not know what to do next. With it, a list of instructions becomes a running program.

## Fetch, decode, execute

Every instruction goes through the same three steps. The CPU repeats them for as long as it runs. This is the *fetch-decode-execute cycle*.

1. **Fetch.** Read the instruction at index `PC`.
2. **Decode.** Work out which instruction it is, and which registers or addresses it names.
3. **Execute.** Do it.

There is a detail about order. Your CPU adds 1 to the PC right after the fetch, before it executes. That means a jump only has to overwrite the PC with its target. A non-jump leaves the PC alone, and the program flows to the next instruction.

In Python, one step has this shape:

```python
def step(self):
    instr = self.program[self.pc]    # fetch
    self.pc += 1                     # point at the next instruction
    op = instr[0]                    # decode
    if op == "LOADI":                # execute
        self.regs[instr[1]] = instr[2]
    elif op == "JMP":
        self.pc = instr[1]
    ...
```

> [!KEY]
> A CPU does only one thing: fetch the instruction at the program counter, execute it, and repeat. Everything a computer does is built on that loop.

## A worked example: add two numbers

Here is a five-instruction program. It adds 2 and 3 and prints the answer.

```text
index  instruction
  0    ("LOADI", 0, 2)      R0 = 2
  1    ("LOADI", 1, 3)      R1 = 3
  2    ("ADD", 0, 1)        R0 = R0 + R1
  3    ("OUT", 0)           print R0
  4    ("HALT",)            stop
```

All registers start at 0, the PC starts at 0, and the output list is empty. The table shows the machine after each step. Read it row by row.

| Step | Fetched at PC | Instruction | Registers after | PC after | Output |
|---|---|---|---|---|---|
| 1 | 0 | `LOADI 0, 2` | `[2, 0, 0, 0]` | 1 | `[]` |
| 2 | 1 | `LOADI 1, 3` | `[2, 3, 0, 0]` | 2 | `[]` |
| 3 | 2 | `ADD 0, 1` | `[5, 3, 0, 0]` | 3 | `[]` |
| 4 | 3 | `OUT 0` | `[5, 3, 0, 0]` | 4 | `[5]` |
| 5 | 4 | `HALT` | `[5, 3, 0, 0]` | 5 | `[5]` |

Five instructions took five steps. The PC ended at 5, one past `HALT`, because the CPU advances the PC before it executes. Your `run` returns 5, counting `HALT`.

## A worked example: a loop

Loops are where the PC earns its keep. This program multiplies 3 by 4 by adding 4 three times. R0 is the running total, R1 counts down from 3, R2 holds 4, and R3 holds the constant 1.

```text
index  instruction
  0    ("LOADI", 0, 0)      total = 0
  1    ("LOADI", 1, 3)      counter = 3
  2    ("LOADI", 2, 4)      amount = 4
  3    ("LOADI", 3, 1)      one = 1
  4    ("JZ", 1, 8)         if counter == 0, go to 8
  5    ("ADD", 0, 2)        total += amount
  6    ("SUB", 1, 3)        counter -= 1
  7    ("JMP", 4)           go back to the test
  8    ("OUT", 0)           print total
  9    ("HALT",)
```

The instructions at indexes 4 to 7 form the loop. Each trip through the loop runs four instructions. Here are the registers at the top of the loop, before `JZ` runs:

| Trip | Registers `[R0, R1, R2, R3]` | `JZ` jumps? |
|---|---|---|
| 1 | `[0, 3, 4, 1]` | no, R1 is 3 |
| 2 | `[4, 2, 4, 1]` | no, R1 is 2 |
| 3 | `[8, 1, 4, 1]` | no, R1 is 1 |
| 4 | `[12, 0, 4, 1]` | yes, R1 is 0, so PC becomes 8 |

The machine then runs `OUT 0`, which outputs 12, and `HALT`. The step count is 4 setup instructions, plus 3 trips of 4 instructions, plus the final `JZ`, `OUT`, and `HALT`: 4 + 12 + 3 = 19 steps.

Notice that `SUB` needs a register that holds 1. The toy machine has no instruction that subtracts a constant, so you keep the constant in a register. Real instruction sets differ here: x86-64 can subtract a constant directly. A tiny instruction set trades convenience for simplicity.

## When things go wrong

A real CPU faces bad programs, and so does yours. Three problems matter.

- **A bad instruction.** An unknown name, or a register number that does not exist, has no meaning. Your CPU raises `CPUError`. A real CPU raises a *fault*, an alarm that it hands to the operating system. Lesson 05 covers what the OS does with it.
- **A bad address.** `LOAD 0, 99` on a 16-word memory reads a box that does not exist. Your CPU raises `CPUError`.
- **Running off the end.** A program with no `HALT` runs past its last instruction and finds nothing. Your CPU raises `CPUError` because the PC is out of range.

There is a fourth problem that no CPU can detect: a program that loops forever. `("JMP", 0)` is a valid program that never ends. Your `run` takes a `max_steps` argument and raises `CPUError` when the program takes more steps than that. Real operating systems face this too, and in lesson 04 you will see how a timer lets the OS take the CPU back from a program that will not give it up.

## Try it on your own machine

These commands show real CPUs. The first two are Linux-only. macOS has `sysctl` instead.

1. Run `lscpu` on Linux. Look for the model name, the number of cores, and the clock speed. On macOS, run `sysctl -n machdep.cpu.brand_string`.
2. Run `grep -c ^processor /proc/cpuinfo` on Linux. It prints how many logical CPUs the kernel sees.
3. Run `python3 -c "import dis; dis.dis(lambda a, b: a + b)"`. Python compiles your code into its own instructions for a virtual machine, and `dis` prints them. Look for `LOAD_FAST` and `BINARY_OP`. The idea is the same as your toy CPU: a list of small instructions, run one at a time.
4. Run `objdump -d /bin/true | head -30` on Linux, if `objdump` is installed. Look at the left column of numbers and the right column of instruction names such as `mov` and `ret`. That is real machine code for your CPU, disassembled into assembly.

## Build it step by step

Open the starter. It defines `CPUError`, the class `CPU`, and the function `make_sum_program`. Fill them in this order, and click Check after each.

1. **`CPU.__init__(program, mem_size)`.** It builds the machine: `self.program` (a list copy of the program), `self.regs` (four zeros), `self.mem` (`mem_size` zeros), `self.pc` (0), `self.halted` (`False`), and `self.output` (an empty list). The common mistake is to keep the caller's `program` list instead of a copy, so a later change to it alters your machine. The first check passes with only this done.
2. **`CPU.step()`, arithmetic and memory.** Fetch with `self.program[self.pc]`, add 1 to `self.pc`, then use an `if`/`elif` chain on `instr[0]`. Start with `LOADI`, `ADD`, and `SUB`, then `LOAD` and `STORE`. A common mistake is writing `self.pc += 1` after the instruction runs. Then `JMP` would be undone.
3. **`CPU.step()`, jumps, output, and halting.** `JMP` sets `self.pc`. `JZ` sets it only when the register is 0. `OUT` appends. `NOP` does nothing. `HALT` sets `self.halted` to `True`.
4. **`CPU.step()`, errors.** Before the fetch, raise `CPUError` if the CPU is halted or the PC is outside `0 <= pc < len(program)`. In the instructions, check that each register number is in `0..3` and each address is inside `self.mem`. Raise `CPUError` for an unknown opcode. A negative index is the trap here: Python accepts `mem[-1]` without complaint, so you must check for it.
5. **`CPU.run(max_steps=1000)`.** Loop on `while not self.halted`, calling `step`. Return the number of instructions executed, `HALT` included. Raise `CPUError` if the count reaches `max_steps` before the machine halts.
6. **`make_sum_program(n)`.** Return a list of instructions that outputs `1 + 2 + ... + n` and halts. Use the multiply program above as a model. Keep the total in R0 and count R1 down from `n` to 0, adding R1 each trip. The common mistake is a wrong jump target. Number your instructions from 0 and count carefully. `n = 0` must output `[0]`.

## Where this breaks

Your toy leaves out almost everything that makes real CPUs hard.

- **Numbers have no size limit.** Python ints grow without bound. A real register holds a fixed number of bits and wraps around when a value gets too large. The next lesson models that.
- **The program is not in memory.** In a real machine a program is stored as numbers beside its data. That has a consequence your toy cannot show: a bug can overwrite the program itself. Operating systems fight this with permission bits on memory, which you meet in the paging lesson.
- **One instruction at a time.** Real chips run several instructions at once, guess which way a jump will go, and run instructions out of order, while keeping the result the same as if they had run one at a time.
- **Memory is slow.** Real chips put small caches between the CPU and memory. Your toy treats every access as equal.
- **There is only one program.** Your CPU runs a program and halts. A real computer runs many programs, which share one CPU. That is the next problem, and the OS exists to solve it.

## Further reading

- [Operating Systems: Three Easy Pieces, Chapter 4: The Abstraction: The Process](https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-intro.pdf) opens with the machine state of a running program: memory, registers, and the program counter.
- [Operating Systems: Three Easy Pieces, Chapter 2: Introduction](https://pages.cs.wisc.edu/~remzi/OSTEP/intro.pdf) describes the fetch-decode-execute cycle and the role of the OS around it.
- [Little Man Computer](https://en.wikipedia.org/wiki/Little_man_computer) is a classic teaching CPU, simpler than real chips, that works like your toy.
- [x86 instruction listings](https://en.wikipedia.org/wiki/X86_instruction_listings) show how large a real instruction set is, compared with your ten.
- [Python dis module](https://docs.python.org/3/library/dis.html) documents the disassembler for Python's own virtual machine.

## The exercise

You build the CPU and a program for it. `CPU` holds the registers, the program counter, a memory list, and the output list. Its `step` method runs one instruction and `run` repeats `step` until `HALT`. `CPUError` signals a bad program. Then you write `make_sum_program(n)`, a program in the toy machine language.

The nine checks go in order: the initial state, arithmetic and the program counter, `STORE` and `LOAD`, jumps, `OUT` with `NOP` and `HALT`, error cases, the runaway guard, a countdown loop with a hand-counted step total, and finally `make_sum_program`. The last check runs your program on a separate reference interpreter and on your own CPU. Click Run to see the machine add 2 and 3 and sum 1 to 4.
