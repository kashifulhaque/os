"""A toy CPU: four registers, a program counter, a list of instructions, and a small memory.

The instruction set (ten instructions). R means a register number 0-3, A a
memory address, T an instruction index.

    ("LOADI", R, value)   R = value
    ("LOAD",  R, A)       R = mem[A]
    ("STORE", R, A)       mem[A] = R
    ("ADD",   Rd, Rs)     Rd = Rd + Rs
    ("SUB",   Rd, Rs)     Rd = Rd - Rs
    ("JMP",   T)          pc = T
    ("JZ",    R, T)       if R == 0: pc = T
    ("OUT",   R)          append R to the output list
    ("NOP",)              do nothing
    ("HALT",)             stop the machine
"""

NUM_REGISTERS = 4


class CPUError(Exception):
    """Raised when the machine cannot continue: a bad instruction or a runaway program."""


class CPU:
    def __init__(self, program, mem_size=16):
        self.program = list(program)
        self.regs = [0] * NUM_REGISTERS
        self.mem = [0] * mem_size
        self.pc = 0
        self.halted = False
        self.output = []

    def _reg(self, r):
        """Check a register number and return it."""
        if not isinstance(r, int) or not 0 <= r < NUM_REGISTERS:
            raise CPUError(f"bad register number {r!r}")
        return r

    def _addr(self, a):
        """Check a memory address and return it."""
        if not isinstance(a, int) or not 0 <= a < len(self.mem):
            raise CPUError(f"bad memory address {a!r}")
        return a

    def step(self):
        """Run exactly one instruction: fetch, decode, execute."""
        if self.halted:
            raise CPUError("the CPU is halted")
        # Fetch.
        if not 0 <= self.pc < len(self.program):
            raise CPUError(f"pc {self.pc} is outside the program (length {len(self.program)})")
        instr = self.program[self.pc]
        self.pc += 1  # point at the next instruction before executing this one
        # Decode.
        op = instr[0]
        # Execute.
        if op == "LOADI":
            self.regs[self._reg(instr[1])] = instr[2]
        elif op == "LOAD":
            self.regs[self._reg(instr[1])] = self.mem[self._addr(instr[2])]
        elif op == "STORE":
            self.mem[self._addr(instr[2])] = self.regs[self._reg(instr[1])]
        elif op == "ADD":
            self.regs[self._reg(instr[1])] += self.regs[self._reg(instr[2])]
        elif op == "SUB":
            self.regs[self._reg(instr[1])] -= self.regs[self._reg(instr[2])]
        elif op == "JMP":
            self.pc = instr[1]
        elif op == "JZ":
            if self.regs[self._reg(instr[1])] == 0:
                self.pc = instr[2]
        elif op == "OUT":
            self.output.append(self.regs[self._reg(instr[1])])
        elif op == "NOP":
            pass
        elif op == "HALT":
            self.halted = True
        else:
            raise CPUError(f"unknown instruction {op!r}")

    def run(self, max_steps=1000):
        """Step until HALT. Return the number of instructions executed, HALT included."""
        steps = 0
        while not self.halted:
            if steps >= max_steps:
                raise CPUError(f"program did not halt within {max_steps} steps")
            self.step()
            steps += 1
        return steps


def make_sum_program(n):
    """Return a program that outputs 1 + 2 + ... + n, then halts.

    make_sum_program(4), run on a CPU, leaves output == [10].
    """
    return [
        ("LOADI", 0, 0),   # 0: R0 = 0, the running total
        ("LOADI", 1, n),   # 1: R1 = n, the counter
        ("LOADI", 2, 1),   # 2: R2 = 1, the constant one
        ("JZ", 1, 7),      # 3: counter is zero -> go to the end
        ("ADD", 0, 1),     # 4: total += counter
        ("SUB", 1, 2),     # 5: counter -= 1
        ("JMP", 3),        # 6: test again
        ("OUT", 0),        # 7: output the total
        ("HALT",),         # 8
    ]


if __name__ == "__main__":
    program = [
        ("LOADI", 0, 2),
        ("LOADI", 1, 3),
        ("ADD", 0, 1),
        ("OUT", 0),
        ("HALT",),
    ]
    cpu = CPU(program)
    steps = cpu.run()
    print("2 + 3 printed:", cpu.output, "after", steps, "steps")
    print("registers:", cpu.regs, "pc:", cpu.pc)

    cpu = CPU(make_sum_program(4))
    steps = cpu.run()
    print("sum of 1..4 printed:", cpu.output, "after", steps, "steps")
