"""Checks for the condition-variables-and-semaphores exercise.

Every check here asserts something that is true under every interleaving of the
threads. Timing is used in one safe direction only: "this thread is still
blocked after 0.2 seconds" can never fail a correct solution, and a wrong one
that does not block is caught almost every time. Every join has a timeout, and a
timeout fails the check instead of hanging it.
"""

import threading
import time

from oscheck import check, equal, fail, has

JOIN = 10  # seconds to wait for a thread that should finish


def start(fn, *args):
    """Start a daemon thread running fn(*args). Its exception, if any, is kept."""
    box = {"error": None, "result": None}

    def runner():
        try:
            box["result"] = fn(*args)
        except BaseException as exc:  # noqa: BLE001
            box["error"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.box = box
    t.start()
    return t


def finish(t, what):
    """Join `t`, failing if it hangs or raised."""
    t.join(JOIN)
    if t.is_alive():
        fail(f"{what} did not finish within {JOIN} seconds (a lost wakeup, or it waits forever?)")
    if isinstance(t.box["error"], NotImplementedError):
        raise t.box["error"]
    if t.box["error"] is not None:
        fail(f"{what} raised {type(t.box['error']).__name__}: {t.box['error']}")
    return t.box["result"]


def still_blocked(t, seconds=0.2):
    t.join(seconds)
    return t.is_alive()


@check("BoundedBuffer is first in, first out and len() counts the items inside")
def test_buffer_fifo(sub):
    BoundedBuffer = has(sub, "BoundedBuffer")
    buf = BoundedBuffer(3)
    equal(len(buf), 0, label="len of an empty buffer")
    for x in ("a", "b", "c"):
        buf.put(x)
    equal(len(buf), 3, label="len after three puts")
    equal([buf.get(), buf.get()], ["a", "b"], label="first two gets")
    buf.put("d")
    equal([buf.get(), buf.get()], ["c", "d"], label="remaining gets")
    equal(len(buf), 0, label="len when drained")
    try:
        BoundedBuffer(0)
    except ValueError:
        return
    fail("BoundedBuffer(0) should raise ValueError")


@check("put blocks while the buffer is full and resumes after a get")
def test_put_blocks(sub):
    BoundedBuffer = has(sub, "BoundedBuffer")
    buf = BoundedBuffer(2)
    buf.put("a")
    buf.put("b")
    t = start(buf.put, "c")
    if not still_blocked(t):
        fail("put() on a full buffer (capacity 2, 2 items) returned instead of blocking")
    equal(len(buf), 2, label="len while a put is blocked")
    equal(buf.get(), "a", label="get that makes room")
    finish(t, "the blocked put()")
    equal([buf.get(), buf.get()], ["b", "c"], label="items after the blocked put finished")


@check("get blocks while the buffer is empty and returns the item once one arrives")
def test_get_blocks(sub):
    BoundedBuffer = has(sub, "BoundedBuffer")
    buf = BoundedBuffer(2)
    t = start(buf.get)
    if not still_blocked(t):
        fail("get() on an empty buffer returned instead of blocking")
    buf.put("x")
    equal(finish(t, "the blocked get()"), "x", label="item returned by the blocked get")
    equal(len(buf), 0, label="len after the item was taken")


@check("waiters re-check the condition: two consumers, one item, nobody takes from an empty buffer")
def test_recheck_after_wakeup(sub):
    BoundedBuffer = has(sub, "BoundedBuffer")
    buf = BoundedBuffer(4)
    t1 = start(buf.get)
    t2 = start(buf.get)
    time.sleep(0.1)  # let both consumers reach wait() (a correct solution works either way)
    buf.put("x")
    # Exactly one consumer can get the item. The other must go back to waiting,
    # even if a notify_all woke it, so it must re-test the condition in a loop.
    deadline = time.time() + JOIN
    while t1.is_alive() and t2.is_alive() and time.time() < deadline:
        time.sleep(0.005)
    time.sleep(0.2)
    done = [t for t in (t1, t2) if not t.is_alive()]
    for t in (t1, t2):
        if t.box["error"] is not None:
            fail(
                f"a consumer raised {type(t.box['error']).__name__}: {t.box['error']}. "
                "It probably woke up and took from an empty buffer: wait in a `while` loop, not an `if`."
            )
    equal(len(done), 1, label="consumers finished after one item was put")
    buf.put("y")
    finish(t1, "consumer 1")
    finish(t2, "consumer 2")
    equal(sorted([t1.box["result"], t2.box["result"]]), ["x", "y"], label="items the two consumers received")


@check("Semaphore counts: acquire lowers, release raises, and acquire blocks at zero")
def test_semaphore_basic(sub):
    Semaphore = has(sub, "Semaphore")
    sem = Semaphore(2)
    sem.acquire()
    equal(sem.try_acquire(), True, label="second unit of Semaphore(2)")
    equal(sem.try_acquire(), False, label="third unit of Semaphore(2)")
    t = start(sem.acquire)
    if not still_blocked(t):
        fail("acquire() on a semaphore at 0 returned instead of blocking")
    sem.release()
    finish(t, "the blocked acquire()")
    equal(sem.try_acquire(), False, label="count after the waiter took the released unit")
    # A semaphore starting at 0 is a signal: acquire waits for a release.
    sig = Semaphore(0)
    t = start(sig.acquire)
    if not still_blocked(t):
        fail("acquire() on Semaphore(0) returned instead of blocking")
    sig.release()
    finish(t, "acquire() on Semaphore(0)")
    # Releases may exceed the starting value.
    sem2 = Semaphore(0)
    sem2.release()
    sem2.release()
    equal([sem2.try_acquire(), sem2.try_acquire(), sem2.try_acquire()], [True, True, False], label="two releases, three tries")
    try:
        Semaphore(-1)
    except ValueError:
        return
    fail("Semaphore(-1) should raise ValueError")


@check("Semaphore(1) works as a mutex and Semaphore(3) never admits more than 3 threads")
def test_semaphore_limits(sub):
    Semaphore = has(sub, "Semaphore")
    # Semaphore(1) protecting a read-yield-write: no update may be lost.
    mutex = Semaphore(1)
    total = [0]

    def bump():
        for _ in range(100):
            mutex.acquire()
            try:
                v = total[0]
                time.sleep(0)  # give other threads a chance to run mid-update
                total[0] = v + 1
            finally:
                mutex.release()

    threads = [start(bump) for _ in range(6)]
    for t in threads:
        finish(t, "a worker")
    equal(total[0], 600, label="total after 6 threads x 100 protected increments")

    sem = Semaphore(3)
    guard = threading.Lock()
    state = {"active": 0, "max": 0, "entered": 0}

    def visit():
        sem.acquire()
        try:
            with guard:
                state["active"] += 1
                state["entered"] += 1
                state["max"] = max(state["max"], state["active"])
            time.sleep(0.002)
            with guard:
                state["active"] -= 1
        finally:
            sem.release()

    threads = [start(visit) for _ in range(9)]
    for t in threads:
        finish(t, "a visitor")
    equal(state["entered"], 9, label="threads that got through")
    if state["max"] > 3:
        fail(f"Semaphore(3) let {state['max']} threads in at once; expected at most 3")


@check("ReadWriteLock lets several readers hold the lock at the same time")
def test_rw_readers_share(sub):
    ReadWriteLock = has(sub, "ReadWriteLock")
    lock = ReadWriteLock()
    barrier = threading.Barrier(3, timeout=JOIN)

    def reader():
        lock.acquire_read()
        try:
            barrier.wait()  # passes only if all three readers are inside at once
        finally:
            lock.release_read()

    threads = [start(reader) for _ in range(3)]
    for t in threads:
        t.join(JOIN + 2)
        if t.is_alive():
            fail("readers did not finish")
        if isinstance(t.box["error"], NotImplementedError):
            raise t.box["error"]
        if t.box["error"] is not None:
            fail("three readers could not hold the lock together (is acquire_read letting readers in while others are inside?)")


@check("ReadWriteLock excludes writers: a writer waits for readers, readers wait for a writer")
def test_rw_exclusion(sub):
    ReadWriteLock = has(sub, "ReadWriteLock")
    lock = ReadWriteLock()
    lock.acquire_read()
    w = start(lambda: (lock.acquire_write(), lock.release_write()))
    if not still_blocked(w):
        fail("acquire_write() returned while a reader was still inside")
    lock.release_read()
    finish(w, "the waiting writer")

    lock.acquire_write()
    r = start(lambda: (lock.acquire_read(), lock.release_read()))
    if not still_blocked(r):
        fail("acquire_read() returned while a writer was inside")
    w2 = start(lambda: (lock.acquire_write(), lock.release_write()))
    if not still_blocked(w2):
        fail("a second acquire_write() returned while a writer was inside")
    lock.release_write()
    finish(r, "the waiting reader")
    finish(w2, "the second writer")

    # Stress: writers update two fields one after the other; readers must never
    # see them disagree, and a writer must never overlap anyone.
    shared = {"a": 0, "b": 0}
    guard = threading.Lock()
    inside = {"readers": 0, "writers": 0}
    problems = []

    def writer():
        for _ in range(60):
            lock.acquire_write()
            try:
                with guard:
                    inside["writers"] += 1
                    if inside["writers"] != 1 or inside["readers"] != 0:
                        problems.append(f"writer saw {inside}")
                shared["a"] += 1
                time.sleep(0)
                shared["b"] += 1
                with guard:
                    inside["writers"] -= 1
            finally:
                lock.release_write()

    def reader():
        for _ in range(60):
            lock.acquire_read()
            try:
                with guard:
                    inside["readers"] += 1
                    if inside["writers"] != 0:
                        problems.append(f"reader saw {inside}")
                a = shared["a"]
                time.sleep(0)
                b = shared["b"]
                if a != b:
                    problems.append(f"reader saw a={a}, b={b}")
                with guard:
                    inside["readers"] -= 1
            finally:
                lock.release_read()

    threads = [start(writer) for _ in range(2)] + [start(reader) for _ in range(4)]
    for t in threads:
        finish(t, "a stress thread")
    equal(problems[:3], [], label="overlaps or torn reads seen")
    equal((shared["a"], shared["b"]), (120, 120), label="final field values after 2 writers x 60 writes")


def _instrumented(sub):
    """Replace sub.BoundedBuffer by a subclass that records how full it gets."""
    Original = sub.BoundedBuffer
    record = {"max_len": 0, "made": 0, "capacity": None}

    class Watched(Original):
        def __init__(self, capacity):
            super().__init__(capacity)
            record["made"] += 1
            record["capacity"] = capacity

        def put(self, item):
            super().put(item)
            record["max_len"] = max(record["max_len"], len(self))

        def get(self):
            before = len(self)
            record["max_len"] = max(record["max_len"], before)
            return super().get()

    sub.BoundedBuffer = Watched
    return Original, record


def _check_delivery(sub, n_producers, n_consumers, per_producer, capacity):
    run_pipeline = has(sub, "run_pipeline")
    has(sub, "BoundedBuffer")
    Original, record = _instrumented(sub)
    try:
        out = start(run_pipeline, n_producers, n_consumers, per_producer, capacity)
        result = finish(out, f"run_pipeline({n_producers}, {n_consumers}, {per_producer}, {capacity})")
    finally:
        sub.BoundedBuffer = Original
    label = f"run_pipeline({n_producers}, {n_consumers}, {per_producer}, {capacity})"
    if record["made"] != 1:
        fail(f"{label} should build exactly one BoundedBuffer(capacity); it built {record['made']}")
    if not isinstance(result, (list, tuple)) or len(result) != n_consumers:
        fail(f"{label} should return one list per consumer ({n_consumers}); got {result!r}")
    everything = sorted(item for consumer in result for item in consumer)
    want = sorted((p, s) for p in range(n_producers) for s in range(per_producer))
    equal(len(everything), len(want), label=f"{label}: number of items delivered")
    equal(everything, want, label=f"{label}: each item delivered exactly once")
    for c, items in enumerate(result):
        last = {}
        for p, s in items:
            if p in last and s <= last[p]:
                fail(f"{label}: consumer {c} got item ({p}, {s}) after ({p}, {last[p]}); order per producer must be kept")
            last[p] = s
    if record["max_len"] > capacity:
        fail(f"{label}: the buffer held {record['max_len']} items, more than its capacity {capacity}")


@check("run_pipeline delivers every item exactly once, in order per producer, within capacity")
def test_pipeline_basic(sub):
    run_pipeline = has(sub, "run_pipeline")
    equal(
        finish(start(run_pipeline, 1, 1, 3, 2), "run_pipeline(1, 1, 3, 2)"),
        [[(0, 0), (0, 1), (0, 2)]],
        label="one producer, one consumer",
    )
    _check_delivery(sub, 3, 2, 40, 3)


@check("run_pipeline survives capacity 1, many producers and consumers, and zero items")
def test_pipeline_stress(sub):
    run_pipeline = has(sub, "run_pipeline")
    _check_delivery(sub, 4, 4, 25, 1)
    _check_delivery(sub, 5, 1, 20, 2)
    _check_delivery(sub, 1, 5, 30, 4)
    equal(
        finish(start(run_pipeline, 2, 3, 0, 2), "run_pipeline with no items"),
        [[], [], []],
        label="no items to deliver",
    )
