"""Checks for the time-slicing exercise."""

from oscheck import check, equal, fail, has

A = [("LOADI", 0, 1), ("LOADI", 1, 2), ("ADD", 0, 1), ("OUT", 0), ("HALT",)]  # prints 3, 5 instructions
B = [("LOADI", 0, 7), ("OUT", 0), ("HALT",)]  # prints 7, 3 instructions
# C counts down from 3, printing each value: 2 setup + 3 * 4 loop + JZ + HALT = 16 instructions.
C = [
    ("LOADI", 0, 3),
    ("LOADI", 1, 1),
    ("JZ", 0, 6),
    ("SUB", 0, 1),
    ("OUT", 0),
    ("JMP", 2),
    ("HALT",),
]


def solo_output(sub, program):
    """Run one program alone, with a quantum big enough that no timer fires."""
    Machine = has(sub, "Machine")
    m = Machine([program], quantum=1000)
    m.run()
    return m.outputs()[0]


@check("save_context copies registers and pc")
def test_save(sub):
    CPU, save_context = has(sub, "CPU"), has(sub, "save_context")
    cpu = CPU()
    cpu.regs = [1, 2, 3, 4]
    cpu.pc = 9
    ctx = save_context(cpu)
    equal(list(ctx.regs), [1, 2, 3, 4], label="saved regs")
    equal(ctx.pc, 9, label="saved pc")
    cpu.regs[0] = 99
    cpu.pc = 0
    equal(list(ctx.regs), [1, 2, 3, 4], label="saved regs after the CPU changed (the context must be a copy)")
    equal(ctx.pc, 9, label="saved pc after the CPU changed")


@check("restore_context loads registers and pc and clears halted")
def test_restore(sub):
    CPU, Context = has(sub, "CPU"), has(sub, "Context")
    restore_context = has(sub, "restore_context")
    cpu = CPU()
    cpu.halted = True
    ctx = Context([5, 6, 7, 8], 3)
    restore_context(cpu, ctx)
    equal(list(cpu.regs), [5, 6, 7, 8], label="cpu.regs")
    equal(cpu.pc, 3, label="cpu.pc")
    equal(cpu.halted, False, label="cpu.halted")
    cpu.regs[1] = 0
    equal(list(ctx.regs), [5, 6, 7, 8], label="ctx.regs after the CPU changed (restore must copy)")


@check("next_runnable walks round robin and skips finished processes")
def test_next(sub):
    Process, next_runnable = has(sub, "Process"), has(sub, "next_runnable")
    procs = [Process(0, []), Process(1, []), Process(2, [])]
    equal(next_runnable(procs, -1), 0, label="start from -1")
    equal(next_runnable(procs, 0), 1, label="after 0")
    equal(next_runnable(procs, 2), 0, label="after 2 wraps to 0")
    procs[1].done = True
    equal(next_runnable(procs, 0), 2, label="after 0 with process 1 done")
    procs[0].done = True
    equal(next_runnable(procs, 2), 2, label="only process 2 is left, so it is chosen again")
    procs[2].done = True
    equal(next_runnable(procs, 2), None, label="everything done")
    equal(next_runnable([], -1), None, label="no processes")


@check("Machine rejects a quantum below 1 and sets up one process per program")
def test_init(sub):
    Machine = has(sub, "Machine")
    m = Machine([A, B, C], quantum=3)
    equal([p.pid for p in m.procs], [0, 1, 2], label="pids")
    equal(m.quantum, 3, label="quantum")
    equal(m.timer_interrupts, 0, label="timer_interrupts before running")
    try:
        Machine([A], quantum=0)
    except ValueError:
        return
    fail("Machine(..., quantum=0) should raise ValueError")


@check("a program that fits in one quantum runs without any timer interrupt")
def test_no_interrupt(sub):
    Machine = has(sub, "Machine")
    m = Machine([A], quantum=100)
    schedule = m.run()
    equal(schedule, [(0, 5)], label="schedule")
    equal(m.timer_interrupts, 0, label="timer_interrupts")
    equal(m.outputs(), {0: [3]}, label="outputs")


@check("two programs interleave with quantum 2 exactly as worked by hand")
def test_two_programs(sub):
    Machine = has(sub, "Machine")
    m = Machine([A, B], quantum=2)
    schedule = m.run()
    # A has 5 instructions and B has 3. Slices of 2: A2 B2 A2 B1(halts) A1(halts).
    equal(schedule, [(0, 2), (1, 2), (0, 2), (1, 1), (0, 1)], label="schedule")
    equal(m.timer_interrupts, 3, label="timer_interrupts")  # A, B, A were interrupted
    equal(m.outputs(), {0: [3], 1: [7]}, label="outputs")


@check("time slicing never changes what a program computes, for any quantum")
def test_isolation(sub):
    Machine = has(sub, "Machine")
    want = {0: solo_output(sub, A), 1: solo_output(sub, B), 2: solo_output(sub, C)}
    equal(want, {0: [3], 1: [7], 2: [2, 1, 0]}, label="outputs when each program runs alone")
    for quantum in (1, 2, 3, 4, 7, 50):
        m = Machine([A, B, C], quantum=quantum)
        m.run()
        equal(m.outputs(), want, label=f"outputs with quantum={quantum}")


@check("quantum 1 alternates one instruction at a time and totals add up")
def test_quantum_one(sub):
    Machine = has(sub, "Machine")
    m = Machine([B, B], quantum=1)
    schedule = m.run()
    equal(schedule, [(0, 1), (1, 1)] * 3, label="schedule")
    total = sum(n for _, n in m.schedule)
    equal(total, 6, label="total instructions run")  # 3 + 3
    equal(m.timer_interrupts, 4, label="timer_interrupts")  # 6 slices, the 2 that ran HALT are not interrupts

    m = Machine([A, B, C], quantum=3)
    m.run()
    equal(sum(n for _, n in m.schedule), 5 + 3 + 16, label="total instructions with three programs")
    for pid, n in m.schedule:
        if not 1 <= n <= 3:
            fail(f"a slice for pid {pid} ran {n} instructions; each slice must run between 1 and the quantum")


@check("a program that never halts raises CPUError instead of hanging")
def test_runaway(sub):
    Machine, CPUError = has(sub, "Machine"), has(sub, "CPUError")
    m = Machine([[("JMP", 0)], B], quantum=5)
    try:
        m.run(max_slices=20)
    except CPUError:
        return
    fail("a machine running an infinite loop should raise CPUError once max_slices is reached")
