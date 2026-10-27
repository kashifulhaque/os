"""Checks for the page-replacement exercise."""

import random

from oscheck import check, equal, fail, has

CLASSIC = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]


def _random_strings():
    rng = random.Random(0)
    return [[rng.randrange(6) for _ in range(rng.randrange(10, 40))] for _ in range(40)]


@check("fifo_faults counts cold misses and evicts the oldest arrival")
def test_fifo(sub):
    fifo_faults = has(sub, "fifo_faults")
    equal(fifo_faults([], 3), 0, label="empty string")
    equal(fifo_faults([1, 2, 3, 1, 2, 3], 3), 3, label="three pages fit in three frames: only cold misses")
    # Frames 2: 1 f, 2 f, 3 f (evict 1), 1 f (evict 2), 2 f (evict 3) -> 5 faults.
    equal(fifo_faults([1, 2, 3, 1, 2], 2), 5, label="[1,2,3,1,2] with 2 frames")
    # A hit does not refresh FIFO order: 1 f, 2 f, 1 hit, 3 f (evict 1, the oldest), 1 f (evict 2) -> 4.
    equal(fifo_faults([1, 2, 1, 3, 1], 2), 4, label="[1,2,1,3,1] with 2 frames")


@check("lru_faults evicts the least recently used page")
def test_lru(sub):
    lru_faults = has(sub, "lru_faults")
    equal(lru_faults([], 3), 0, label="empty string")
    # 1 f, 2 f, 1 hit, 3 f (evict 2, since 1 was just used), 1 hit -> 3 faults.
    equal(lru_faults([1, 2, 1, 3, 1], 2), 3, label="[1,2,1,3,1] with 2 frames")
    # 1 f, 2 f, 1 hit, 3 f (evict 2), 2 f (evict 1) -> 4 faults.
    equal(lru_faults([1, 2, 1, 3, 2], 2), 4, label="[1,2,1,3,2] with 2 frames")


@check("FIFO and LRU give 9 and 10 faults on the classic string with 3 frames")
def test_classic_3(sub):
    fifo_faults, lru_faults = has(sub, "fifo_faults"), has(sub, "lru_faults")
    opt_faults = has(sub, "opt_faults")
    equal(fifo_faults(CLASSIC, 3), 9, label="FIFO, 3 frames")
    equal(lru_faults(CLASSIC, 3), 10, label="LRU, 3 frames")
    equal(opt_faults(CLASSIC, 3), 7, label="OPT, 3 frames")


@check("Belady's anomaly: FIFO gets worse from 3 to 4 frames; LRU and OPT improve")
def test_belady(sub):
    fifo_faults, lru_faults = has(sub, "fifo_faults"), has(sub, "lru_faults")
    opt_faults = has(sub, "opt_faults")
    equal(fifo_faults(CLASSIC, 4), 10, label="FIFO, 4 frames")
    equal(lru_faults(CLASSIC, 4), 8, label="LRU, 4 frames")
    equal(opt_faults(CLASSIC, 4), 6, label="OPT, 4 frames")


@check("opt_faults evicts the page used farthest in the future")
def test_opt(sub):
    opt_faults = has(sub, "opt_faults")
    # 2 frames on 1,2,3,1,2: 1 f, 2 f, 3 f (evict 2: next use of 1 is sooner? 1 at idx 3, 2 at idx 4 -> evict 2),
    # 1 hit, 2 f (evict 3, never used again) -> 4 faults.
    equal(opt_faults([1, 2, 3, 1, 2], 2), 4, label="[1,2,3,1,2] with 2 frames")
    # 3 frames on the textbook string: 6 faults (2, 3, 1, then 5, 4, and the final reload of 3).
    equal(opt_faults([2, 3, 2, 1, 5, 2, 4, 5, 3, 2, 5, 2], 3), 6, label="textbook string, 3 frames")
    equal(opt_faults([7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1], 3), 9,
          label="OSTEP/Silberschatz 20-reference string, 3 frames")


