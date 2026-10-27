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
        """Set up the machine, ready to run program from instruction 0.

        Create these attributes:
            self.program  a list of instruction tuples
            self.regs     four registers, all 0 at the start
            self.mem      mem_size words of memory, all 0
            self.pc       the program counter, 0
            self.halted   False
            self.output   an empty list that OUT appends to
        """
        raise NotImplementedError

    def step(self):
        """Run exactly one instruction: fetch, decode, execute.

        Raise CPUError when the CPU is already halted, when pc is outside the
        program, when an instruction names a bad register or memory address,
        or when the opcode is unknown. Add 1 to pc before executing.
        """
        raise NotImplementedError

    def run(self, max_steps=1000):
        """Step until HALT. Return the number of instructions executed, HALT included.

        Raise CPUError if the program has not halted after max_steps steps.
        """
        raise NotImplementedError


def make_sum_program(n):
    """Return a program that outputs 1 + 2 + ... + n, then halts.

    make_sum_program(4), run on a CPU, leaves output == [10].
    make_sum_program(0) outputs [0].
    """
    raise NotImplementedError


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
