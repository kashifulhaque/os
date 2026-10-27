"""Deadlock: wait-for graphs, the Banker's algorithm, and lock ordering."""

from __future__ import annotations

import threading
import time


# ------------------------------------------------------------ wait-for graph


def wait_for_graph(owner, wants):
    """Build the wait-for graph of a set of threads and locks.

    `owner` maps each held lock to the thread holding it. `wants` maps each
    thread to the locks it is waiting for. Thread T waits for thread U when T
    wants a lock that U holds. Returns a dict that maps every thread (anyone in
    `wants` or in `owner.values()`) to the sorted list of threads it waits for.
    A lock that nobody holds blocks nobody.

    Example: owner {"L1": "A", "L2": "B"}, wants {"A": ["L2"], "B": ["L1"]}
    gives {"A": ["B"], "B": ["A"]}.
    """
    raise NotImplementedError


def find_cycle(graph):
    """Return a cycle in a directed graph as a list of nodes, or None.

    `graph` maps a node to the list of nodes it points to. Some nodes may appear
    only as targets. For the cycle [a, b, c], the edges are a->b, b->c, c->a.
    A node that points to itself is the cycle [a].

    Hint: depth-first search, marking each node unseen, on the current path, or
    finished. An edge back to a node on the current path closes a cycle.
    """
    raise NotImplementedError


# ------------------------------------------------------------- Banker's algorithm


def is_safe(available, max_need, allocation):
    """The Banker's safety algorithm.

    `available[j]` is the number of free units of resource j. `max_need[i][j]` is
    the most of resource j that process i will ever hold. `allocation[i][j]` is
    what it holds now. Returns a safe sequence (a list of process numbers in an
    order that lets every process finish) or None if the state is unsafe.

    Remaining need is max_need - allocation. Start with work = available. Pick
    the lowest-numbered unfinished process whose remaining need fits in work,
    add its allocation to work, and repeat. If no unfinished process fits, the
    state is unsafe.
    """
    raise NotImplementedError


def request_resources(available, max_need, allocation, tid, request):
    """Should the Banker grant `request` from process `tid`?

    Raises ValueError if the request exceeds the process's remaining need.
    Returns False if it exceeds what is available (the process must wait), or if
    granting it would leave an unsafe state. Otherwise True. The inputs are not
    modified: test the pretend-grant on copies.
    """
    raise NotImplementedError


# ------------------------------------------------------ dining philosophers


def fork_order(i, n):
    """The order in which philosopher `i` of `n` picks up forks.

    Philosopher i sits between fork i and fork (i + 1) % n. Pick up the
    lower-numbered fork first. That one rule is a global lock order.

    Example: fork_order(4, 5) is (0, 4), and fork_order(1, 5) is (1, 2).
    """
    raise NotImplementedError


def dine(n, meals):
    """Run `n` philosophers as real threads; each eats `meals` times.

    Each fork is a threading.Lock. A philosopher takes both forks in the order
    given by fork_order, eats (adds one to its own meal count), and puts them
    back. Between the two pickups, call time.sleep(0) to give other threads a
    chance to run. Join every thread with a timeout and raise RuntimeError if
    one is still alive. Returns a list with the number of meals each ate.

    Example: dine(5, 20) returns [20, 20, 20, 20, 20].
    """
    raise NotImplementedError


if __name__ == "__main__":
    # A deadlock: A holds L1 and wants L2, B holds L2 and wants L1.
    graph = wait_for_graph({"L1": "A", "L2": "B"}, {"A": ["L2"], "B": ["L1"]})
    print("wait-for graph:", graph)
    print("cycle:", find_cycle(graph))

    # The classic five-process, three-resource example (resources A, B, C).
    available = [3, 3, 2]
    max_need = [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]
    allocation = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]
    print("safe sequence:", is_safe(available, max_need, allocation))
    print("P1 asks (1,0,2):", request_resources(available, max_need, allocation, 1, [1, 0, 2]))
    print("P4 asks (3,3,0):", request_resources(available, max_need, allocation, 4, [3, 3, 0]))

    print("fork order for 5 philosophers:", [fork_order(i, 5) for i in range(5)])
    print("meals eaten:", dine(5, 20))
