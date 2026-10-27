"""Checks for the proportional-share scheduling exercise."""

import random
from collections import Counter

from oscheck import almost, check, equal, fail, has


class ScriptedRng:
    """A stand-in for random.Random that returns scripted draws and records calls."""

    def __init__(self, draws):
        self.draws = list(draws)
        self.asked = []

    def randrange(self, n, *rest):
        self.asked.append(n)
        if not self.draws:
            fail("lottery asked for more draws than there were slices")
        return self.draws.pop(0)


def J(sub, name, arrival, burst):
    return has(sub, "Job")(name, arrival, burst)


@check("weight_for_nice reads Linux's table and rejects values outside -20..19")
def test_weight(sub):
    weight_for_nice = has(sub, "weight_for_nice")
    for nice, want in [(-20, 88761), (-5, 3121), (0, 1024), (5, 335), (19, 15)]:
        equal(weight_for_nice(nice), want, label=f"weight_for_nice({nice})")
    for bad in (-21, 20):
        try:
            weight_for_nice(bad)
        except ValueError:
            continue
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            fail(f"nice={bad} should raise ValueError, got {type(exc).__name__}")
        fail(f"nice={bad} should raise ValueError, but the call returned")


@check("vruntime_delta scales run time by 1024 / weight")
def test_vruntime_delta(sub):
    vruntime_delta = has(sub, "vruntime_delta")
    almost(vruntime_delta(10, 1024), 10.0, 1e-9, label="nice 0 (weight 1024)")
    almost(vruntime_delta(3, 2048), 1.5, 1e-9, label="weight 2048")
    # 10 * 1024 / 335 = 10240 / 335 = 30.5671...
    almost(vruntime_delta(10, 335), 10240 / 335, 1e-9, label="nice 5 (weight 335)")


@check("lottery maps each draw to the right job, walking names in sorted order")
def test_lottery_scripted(sub):
    lottery = has(sub, "lottery")
    # Names sorted: A (tickets 0..74), B (75..99). total = 100.
    # 0 -> A, 74 -> A, 75 -> B, 99 -> B.
    rng = ScriptedRng([0, 74, 75, 99])
    got = lottery({"B": 25, "A": 75}, 4, rng)
    equal(got, ["A", "A", "B", "B"])
    equal(rng.asked, [100, 100, 100, 100], label="calls to rng.randrange(total)")
    # Three jobs: A 1 (0), B 2 (1..2), C 3 (3..5). total = 6.
    rng = ScriptedRng([0, 1, 2, 3, 5])
    equal(lottery({"A": 1, "B": 2, "C": 3}, 5, rng), ["A", "B", "B", "C", "C"], label="three jobs")


@check("lottery with a seeded generator is reproducible and close to the ticket ratio")
def test_lottery_seeded(sub):
    lottery = has(sub, "lottery")
    tickets = {"A": 75, "B": 25}
    first = lottery(tickets, 10000, random.Random(0))
    again = lottery(tickets, 10000, random.Random(0))
    equal(first, again, label="same seed, same winners")
    counts = Counter(first)
    share = counts["A"] / 10000
    # Expected 0.75. The standard deviation of the share over 10000 draws is
    # sqrt(0.75 * 0.25 / 10000) = 0.0043, so 0.02 is a wide margin.
    almost(share, 0.75, 0.02, label="share of A over 10000 slices")


@check("stride_schedule produces the expected sequence and rejects zero tickets")
def test_stride_sequence(sub):
    stride_schedule = has(sub, "stride_schedule")
    # Tickets A 100, B 50, C 250 -> strides 10000//100 = 100, 200, 40. Passes start 0.
    # 1 A (A=100) 2 B (B=200) 3 C (C=40) 4 C (80) 5 C (120)
    # 6 A (100 < 120, A=200) 7 C (120 -> 160) 8 C (200)
    # 9 all tied at 200 -> A (300) 10 B (200 ties C 200, B first -> 400)
    equal("".join(stride_schedule({"A": 100, "B": 50, "C": 250}, 10)), "ABCCCACCAB")
    try:
        stride_schedule({"A": 0, "B": 5}, 3)
    except ValueError:
        return
    except NotImplementedError:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"zero tickets should raise ValueError, got {type(exc).__name__}")
    fail("zero tickets should raise ValueError, but the call returned")


