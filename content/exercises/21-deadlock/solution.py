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

    Example: owner {"L1": "A", "L2": "B"}, wants {"A": ["L2"], "B": ["L1"]}
    gives {"A": ["B"], "B": ["A"]}.
    """
    graph = {}
    for thread in wants:
        graph[thread] = set()
    for thread in owner.values():
        graph.setdefault(thread, set())
    for thread, locks in wants.items():
        for lock in locks:
            if lock in owner:  # a lock nobody holds does not block anyone
                graph[thread].add(owner[lock])
    return {thread: sorted(targets) for thread, targets in graph.items()}


def find_cycle(graph):
    """Return a cycle in a directed graph as a list of nodes, or None.

    `graph` maps a node to the list of nodes it points to. Some nodes may appear
    only as targets. For the cycle [a, b, c], the edges are a->b, b->c, c->a.
    A node that points to itself is the cycle [a].
    """
    WHITE, GREY, BLACK = 0, 1, 2  # unseen, on the current path, finished
    colour = {}
    path = []

    def visit(node):
        colour[node] = GREY
        path.append(node)
        for nxt in graph.get(node, []):
            state = colour.get(nxt, WHITE)
            if state == GREY:
                # `nxt` is on the current path, so path[index:] closes a cycle.
                return path[path.index(nxt):]
            if state == WHITE:
                found = visit(nxt)
                if found is not None:
                    return found
        path.pop()
        colour[node] = BLACK
        return None

    for start in list(graph):
        if colour.get(start, WHITE) == WHITE:
            found = visit(start)
            if found is not None:
                return list(found)
    return None


# ------------------------------------------------------------- Banker's algorithm


def _fits(need, work):
    return all(n <= w for n, w in zip(need, work))


def is_safe(available, max_need, allocation):
    """The Banker's safety algorithm.

    `available[j]` is the number of free units of resource j. `max_need[i][j]` is
    the most of resource j that process i will ever hold. `allocation[i][j]` is
    what it holds now. Returns a safe sequence (a list of process numbers in an
    order that lets every process finish) or None if the state is unsafe.

    Always pick the lowest-numbered unfinished process whose remaining need fits
    in the work vector, then add its allocation back.
    """
    n = len(allocation)
    need = [[m - a for m, a in zip(max_need[i], allocation[i])] for i in range(n)]
    work = list(available)
    finished = [False] * n
    order = []
    while len(order) < n:
        for i in range(n):
            if not finished[i] and _fits(need[i], work):
                work = [w + a for w, a in zip(work, allocation[i])]
                finished[i] = True
                order.append(i)
                break
        else:
            return None  # nobody can finish: unsafe
    return order


def request_resources(available, max_need, allocation, tid, request):
    """Should the Banker grant `request` from process `tid`?

    Raises ValueError if the request exceeds the process's remaining need.
    Returns False if it exceeds what is available (the process must wait), or if
    granting it would leave an unsafe state. Otherwise True. The inputs are not
    modified.
    """
    need = [m - a for m, a in zip(max_need[tid], allocation[tid])]
    if not _fits(request, need):
        raise ValueError(f"process {tid} asks for {request}, more than its remaining need {need}")
    if not _fits(request, available):
        return False
    # Pretend to grant it, on copies, and test the resulting state.
    new_available = [a - r for a, r in zip(available, request)]
    new_allocation = [list(row) for row in allocation]
    new_allocation[tid] = [a + r for a, r in zip(new_allocation[tid], request)]
    return is_safe(new_available, max_need, new_allocation) is not None


# ------------------------------------------------------ dining philosophers


def fork_order(i, n):
    """The order in which philosopher `i` of `n` picks up forks.

    Philosopher i sits between fork i and fork (i + 1) % n. Pick up the
    lower-numbered fork first. That one rule is a global lock order.

    Example: fork_order(4, 5) is (0, 4), and fork_order(1, 5) is (1, 2).
    """
    a, b = i, (i + 1) % n
    return (a, b) if a < b else (b, a)


def dine(n, meals):
    """Run `n` philosophers as real threads; each eats `meals` times.

    Each fork is a threading.Lock. A philosopher takes both forks in the order
    given by fork_order, eats, and puts them back. Returns a list with the number
    of meals each philosopher ate.
    """
    forks = [threading.Lock() for _ in range(n)]
    eaten = [0] * n

    def philosopher(i):
        first, second = fork_order(i, n)
        for _ in range(meals):
            with forks[first]:
                time.sleep(0)  # a pause between forks, to invite a deadlock
                with forks[second]:
                    eaten[i] += 1

    threads = [threading.Thread(target=philosopher, args=(i,), daemon=True) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
        if t.is_alive():
            raise RuntimeError("philosophers are still waiting after 20 seconds: deadlock?")
    return eaten


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
