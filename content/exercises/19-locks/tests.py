"""Checks for the locks exercise."""

from oscheck import check, equal, fail, has

MEM = {"counter": 0}


def _solo(sub, program, mem=None):
    """Run one thread alone to completion and return the machine."""
    run_schedule = has(sub, "run_schedule")
    return run_schedule([program], [0] * 80, mem if mem is not None else dict(MEM))


def _naive_lock(sub):
    """A broken lock: it checks the flag and sets it in two separate steps."""
    critical_section = has(sub, "critical_section")
    return (
        [("load", "f", "lock"), ("jnz", "f", 0), ("set", "lock", 1)]
        + critical_section()
        + [("set", "lock", 0)]
    )


@check("spin_lock_program uses tas, runs alone to counter == 1, and frees the lock")
def test_spin_program(sub):
    spin_lock_program = has(sub, "spin_lock_program")
    prog = spin_lock_program()
    if not any(step[0] == "tas" for step in prog):
        fail("the spin lock should take the lock with an atomic ('tas', ...) step, but found none")
    m = _solo(sub, prog, {"counter": 0, "lock": 0})
    equal(m.mem.get("counter"), 1, label="counter after one thread runs alone")
    equal(m.mem.get("lock"), 0, label="lock cell after release")
    equal(m.in_cs, set(), label="threads still inside the critical section at the end")


@check("cas_lock_program uses cas, runs alone to counter == 1, and frees the lock")
def test_cas_program(sub):
    cas_lock_program = has(sub, "cas_lock_program")
    prog = cas_lock_program()
    if not any(step[0] == "cas" for step in prog):
        fail("the CAS lock should take the lock with an atomic ('cas', ...) step, but found none")
    m = _solo(sub, prog, {"counter": 0, "lock": 0})
    equal(m.mem.get("counter"), 1, label="counter after one thread runs alone")
    equal(m.mem.get("lock"), 0, label="lock cell after release")
    # A lock that is already held must keep a lone thread spinning: after 30
    # steps with lock == 1 it must still not have entered the critical section.
    run_schedule = has(sub, "run_schedule")
    held = run_schedule([prog], [0] * 30, {"counter": 0, "lock": 1})
    equal(held.in_cs, set(), label="thread entered the critical section although the lock was held")
    equal(held.mem.get("counter"), 0, label="counter while the lock is held by someone else")


@check("ticket_lock_program hands out ticket 0 and advances now_serving")
def test_ticket_program(sub):
    ticket_lock_program = has(sub, "ticket_lock_program")
    prog = ticket_lock_program()
    m = _solo(sub, prog, {"counter": 0, "next_ticket": 0, "now_serving": 0})
    equal(m.mem.get("counter"), 1, label="counter after one thread runs alone")
    equal(m.mem.get("next_ticket"), 1, label="next_ticket after one acquire")
    equal(m.mem.get("now_serving"), 1, label="now_serving after one release")
    # With tickets 0..2 already taken but only 0 served, a thread holding ticket 3
    # (next_ticket = 3 is handed out as it arrives) must wait while now_serving = 1.
    run_schedule = has(sub, "run_schedule")
    waiting = run_schedule([prog], [0] * 40, {"counter": 0, "next_ticket": 3, "now_serving": 1})
    equal(waiting.in_cs, set(), label="a thread with ticket 3 entered while now_serving was 1")


@check("peterson_program runs alone and uses its own flag cell")
def test_peterson_program(sub):
    peterson_program = has(sub, "peterson_program")
    for tid in (0, 1):
        m = _solo(sub, peterson_program(tid), {"counter": 0})
        equal(m.mem.get("counter"), 1, label=f"counter after thread {tid} runs alone")
        equal(m.mem.get(f"flag{tid}"), 0, label=f"flag{tid} after leaving")
        other = m.mem.get(f"flag{1 - tid}", 0)
        equal(other, 0, label=f"flag{1 - tid} must stay untouched by thread {tid}")
        equal(m.mem.get("turn"), 1 - tid, label=f"turn after thread {tid} runs: it hands the turn to the other")