@check("stride_schedule hits the ticket ratio exactly over whole periods")
def test_stride_ratio(sub):
    stride_schedule = has(sub, "stride_schedule")
    # After 8 slices every pass is 200 again: A ran 2, B ran 1, C ran 5.
    # Ten such periods (80 slices) give A 20, B 10, C 50.
    got = Counter(stride_schedule({"A": 100, "B": 50, "C": 250}, 80))
    equal(dict(got), {"A": 20, "B": 10, "C": 50})
    equal("".join(stride_schedule({"A": 1, "B": 1}, 4)), "ABAB", label="equal tickets alternate")
    equal(stride_schedule({"A": 3}, 3), ["A", "A", "A"], label="one job")


@check("cfs alternates equal-weight jobs, and a longer slice gives longer turns")
def test_cfs_equal(sub):
    cfs = has(sub, "cfs")
    # Both nice 0, vruntime grows 1.0 per tick. A, B tie at 0 -> A first (name).
    # A 0-1 (A=1). B 1-2 (B=1). Tie again -> A 2-3. B 3-4.
    jobs = [J(sub, "B", 0, 2), J(sub, "A", 0, 2)]
    equal(cfs(jobs, {}), [("A", 0, 1), ("B", 1, 2), ("A", 2, 3), ("B", 3, 4)])
    # slice_len 2, bursts 6: A 0-2, B 2-4, A 4-6, B 6-8, A 8-10, B 10-12.
    jobs = [J(sub, "A", 0, 6), J(sub, "B", 0, 6)]
    equal(cfs(jobs, {}, slice_len=2),
          [("A", 0, 2), ("B", 2, 4), ("A", 4, 6), ("B", 6, 8), ("A", 8, 10), ("B", 10, 12)])


@check("cfs gives a heavier job more turns: nice 0 against nice 5")
def test_cfs_weighted(sub):
    cfs = has(sub, "cfs")
    # A weight 1024: +1.0 per tick. B weight 335: +1024/335 = 3.0567 per tick.
    # t0 tie -> A (A=1). t1 B(0)<A(1) -> B (B=3.0567). t2 A=1 -> 2. t3 A 2 -> 3.
    # t4 A 3 < 3.0567 -> A (4). t5 B 3.0567 < 4 -> B (6.1134).
    # t6 A 4->5, t7 5->6, t8 6 < 6.1134 -> A (7). t9 B 6.1134 < 7 -> B.
    equal(cfs([J(sub, "A", 0, 40), J(sub, "B", 0, 40)], {"B": 5})[:6],
          [("A", 0, 1), ("B", 1, 2), ("A", 2, 5), ("B", 5, 6), ("A", 6, 9), ("B", 9, 10)])


@check("cfs long-run CPU shares follow the weights")
def test_cfs_share(sub):
    cfs = has(sub, "cfs")
    jobs = [J(sub, "A", 0, 5000), J(sub, "B", 0, 5000)]
    line = cfs(jobs, {"B": 5})
    # Stop counting at tick 2000, well before either job can finish.
    ran = {"A": 0, "B": 0}
    for name, start, end in line:
        ran[name] += max(0, min(end, 2000) - min(start, 2000))
    # B's share should be 335 / (1024 + 335) = 0.2465.
    almost(ran["B"] / 2000, 335 / 1359, 0.005, label="share of B in the first 2000 ticks")


@check("cfs starts a late arrival at min_vruntime so it cannot hog the CPU")
def test_cfs_late(sub):
    cfs = has(sub, "cfs")
    jobs = [J(sub, "A", 0, 10), J(sub, "B", 5, 3)]
    # A runs ticks 0-4 alone, vruntime 5.0 at t=5. B arrives with min_vruntime 5.0.
    # t5 tie (5, 5) -> A (6). t6 B(5) -> 6. t7 tie -> A (7). t8 B -> 7.
    # t9 tie -> A (8). t10 B -> 8 (B done: 3 ticks). Then A runs 11-13 (rem 2).
    # Starting B at 0 would instead give B ticks 5-8 back to back.
    equal(cfs(jobs, {}),
          [("A", 0, 6), ("B", 6, 7), ("A", 7, 8), ("B", 8, 9), ("A", 9, 10),
           ("B", 10, 11), ("A", 11, 13)])
