"""Checks for the round robin and MLFQ exercise."""

from oscheck import check, equal, fail, has


def J(sub, name, arrival, burst, io_every=0, io_wait=0):
    return has(sub, "Job")(name, arrival, burst, io_every, io_wait)


@check("round_robin rotates three jobs that arrive together")
def test_rr_basic(sub):
    round_robin = has(sub, "round_robin")
    jobs = [J(sub, "A", 0, 5), J(sub, "B", 0, 3), J(sub, "C", 0, 2)]
    # Queue A B C, quantum 2.
    # A 0-2 (3 left). B 2-4 (1 left). C 4-6 (done). A 6-8 (1 left).
    # B 8-9 (done). A 9-10 (done). Total 2+2+2+2+1+1 = 10 = 5+3+2.
    equal(round_robin(jobs, 2),
          [("A", 0, 2), ("B", 2, 4), ("C", 4, 6), ("A", 6, 8), ("B", 8, 9), ("A", 9, 10)])


@check("round_robin queues arrivals ahead of the job that was just preempted")
def test_rr_arrivals(sub):
    round_robin = has(sub, "round_robin")
    jobs = [J(sub, "C", 2, 2), J(sub, "B", 1, 4), J(sub, "A", 0, 4)]
    # Quantum 3. A runs 0-3 (1 left). B (arrival 1) and C (arrival 2) have both
    # arrived by t=3, so the queue is B, C, A.
    # B 3-6 (1 left) -> queue C, A, B. C 6-8 (done). A 8-9 (done). B 9-10 (done).
    equal(round_robin(jobs, 3),
          [("A", 0, 3), ("B", 3, 6), ("C", 6, 8), ("A", 8, 9), ("B", 9, 10)])


@check("round_robin lets an arrival at the exact slice end go first, and idles when empty")
def test_rr_boundary_idle(sub):
    round_robin = has(sub, "round_robin")
    # A runs 0-3 (1 left). B arrives at exactly 3, so B is queued before A:
    # B 3-5 (done), then A 5-6.
    equal(round_robin([J(sub, "A", 0, 4), J(sub, "B", 3, 2)], 3),
          [("A", 0, 3), ("B", 3, 5), ("A", 5, 6)], label="arrival at slice end")
    # A 0-1. Nothing else until B arrives at 4: idle 1-4. B 4-5.
    equal(round_robin([J(sub, "A", 0, 1), J(sub, "B", 4, 1)], 2),
          [("A", 0, 1), ("B", 4, 5)], label="idle gap")


@check("round_robin merges a lone job's slices, and a huge quantum behaves like FCFS")
def test_rr_merge_fcfs(sub):
    round_robin = has(sub, "round_robin")
    # A alone with burst 7 and quantum 3 runs 3 + 3 + 1, but it is one segment.
    equal(round_robin([J(sub, "A", 0, 7)], 3), [("A", 0, 7)], label="single job")
    # Quantum 100 is longer than any burst: each job runs to completion in order.
    jobs = [J(sub, "B", 1, 4), J(sub, "A", 0, 3), J(sub, "C", 2, 2)]
    # A 0-3, B 3-7, C 7-9.
    equal(round_robin(jobs, 100), [("A", 0, 3), ("B", 3, 7), ("C", 7, 9)], label="huge quantum")


@check("round_robin charges the context-switch cost only between different jobs")
def test_rr_switch_cost(sub):
    round_robin = has(sub, "round_robin")
    # A and B, burst 4, quantum 2, cost 1.
    # A 0-2, switch 2-3, B 3-5, switch 5-6, A 6-8, switch 8-9, B 9-11.
    jobs = [J(sub, "A", 0, 4), J(sub, "B", 0, 4)]
    equal(round_robin(jobs, 2, switch_cost=1),
          [("A", 0, 2), ("B", 3, 5), ("A", 6, 8), ("B", 9, 11)], label="two jobs")
    # A alone: it runs 2, 2, 2 with no switches, one merged segment.
    equal(round_robin([J(sub, "A", 0, 6)], 2, switch_cost=1), [("A", 0, 6)], label="lone job")
    # A 0-2, switch 2-5 (cost 3), B 5-7.
    equal(round_robin([J(sub, "A", 0, 2), J(sub, "B", 0, 2)], 2, switch_cost=3),
          [("A", 0, 2), ("B", 5, 7)], label="cost 3")