@check("reachable finds every state once, with a shortest schedule to each")
def test_reachable(sub):
    reachable = has(sub, "reachable")
    Machine = has(sub, "Machine")
    writer = [("set", "x", 1)]
    states = reachable([writer, writer], {})
    # pc pairs (0,0), (1,0), (0,1), (1,1) -> 4 states.
    equal(len(states), 4, label="states for two one-step threads")
    equal(states[Machine([writer, writer], {}).key()], [], label="schedule to the start state")
    equal(sorted(map(tuple, states.values())), [(), (0,), (0, 1), (1,)], label="shortest schedules (thread 0 tried first)")
    # Two increment threads have 3 steps each, so no shortest schedule is
    # longer than 6 steps.
    inc = [("load", "r", "c"), ("add", "r", 1), ("store", "c", "r")]
    big = reachable([inc, inc], {"c": 0})
    for schedule in big.values():
        if len(schedule) > 6:
            fail(f"a shortest schedule has {len(schedule)} steps, but each program has only 3 steps")
    # A thread that spins forever still has finitely many states.
    spinner = [("jmp", 0)]
    equal(len(reachable([spinner], {})), 1, label="states for a thread that loops forever")
    # Every recorded schedule must really lead to its state.
    run_schedule = has(sub, "run_schedule")
    for key, schedule in big.items():
        equal(run_schedule([inc, inc], schedule, {"c": 0}).key(), key, label=f"replaying schedule {schedule}")


@check("find_violation returns the shortest schedule that breaks a naive lock")
def test_find_violation(sub):
    find_violation = has(sub, "find_violation")
    run_schedule = has(sub, "run_schedule")
    naive = _naive_lock(sub)
    mem = {"counter": 0, "lock": 0}
    schedule = find_violation([naive, naive], mem)
    if schedule is None:
        fail("the naive lock (check the flag, then set it in a separate step) breaks mutual exclusion, but find_violation returned None")
    machine = run_schedule([naive, naive], schedule, mem)
    equal(machine.in_cs, {0, 1}, label=f"threads in the critical section after {schedule}")
    # Each thread needs 4 steps (load, jnz, set, cs_enter) to get in, and the
    # second thread must load before the first sets the flag: 8 steps minimum.
    equal(len(schedule), 8, label="length of the shortest violating schedule")
    # Without any lock at all, two threads are in the critical section after 2 steps.
    critical_section = has(sub, "critical_section")
    equal(find_violation([critical_section(), critical_section()], {"counter": 0}), [0, 1], label="no lock at all")


@check("final_values sees both outcomes of an unprotected counter")
def test_final_values(sub):
    final_values = has(sub, "final_values")
    critical_section = has(sub, "critical_section")
    bare = critical_section()
    # Same race as lesson 18: both threads read 0 (result 1), or run one after the other (result 2).
    equal(final_values([bare, bare], {"counter": 0}, "counter"), [1, 2], label="unprotected counter")
    equal(final_values([bare], {"counter": 5}, "counter"), [6], label="a single thread")


def _assert_good_lock(sub, programs, mem, n):
    find_violation = has(sub, "find_violation")
    final_values = has(sub, "final_values")
    v = find_violation(programs, mem)
    if v is not None:
        fail(f"mutual exclusion should hold, but find_violation returned the schedule {v}")
    equal(final_values(programs, mem, "counter"), [n], label=f"final counter values with {n} threads")


@check("the test-and-set and compare-and-swap locks give mutual exclusion for 2 and 3 threads")
def test_spin_and_cas_locks_safe(sub):
    for name in ("spin_lock_program", "cas_lock_program"):
        p = has(sub, name)()
        _assert_good_lock(sub, [p, p], {"counter": 0, "lock": 0}, 2)
        _assert_good_lock(sub, [p, p, p], {"counter": 0, "lock": 0}, 3)


@check("the ticket lock gives mutual exclusion for 2 and 3 threads")
def test_ticket_lock_safe(sub):
    ticket_lock_program = has(sub, "ticket_lock_program")
    p = ticket_lock_program()
    mem = {"counter": 0, "next_ticket": 0, "now_serving": 0}
    _assert_good_lock(sub, [p, p], dict(mem), 2)
    _assert_good_lock(sub, [p, p, p], dict(mem), 3)


@check("Peterson's algorithm gives mutual exclusion for two threads")
def test_peterson_safe(sub):
    peterson_program = has(sub, "peterson_program")
    _assert_good_lock(sub, [peterson_program(0), peterson_program(1)], {"counter": 0}, 2)
