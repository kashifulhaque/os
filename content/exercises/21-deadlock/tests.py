"""Checks for the deadlock exercise."""

import copy
import threading

from oscheck import check, equal, fail, has

# The classic five-process, three-resource example (resources A, B, C).
AVAILABLE = [3, 3, 2]
MAX_NEED = [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]
ALLOCATION = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]
# Remaining need = max - allocation:
#   P0 (7,4,3)  P1 (1,2,2)  P2 (6,0,0)  P3 (0,1,1)  P4 (4,3,1)


def state():
    return copy.deepcopy(AVAILABLE), copy.deepcopy(MAX_NEED), copy.deepcopy(ALLOCATION)


def call_with_timeout(fn, *args, timeout=10):
    box = {}

    def runner():
        try:
            box["value"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001
            box["error"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        fail(f"{getattr(fn, '__name__', 'your function')} did not finish within {timeout} seconds")
    if "error" in box:
        raise box["error"]
    return box["value"]


def assert_valid_cycle(graph, cycle, label):
    if not cycle:
        fail(f"{label}: expected a cycle as a non-empty list, got {cycle!r}")
    if len(set(cycle)) != len(cycle):
        fail(f"{label}: the cycle {cycle!r} repeats a node")
    for a, b in zip(cycle, cycle[1:] + cycle[:1]):
        if b not in graph.get(a, []):
            fail(f"{label}: {cycle!r} is not a cycle, because there is no edge {a!r} -> {b!r}")


@check("wait_for_graph links each thread to the owners of the locks it wants")
def test_wait_for_graph(sub):
    wait_for_graph = has(sub, "wait_for_graph")
    equal(
        wait_for_graph({"L1": "A", "L2": "B"}, {"A": ["L2"], "B": ["L1"]}),
        {"A": ["B"], "B": ["A"]},
        label="two threads, each wanting the other's lock",
    )
    # A holds L1, B holds L2, C holds L3. A wants L2 and L3. B wants L3. C wants a
    # free lock (L9), so C waits for nobody. D holds nothing and wants L1.
    got = wait_for_graph(
        {"L1": "A", "L2": "B", "L3": "C"},
        {"A": ["L2", "L3"], "B": ["L3"], "C": ["L9"], "D": ["L1"]},
    )
    equal(got, {"A": ["B", "C"], "B": ["C"], "C": [], "D": ["A"]}, label="four threads")
    # A thread that holds a lock but waits for nothing still appears.
    equal(wait_for_graph({"L1": "A"}, {}), {"A": []}, label="holder with no wants")


@check("find_cycle returns None for graphs without a cycle")
def test_no_cycle(sub):
    find_cycle = has(sub, "find_cycle")
    equal(find_cycle({}), None, label="empty graph")
    equal(find_cycle({"A": ["B"], "B": ["C"], "C": []}), None, label="a chain")
    # A diamond joins two paths at D. Visiting D twice is not a cycle.
    diamond = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
    equal(find_cycle(diamond), None, label="a diamond")
    equal(find_cycle({"A": ["B"]}), None, label="a node that appears only as a target")


@check("find_cycle finds two-node, self, and longer cycles, even behind a tail")
def test_cycles(sub):
    find_cycle = has(sub, "find_cycle")
    g = {"A": ["B"], "B": ["A"]}
    assert_valid_cycle(g, find_cycle(g), "two-node cycle")
    g = {"A": ["A"]}
    equal(find_cycle(g), ["A"], label="a thread waiting for itself")
    g = {"A": ["B"], "B": ["C"], "C": ["D"], "D": ["B"]}
    cycle = find_cycle(g)
    assert_valid_cycle(g, cycle, "cycle behind a tail")
    equal(sorted(cycle), ["B", "C", "D"], label="the tail node A is not part of the cycle")
    # Two components: an acyclic one first, a cyclic one second.
    g = {"X": ["Y"], "Y": [], "P": ["Q"], "Q": ["R"], "R": ["P"]}
    cycle = find_cycle(g)
    assert_valid_cycle(g, cycle, "second component")
    equal(sorted(cycle), ["P", "Q", "R"], label="members of the cycle in the second component")
    # A wait-for graph from the lock table feeds straight into find_cycle.
    wait_for_graph = has(sub, "wait_for_graph")
    g = wait_for_graph({"L1": "A", "L2": "B", "L3": "C"}, {"A": ["L2"], "B": ["L3"], "C": ["L1"]})
    cycle = find_cycle(g)
    assert_valid_cycle(g, cycle, "three-thread deadlock")
    equal(sorted(cycle), ["A", "B", "C"], label="threads in the three-way deadlock")


@check("is_safe finds a safe sequence for the classic five-process state")
def test_safe_state(sub):
    is_safe = has(sub, "is_safe")
    available, max_need, allocation = state()
    order = is_safe(available, max_need, allocation)
    if order is None:
        fail("the textbook state is safe (for example P1, P3, P4, P0, P2), but is_safe returned None")
    equal(sorted(order), [0, 1, 2, 3, 4], label="the sequence must list every process once")
    # Replay the sequence: each process's remaining need must fit in the work vector.
    work = list(available)
    for i in order:
        need = [m - a for m, a in zip(max_need[i], allocation[i])]
        if any(n > w for n, w in zip(need, work)):
            fail(f"in {order}, process P{i} needs {need} but only {work} is free at that point")
        work = [w + a for w, a in zip(work, allocation[i])]
    # Worked by hand: work (3,3,2) -> P1 -> (5,3,2) -> P3 -> (7,4,3) -> P0 -> (7,5,3)
    # -> P2 -> (10,5,5) -> P4 -> (10,5,7), which is the total of each resource.
    equal(work, [10, 5, 7], label="work vector after the whole sequence (totals 10, 5, 7)")
    equal(order, [1, 3, 0, 2, 4], label="the sequence from 'lowest-numbered process that fits, each time'")
    equal((available, max_need, allocation), state(), label="inputs must not be modified")


@check("is_safe returns None for an unsafe state")
def test_unsafe_state(sub):
    is_safe = has(sub, "is_safe")
    # Textbook state after P1 got (1,0,2) and P0 got (0,2,0): nobody's need fits in (2,1,0).
    allocation = [[0, 3, 0], [3, 0, 2], [3, 0, 2], [2, 1, 1], [0, 0, 2]]
    equal(is_safe([2, 1, 0], MAX_NEED, allocation), None, label="unsafe state")
    # One resource, two processes, each holding 1 and needing 2 with 0 free: deadlock-bound.
    equal(is_safe([0], [[2], [2]], [[1], [1]]), None, label="two processes each need one more unit")
    # Same, but 1 unit free: one finishes, returns its 2 units, the other finishes.
    equal(is_safe([1], [[2], [2]], [[1], [1]]), [0, 1], label="one free unit makes it safe")
    equal(is_safe([0], [], []), [], label="no processes")


@check("request_resources grants safe requests and refuses unavailable or unsafe ones")
def test_requests(sub):
    request_resources = has(sub, "request_resources")
    available, max_need, allocation = state()
    # P1 asks for (1,0,2): within need (1,2,2) and available (3,3,2); the result is safe.
    equal(request_resources(available, max_need, allocation, 1, [1, 0, 2]), True, label="P1 requests (1,0,2)")
    equal((available, max_need, allocation), state(), label="inputs must not be modified")
    # After that grant, available is (2,3,0) and P1 holds (3,0,2).
    available2 = [2, 3, 0]
    allocation2 = copy.deepcopy(ALLOCATION)
    allocation2[1] = [3, 0, 2]
    equal(request_resources(available2, max_need, allocation2, 4, [3, 3, 0]), False, label="P4 requests (3,3,0): only (2,3,0) is free")
    # P0 asks for (0,2,0): available, but granting it leaves available (2,1,0): unsafe.
    equal(request_resources(available2, max_need, allocation2, 0, [0, 2, 0]), False, label="P0 requests (0,2,0): unsafe")
    equal(request_resources(available2, max_need, allocation2, 3, [0, 1, 1]), False, label="P3 requests (0,1,1): not enough C free")
    # Asking for more than the declared maximum is an error, not a refusal.
    try:
        request_resources(available, max_need, allocation, 3, [1, 0, 0])
    except ValueError:
        return
    fail("P3 has maximum (2,2,2) and holds (2,1,1), so its remaining need in A is 0; asking for (1,0,0) should raise ValueError")


@check("fork_order sends every philosopher to the lower-numbered fork first")
def test_fork_order(sub):
    fork_order = has(sub, "fork_order")
    equal([fork_order(i, 5) for i in range(5)], [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)], label="five philosophers")
    equal([fork_order(i, 2) for i in range(2)], [(0, 1), (0, 1)], label="two philosophers share both forks")
    equal(fork_order(2, 3), (0, 2), label="the last of three philosophers")


def _has_cycle(adj):
    """A small independent cycle finder for the deadlock-freedom check."""
    colour = {}

    def visit(u):
        colour[u] = 1
        for v in adj.get(u, []):
            if colour.get(v) == 1 or (colour.get(v) is None and visit(v)):
                return True
        colour[u] = 2
        return False

    return any(colour.get(u) is None and visit(u) for u in list(adj))


def _can_deadlock(order_of, n):
    """Can some set of philosophers each hold their first fork and wait for a second?

    Try every set S of philosophers that hold their first fork (no two may hold
    the same fork). Everyone else wants their first fork. Build who-waits-for-whom
    and look for a cycle.
    """
    for mask in range(1, 1 << n):
        holders = [i for i in range(n) if mask >> i & 1]
        owner = {}
        ok = True
        for i in holders:
            first = order_of(i)[0]
            if first in owner:
                ok = False
                break
            owner[first] = i
        if not ok:
            continue
        adj = {}
        for i in range(n):
            # A holder waits for its second fork; everyone else for its first.
            wanted = order_of(i)[1] if i in holders else order_of(i)[0]
            if wanted in owner and owner[wanted] != i:
                adj[i] = [owner[wanted]]
        if _has_cycle(adj):
            return True
    return False


@check("with your fork_order no set of philosophers can wait on each other in a cycle")
def test_no_deadlock_possible(sub):
    fork_order = has(sub, "fork_order")
    # Sanity check of this test: the naive "left fork, then right fork" order does deadlock.
    for n in (3, 4, 5):
        if not _can_deadlock(lambda i, n=n: (i, (i + 1) % n), n):
            fail("internal error: the naive order should be able to deadlock")
    for n in (2, 3, 4, 5, 6):
        order = [tuple(fork_order(i, n)) for i in range(n)]
        for i, (a, b) in enumerate(order):
            if {a, b} != {i, (i + 1) % n}:
                fail(f"philosopher {i} of {n} must use forks {i} and {(i + 1) % n}, but fork_order gave {(a, b)}")
        if _can_deadlock(lambda i, order=order: order[i], n):
            fail(
                f"with {n} philosophers, your order {order} lets every philosopher hold one fork "
                "while waiting for the next one in a circle"
            )


@check("dine runs five philosophers on real locks and everyone finishes every meal")
def test_dine(sub):
    dine = has(sub, "dine")
    equal(call_with_timeout(dine, 5, 40), [40] * 5, label="dine(5, 40)")
    equal(call_with_timeout(dine, 2, 25), [25, 25], label="dine(2, 25)")
    equal(call_with_timeout(dine, 7, 10), [10] * 7, label="dine(7, 10)")
    equal(call_with_timeout(dine, 3, 0), [0, 0, 0], label="dine(3, 0)")