@check("round_robin rejects a quantum below 1")
def test_rr_invalid(sub):
    round_robin = has(sub, "round_robin")
    for bad in (0, -2):
        try:
            round_robin([J(sub, "A", 0, 3)], bad)
        except ValueError:
            continue
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            fail(f"quantum={bad} should raise ValueError, got {type(exc).__name__}")
        fail(f"quantum={bad} should raise ValueError, but the call returned")


@check("mlfq demotes jobs that use their allotment and round-robins the bottom level")
def test_mlfq_demotion(sub):
    mlfq = has(sub, "mlfq")
    levels = [(1, 1), (2, 2)]
    jobs = [J(sub, "B", 0, 4), J(sub, "A", 0, 4)]
    # Level 0 queue A, B (name order). A 0-1 uses its allotment 1 -> level 1.
    # B 1-2 -> level 1. Level 1 queue A, B with quantum 2.
    # A 2-4 (1 left), B 4-6 (1 left), A 6-7 (done), B 7-8 (done).
    equal(mlfq(jobs, levels),
          [("A", 0, 1), ("B", 1, 2), ("A", 2, 4), ("B", 4, 6), ("A", 6, 7), ("B", 7, 8)])


@check("mlfq lets a short arrival at the top level preempt a demoted CPU hog")
def test_mlfq_preempt(sub):
    mlfq = has(sub, "mlfq")
    levels = [(2, 2), (4, 4)]
    jobs = [J(sub, "A", 0, 10), J(sub, "B", 5, 2)]
    # A runs 0-2 at level 0, uses its allotment 2, drops to level 1.
    # A runs 2-5 at level 1. At t=5 B arrives at level 0 and preempts A.
    # B runs 5-7 and finishes. A (7 ticks of work done: 2 + 3 = 5, so 5 left)
    # resumes at 7: it runs 7-11 (quantum 4), is re-queued, then runs 11-12.
    equal(mlfq(jobs, levels), [("A", 0, 5), ("B", 5, 7), ("A", 7, 12)])


@check("mlfq keeps an I/O-bound job at high priority while a hog sinks")
def test_mlfq_io(sub):
    mlfq = has(sub, "mlfq")
    levels = [(2, 4), (4, 8)]
    jobs = [J(sub, "H", 0, 6), J(sub, "I", 0, 3, io_every=1, io_wait=1)]
    # Level 0 queue H, I. H 0-2 (quantum 2, used 2) -> back of level 0: I, H.
    # I 2-3: 1 tick of CPU = io_every, so I blocks until 3+1 = 4.
    # H 3-4 (slice 1 of 2). At t=4 I wakes at level 0, same level as H: no preempt.
    # H 4-5 uses its 4th tick of allotment (2+1+1): demoted to level 1.
    # t=5: I 5-6, blocks until 7. t=6: only H is ready, H 6-7 at level 1.
    # t=7: I wakes into level 0 and preempts H. I 7-8 is its 3rd tick: done.
    # H runs 8-9 for its sixth and last tick.
    equal(mlfq(jobs, levels),
          [("H", 0, 2), ("I", 2, 3), ("H", 3, 5), ("I", 5, 6),
           ("H", 6, 7), ("I", 7, 8), ("H", 8, 9)])


@check("mlfq priority boost lifts every job back to the top queue")
def test_mlfq_boost(sub):
    mlfq = has(sub, "mlfq")
    levels = [(1, 1), (2, 2)]
    jobs = [J(sub, "A", 0, 6), J(sub, "B", 0, 6)]
    # Without a boost both sink to level 1 and alternate with quantum 2:
    # A 0-1, B 1-2, A 2-4, B 4-6, A 6-8, B 8-10, A 10-11, B 11-12.
    equal(mlfq(jobs, levels),
          [("A", 0, 1), ("B", 1, 2), ("A", 2, 4), ("B", 4, 6),
           ("A", 6, 8), ("B", 8, 10), ("A", 10, 11), ("B", 11, 12)], label="no boost")
    # With boost_every=5: same until t=5. B is running (ticks 4-5); it goes to the
    # front of level 1, queue B, A moves to level 0 with allotment reset.
    # B 5-6 -> demoted to level 1. A 6-7 -> level 1. Level 1 queue B, A.
    # B 7-9 (quantum 2). Then A runs 9-10; at t=10 a boost puts A at level 0
    # again: A 10-11 finishes (A used 1+2+1+1+1 = 6). B 11-12 finishes.
    equal(mlfq(jobs, levels, boost_every=5),
          [("A", 0, 1), ("B", 1, 2), ("A", 2, 4), ("B", 4, 6),
           ("A", 6, 7), ("B", 7, 9), ("A", 9, 11), ("B", 11, 12)], label="boost_every=5")
