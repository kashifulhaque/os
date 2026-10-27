"""Share one toy CPU between programs: contexts, a timer interrupt, and a round-robin dispatcher.

The instruction set is the one from the previous lesson. The only change is that
the "hardware" (registers, pc, halted flag) is split from what lives in memory:
step() receives the program, memory, and output list of whoever is running.

    ("LOADI", R, value)   ("LOAD", R, A)    ("STORE", R, A)
    ("ADD", Rd, Rs)       ("SUB", Rd, Rs)   ("JMP", T)
    ("JZ", R, T)          ("OUT", R)        ("NOP",)       ("HALT",)
"""

from dataclasses import dataclass, field

NUM_REGISTERS = 4


class CPUError(Exception):
    """Raised for a bad instruction, or when the Machine cannot make progress."""


class CPU:
    """The hardware: registers, a program counter, and a halted flag. Provided."""

    def __init__(self):
        self.regs = [0] * NUM_REGISTERS
        self.pc = 0
        self.halted = False

    def step(self, program, mem, output):
        """Run one instruction of `program`, using `mem` and appending to `output`."""
        if self.halted:
            raise CPUError("the CPU is halted")
        if not 0 <= self.pc < len(program):
            raise CPUError(f"pc {self.pc} is outside the program")
        instr = program[self.pc]
        self.pc += 1
        op = instr[0]
        if op == "LOADI":
            self.regs[instr[1]] = instr[2]
        elif op == "LOAD":
            self.regs[instr[1]] = mem[instr[2]]
        elif op == "STORE":
            mem[instr[2]] = self.regs[instr[1]]
        elif op == "ADD":
            self.regs[instr[1]] += self.regs[instr[2]]
        elif op == "SUB":
            self.regs[instr[1]] -= self.regs[instr[2]]
        elif op == "JMP":
            self.pc = instr[1]
        elif op == "JZ":
            if self.regs[instr[1]] == 0:
                self.pc = instr[2]
        elif op == "OUT":
            output.append(self.regs[instr[1]])
        elif op == "NOP":
            pass
        elif op == "HALT":
            self.halted = True
        else:
            raise CPUError(f"unknown instruction {op!r}")


@dataclass
class Context:
    """A saved copy of the CPU's private state. Provided."""

    regs: list
    pc: int


@dataclass
class Process:
    """A program plus everything the OS keeps for it. Provided."""

    pid: int
    program: list
    mem: list = field(default_factory=lambda: [0] * 16)
    ctx: Context = field(default_factory=lambda: Context([0] * NUM_REGISTERS, 0))
    output: list = field(default_factory=list)
    done: bool = False


def save_context(cpu):
    """Copy the CPU's registers and pc into a new Context.

    Changing cpu.regs afterwards must not change the Context you return.
    """
    raise NotImplementedError


def restore_context(cpu, ctx):
    """Load a saved Context back into the CPU. The CPU is not halted afterwards.

    Running the CPU afterwards must not change ctx.
    """
    raise NotImplementedError


def next_runnable(procs, current):
    """Return the index of the next process after `current` that is not done, or None.

    Look at current + 1, current + 2, ... wrapping around the list. `current`
    itself is the last one considered. Use current = -1 to start from process 0.

    With three processes and process 1 done: next_runnable(procs, 0) -> 2.
    """
    raise NotImplementedError


class Machine:
    """One CPU, several processes, and a timer that fires every `quantum` instructions."""

    def __init__(self, programs, quantum):
        """Create self.cpu = CPU(), self.quantum, and one Process per program (pids 0, 1, ...).

        Also set self.schedule = [] and self.timer_interrupts = 0.
        Raise ValueError if quantum is less than 1.
        """
        raise NotImplementedError

    def run(self, max_slices=10000):
        """Run every process to completion, round robin. Return self.schedule.

        Each time slice: restore the process's context, run up to `quantum`
        instructions (stopping early if the program halts), save the context,
        and append (pid, instructions_run) to self.schedule. A slice that ends
        without a HALT counts as one timer interrupt. Finished processes are
        skipped. Raise CPUError after max_slices slices.
        """
        raise NotImplementedError

    def outputs(self):
        """Return {pid: list of values that process printed with OUT}."""
        raise NotImplementedError


if __name__ == "__main__":
    prog_a = [("LOADI", 0, 1), ("LOADI", 1, 2), ("ADD", 0, 1), ("OUT", 0), ("HALT",)]
    prog_b = [("LOADI", 0, 7), ("OUT", 0), ("HALT",)]
    machine = Machine([prog_a, prog_b], quantum=2)
    schedule = machine.run()
    print("schedule (pid, instructions):", schedule)
    print("timer interrupts:", machine.timer_interrupts)
    print("outputs:", machine.outputs())
