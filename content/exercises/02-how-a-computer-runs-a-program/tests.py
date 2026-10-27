"""Checks for the toy CPU exercise."""

from oscheck import check, equal, fail, has


def make(sub, program, mem_size=16):
    return has(sub, "CPU")(program, mem_size)


def expect_cpu_error(sub, action, what):
    CPUError = has(sub, "CPUError")
    try:
        action()
    except CPUError:
        return
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"{what}: raised {type(exc).__name__}, expected CPUError")
    fail(f"{what}: expected CPUError, but nothing was raised")


def reference_output(program, limit=5000):
    """A tiny independent interpreter, so the program check does not depend on the reader's CPU."""
    regs, mem, out, pc = [0] * 4, [0] * 16, [], 0
    for _ in range(limit):
        ins = program[pc]
        pc += 1
        op = ins[0]
        if op == "LOADI":
            regs[ins[1]] = ins[2]
        elif op == "ADD":
            regs[ins[1]] += regs[ins[2]]
        elif op == "SUB":
            regs[ins[1]] -= regs[ins[2]]
        elif op == "JMP":
            pc = ins[1]
        elif op == "JZ":
            if regs[ins[1]] == 0:
                pc = ins[2]
        elif op == "OUT":
            out.append(regs[ins[1]])
        elif op == "HALT":
            return out
        else:
            raise AssertionError(f"reference interpreter has no {op}")
    raise AssertionError("reference interpreter ran too long")


@check("a new CPU starts with zeroed registers, pc 0, and empty output")
def test_init(sub):
    cpu = make(sub, [("HALT",)], 8)
    equal(list(cpu.regs), [0, 0, 0, 0], label="regs")
    equal(cpu.pc, 0, label="pc")
    equal(len(cpu.mem), 8, label="len(mem)")
    equal(list(cpu.mem), [0] * 8, label="mem")
    equal(cpu.halted, False, label="halted")
    equal(list(cpu.output), [], label="output")


@check("LOADI, ADD, and SUB change registers and advance pc by one")
def test_arithmetic(sub):
    cpu = make(sub, [("LOADI", 0, 5), ("LOADI", 1, 3), ("ADD", 0, 1), ("SUB", 1, 0)])
    cpu.step()
    equal(list(cpu.regs), [5, 0, 0, 0], label="regs after LOADI 0, 5")
    equal(cpu.pc, 1, label="pc after one step")
    cpu.step()
    cpu.step()
    equal(list(cpu.regs), [8, 3, 0, 0], label="regs after ADD 0, 1")  # 5 + 3 = 8
    cpu.step()
    equal(list(cpu.regs), [8, -5, 0, 0], label="regs after SUB 1, 0")  # 3 - 8 = -5
    equal(cpu.pc, 4, label="pc after four steps")


@check("STORE writes memory and LOAD reads it back")
def test_memory(sub):
    cpu = make(sub, [("LOADI", 2, 77), ("STORE", 2, 5), ("LOADI", 2, 0), ("LOAD", 3, 5)])
    for _ in range(4):
        cpu.step()
    equal(cpu.mem[5], 77, label="mem[5]")
    equal(list(cpu.regs), [0, 0, 0, 77], label="regs after LOAD 3, 5")


@check("JMP always jumps and JZ jumps only when the register is zero")
def test_jumps(sub):
    cpu = make(sub, [("JMP", 3), ("HALT",), ("HALT",), ("NOP",)])
    cpu.step()
    equal(cpu.pc, 3, label="pc after JMP 3")

    taken = make(sub, [("JZ", 0, 5)])
    taken.step()
    equal(taken.pc, 5, label="pc after JZ with R0 == 0")

    not_taken = make(sub, [("LOADI", 0, 1), ("JZ", 0, 5), ("NOP",)])
    not_taken.step()
    not_taken.step()
    equal(not_taken.pc, 2, label="pc after JZ with R0 == 1 (falls through)")


@check("OUT records values, NOP does nothing, and HALT stops the machine")
def test_out_halt(sub):
    cpu = make(sub, [("LOADI", 0, 9), ("NOP",), ("OUT", 0), ("OUT", 1), ("HALT",)])
    steps = cpu.run()
    equal(list(cpu.output), [9, 0], label="output")
    equal(cpu.halted, True, label="halted")
    equal(steps, 5, label="run() return value (instructions executed, HALT included)")
    equal(cpu.pc, 5, label="pc after HALT points past it")


@check("step raises CPUError for bad programs")
def test_errors(sub):
    expect_cpu_error(sub, lambda: make(sub, [("FLY", 0)]).step(), "unknown opcode FLY")
    expect_cpu_error(sub, lambda: make(sub, [("LOADI", 4, 1)]).step(), "register number 4")
    expect_cpu_error(sub, lambda: make(sub, [("LOAD", 0, 16)], 16).step(), "address 16 in a 16-word memory")
    expect_cpu_error(sub, lambda: make(sub, [("STORE", 0, -1)]).step(), "address -1")
    expect_cpu_error(sub, lambda: make(sub, [("NOP",)]).run() , "running off the end of the program")
    expect_cpu_error(sub, lambda: make(sub, [("JMP", 9)]).run(), "jumping outside the program")

    cpu = make(sub, [("HALT",), ("NOP",)])
    cpu.step()
    expect_cpu_error(sub, cpu.step, "stepping a halted CPU")


@check("run raises CPUError when a program never halts")
def test_runaway(sub):
    cpu = make(sub, [("JMP", 0)])
    expect_cpu_error(sub, lambda: cpu.run(max_steps=50), "an infinite loop with max_steps=50")
    # A program of exactly max_steps instructions is fine.
    ok = make(sub, [("NOP",), ("NOP",), ("HALT",)])
    equal(ok.run(max_steps=3), 3, label="run(max_steps=3) on a 3-instruction program")


@check("a loop that counts down runs the right number of steps")
def test_loop(sub):
    # R0 = 3; R1 = 1; while R0 != 0: R0 -= R1; OUT R0
    program = [
        ("LOADI", 0, 3),  # 0
        ("LOADI", 1, 1),  # 1
        ("JZ", 0, 6),     # 2
        ("SUB", 0, 1),    # 3
        ("OUT", 0),       # 4
        ("JMP", 2),       # 5
        ("HALT",),        # 6
    ]
    cpu = make(sub, program)
    steps = cpu.run()
    equal(list(cpu.output), [2, 1, 0], label="output")
    # 2 setup + 3 iterations of (JZ, SUB, OUT, JMP) + final JZ + HALT = 2 + 12 + 1 + 1
    equal(steps, 16, label="steps")


@check("make_sum_program computes 1 + 2 + ... + n")
def test_sum_program(sub):
    make_sum_program = has(sub, "make_sum_program")
    for n in (0, 1, 4, 10, 25):
        program = make_sum_program(n)
        want = [n * (n + 1) // 2]
        try:
            got = reference_output(program)
        except AssertionError as exc:
            fail(f"make_sum_program({n}) is not a valid program: {exc}")
        except (IndexError, TypeError) as exc:
            fail(f"make_sum_program({n}) is not a valid program ({type(exc).__name__}: {exc})")
        equal(got, want, label=f"output of make_sum_program({n})")
    cpu = make(sub, make_sum_program(10))
    cpu.run()
    equal(list(cpu.output), [55], label="make_sum_program(10) on your own CPU")
