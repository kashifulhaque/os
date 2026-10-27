"""Checks for the threads-and-race-conditions exercise."""

import sys
import threading

from oscheck import check, equal, fail, has


def call_with_timeout(fn, *args, timeout=20):
    """Run fn(*args) in a helper thread. Fail, rather than hang, on timeout."""
    box = {}

    def runner():
        try:
            box["value"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001
            box["error"] = exc

    helper = threading.Thread(target=runner, daemon=True)
    helper.start()
    helper.join(timeout)
    if helper.is_alive():
        fail(f"{getattr(fn, '__name__', 'your function')} did not finish within {timeout} seconds")
    if "error" in box:
        raise box["error"]
    return box["value"]


@check("Machine.step runs load, add, store, and set, with per-thread registers")
def test_step(sub):
    Machine = has(sub, "Machine")
    prog = [("load", "r", "x"), ("add", "r", 5), ("store", "y", "r"), ("set", "z", 9)]
    m = Machine([prog, prog], {"x": 3})
    m.step(0)
    equal(m.regs[0].get("r"), 3, label="after load, thread 0 register r")
    equal(m.pc, [1, 0], label="program counters after one step of thread 0")
    equal(m.regs[1].get("r", 0), 0, label="thread 1's register r is untouched")
    m.step(0)
    equal(m.regs[0]["r"], 8, label="after add 5, register r (3 + 5)")
    m.step(0)
    equal(m.mem.get("y"), 8, label="after store, mem['y']")
    m.step(0)
    equal(m.mem.get("z"), 9, label="after set, mem['z']")
    equal(m.done(0), True, label="thread 0 finished")
    equal(m.done(1), False, label="thread 1 not started")
    # Reading a never-written address gives 0.
    m2 = Machine([[("load", "q", "nowhere"), ("store", "out", "q")]], {})
    m2.step(0)
    m2.step(0)
    equal(m2.mem.get("out"), 0, label="a never-written address reads as 0")
    try:
        m.step(0)
    except ValueError:
        return
    fail("stepping a finished thread should raise ValueError")


@check("increment_program is a three-step load, add, store on the given address")
def test_increment_program(sub):
    increment_program = has(sub, "increment_program")
    Machine = has(sub, "Machine")
    prog = increment_program()
    equal(len(prog), 3, label="number of steps in increment_program()")
    m = Machine([prog], {"counter": 5})
    for _ in range(3):
        m.step(0)
    equal(m.mem["counter"], 6, label="counter after one run, starting at 5")
    prog2 = increment_program("hits")
    m = Machine([prog2], {"hits": 40, "counter": 1})
    for _ in range(3):
        m.step(0)
    equal(m.mem["hits"], 41, label="hits after increment_program('hits')")
    equal(m.mem["counter"], 1, label="counter must not be touched")


@check("run_schedule gives 2 for a serial schedule and 1 for an overlapping one")
def test_run_schedule(sub):
    increment_program = has(sub, "increment_program")
    run_schedule = has(sub, "run_schedule")
    programs = [increment_program(), increment_program()]
    mem = {"counter": 0}
    m = run_schedule(programs, [0, 0, 0, 1, 1, 1], mem)
    equal(m.mem["counter"], 2, label="serial schedule [0,0,0,1,1,1]")
    # T0 load(0), T1 load(0), T0 add, T0 store(1), T1 add (0+1), T1 store(1).
    m = run_schedule(programs, [0, 1, 0, 0, 1, 1], mem)
    equal(m.mem["counter"], 1, label="overlapping schedule [0,1,0,0,1,1]")
    equal(mem, {"counter": 0}, label="the mem you pass in must not be modified")
    m = run_schedule(programs, [0, 0, 0, 0, 0, 1, 1, 1], mem)
    equal(m.mem["counter"], 2, label="entries for a finished thread do nothing")


@check("interleavings lists every merge of the threads' steps, in order")
def test_interleavings(sub):
    interleavings = has(sub, "interleavings")
    equal(
        interleavings([2, 2]),
        [[0, 0, 1, 1], [0, 1, 0, 1], [0, 1, 1, 0], [1, 0, 0, 1], [1, 0, 1, 0], [1, 1, 0, 0]],
        label="interleavings([2, 2])",
    )
    equal(len(interleavings([3, 3])), 20, label="count for [3, 3]  (6!/(3!3!))")
    equal(len(interleavings([1, 1, 1])), 6, label="count for [1, 1, 1]  (3!)")
    equal(len(interleavings([2, 2, 2])), 90, label="count for [2, 2, 2]  (6!/(2!2!2!))")
    equal(interleavings([0, 2]), [[1, 1]], label="interleavings([0, 2])")
    equal(interleavings([0, 0]), [[]], label="interleavings([0, 0]) is one empty schedule")
    for s in interleavings([2, 3]):
        equal((s.count(0), s.count(1)), (2, 3), label=f"step counts in schedule {s}")


@check("outcome_counts shows 18 of 20 schedules lose an update")
def test_outcome_counts(sub):
    increment_program = has(sub, "increment_program")
    outcome_counts = has(sub, "outcome_counts")
    programs = [increment_program(), increment_program()]
    # Only the two serial schedules keep both increments: 2 schedules give 2,
    # and the other 18 give 1 (both threads read 0 and both write 1).
    equal(outcome_counts(programs, {"counter": 0}, "counter"), {2: 2, 1: 18}, label="two incrementers")
    # With three threads, 3 steps each, there are 1680 schedules.
    three = outcome_counts([increment_program()] * 3, {"counter": 0}, "counter")
    equal(sum(three.values()), 1680, label="total schedules for three incrementers (9!/(3!3!3!))")
    equal(max(three), 3, label="best possible final value with three incrementers")
    equal(min(three), 1, label="worst possible final value with three incrementers")
    # No race when each thread writes a different cell.
    other = outcome_counts([increment_program("a"), increment_program("b")], {}, "a")
    equal(other, {1: 20}, label="threads using different cells never interfere")


@check("find_lost_update returns the first losing schedule, or None when there is none")
def test_find_lost_update(sub):
    increment_program = has(sub, "increment_program")
    find_lost_update = has(sub, "find_lost_update")
    run_schedule = has(sub, "run_schedule")
    programs = [increment_program(), increment_program()]
    mem = {"counter": 0}
    got = find_lost_update(programs, mem, "counter", 2)
    # Schedules starting 0,0,0 are the serial one. The next in order is
    # [0,0,1,0,1,1]: T1 loads before T0 stores.
    equal(got, [0, 0, 1, 0, 1, 1], label="first losing schedule")
    equal(run_schedule(programs, got, mem).mem["counter"], 1, label="replaying that schedule")
    sets = [[("set", "x", 1)], [("set", "x", 1)]]
    equal(find_lost_update(sets, {}, "x", 1), None, label="two writers of the same value")
    # Reaching the wrong expectation: x ends as 1 or 2 depending on order.
    mixed = [[("set", "x", 1)], [("set", "x", 2)]]
    equal(find_lost_update(mixed, {}, "x", 2), [1, 0], label="last writer wins")


def _hammer(n_threads, work):
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # ask the interpreter to switch threads very often
    try:
        threads = [threading.Thread(target=work) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)
            if t.is_alive():
                fail("a worker thread did not finish within 20 seconds")
    finally:
        sys.setswitchinterval(old)


@check("SafeCounter loses no increments under many real threads")
def test_safe_counter(sub):
    SafeCounter = has(sub, "SafeCounter")
    counter = SafeCounter()
    equal(counter.value, 0, label="a fresh counter")

    def work():
        for _ in range(2000):
            counter.increment()

    _hammer(8, work)
    equal(counter.value, 16000, label="value after 8 threads x 2000 increments")
    other = SafeCounter()
    other.increment()
    equal((counter.value, other.value), (16000, 1), label="two counters must not share state")


@check("increment_with_lock returns exactly threads x iterations")
def test_increment_with_lock(sub):
    increment_with_lock = has(sub, "increment_with_lock")
    equal(call_with_timeout(increment_with_lock, 1, 10), 10, label="increment_with_lock(1, 10)")
    equal(call_with_timeout(increment_with_lock, 0, 5), 0, label="increment_with_lock(0, 5)")
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for _ in range(3):
            equal(call_with_timeout(increment_with_lock, 4, 5000), 20000, label="increment_with_lock(4, 5000)")
    finally:
        sys.setswitchinterval(old)