@check("clock_faults gives a second chance to pages whose reference bit is set")
def test_clock(sub):
    clock_faults = has(sub, "clock_faults")
    textbook = [2, 3, 2, 1, 5, 2, 4, 5, 3, 2, 5, 2]
    # Hand trace, 3 frames; slots shown as page:bit, hand after the step.
    # 2 f [2:1 _ _] h1 | 3 f [2:1 3:1 _] h2 | 2 hit | 1 f [2:1 3:1 1:1] h0
    # 5 f: bits clear 2,3,1 then slot 0 is replaced [5:1 3:0 1:0] h1
    # 2 f: slot 1 has bit 0 -> [5:1 2:1 1:0] h2 | 4 f: slot 2 -> [5:1 2:1 4:1] h0 | 5 hit
    # 3 f: clear 5,2,4, replace slot 0 [3:1 2:0 4:0] h1 | 2 hit [3:1 2:1 4:0]
    # 5 f: clear slot 1, replace slot 2 [3:1 2:0 5:1] h0 | 2 hit.  Faults: 8.
    equal(clock_faults(textbook, 3), 8, label="textbook string, 3 frames (FIFO 9, LRU 7, OPT 6)")
    equal(clock_faults([], 3), 0, label="empty string")
    equal(clock_faults([1, 2, 3, 1, 2, 3], 3), 3, label="working set fits: only cold misses")
    equal(clock_faults(CLASSIC, 3), 9, label="classic string, 3 frames")
    equal(clock_faults(CLASSIC, 4), 10, label="classic string, 4 frames")


@check("with one frame every policy faults whenever the page changes")
def test_one_frame(sub):
    names = ["fifo_faults", "lru_faults", "clock_faults", "opt_faults"]
    refs = [3, 3, 1, 1, 1, 2, 3, 3, 2]
    # First reference faults; then a fault at each change of page: 3|1|2|3|2 -> 5 faults.
    for name in names:
        equal(has(sub, name)(refs, 1), 5, label=f"{name}, 1 frame")


@check("enough frames means only cold misses; faults are bounded by length")
def test_bounds(sub):
    funcs = [has(sub, n) for n in ("fifo_faults", "lru_faults", "clock_faults", "opt_faults")]
    for refs in _random_strings():
        distinct = len(set(refs))
        for fn in funcs:
            got = fn(refs, 6)
            if got != distinct:
                fail(f"{fn.__name__}({refs}, 6) returned {got}, expected {distinct} (one cold miss per distinct page)")
            for frames in (1, 2, 3):
                got = fn(refs, frames)
                if not distinct <= got <= len(refs):
                    fail(f"{fn.__name__}({refs}, {frames}) returned {got}, which is outside {distinct}..{len(refs)}")


@check("OPT never faults more than any other policy; LRU never gets worse with more frames")
def test_properties(sub):
    fifo_faults, lru_faults = has(sub, "fifo_faults"), has(sub, "lru_faults")
    clock_faults, opt_faults = has(sub, "clock_faults"), has(sub, "opt_faults")
    for refs in _random_strings():
        for frames in (2, 3, 4):
            best = opt_faults(refs, frames)
            for fn in (fifo_faults, lru_faults, clock_faults):
                got = fn(refs, frames)
                if best > got:
                    fail(f"opt_faults({refs}, {frames}) = {best} but {fn.__name__} = {got}; OPT cannot be worse")
        for fn in (lru_faults, opt_faults):
            counts = [fn(refs, f) for f in range(1, 7)]
            if counts != sorted(counts, reverse=True):
                fail(f"{fn.__name__} faults for 1..6 frames on {refs} are {counts}; they must never increase")


@check("find_belady finds the anomaly for FIFO and none for LRU; compare_policies bundles the counts")
def test_find_belady(sub):
    find_belady, lru_faults = has(sub, "find_belady"), has(sub, "lru_faults")
    compare_policies = has(sub, "compare_policies")
    equal(find_belady(CLASSIC, 6), (3, 9, 10), label="find_belady(classic, 6)")
    equal(find_belady(CLASSIC, 3), None, label="find_belady(classic, 3) only tries f = 1, 2")
    equal(find_belady(CLASSIC, 6, lru_faults), None, label="LRU has no anomaly on the classic string")
    for refs in _random_strings():
        got = find_belady(refs, 7, lru_faults)
        if got is not None:
            fail(f"LRU is a stack algorithm and cannot show Belady's anomaly, but find_belady returned {got} on {refs}")
    equal(compare_policies(CLASSIC, 3), {"FIFO": 9, "LRU": 10, "Clock": 9, "OPT": 7}, label="compare_policies(classic, 3)")
    equal(compare_policies(CLASSIC, 4), {"FIFO": 10, "LRU": 8, "Clock": 10, "OPT": 6}, label="compare_policies(classic, 4)")
