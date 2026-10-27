"""Condition variables and semaphores: a bounded buffer, a semaphore, and a
reader-writer lock, built on `threading.Condition`."""

from __future__ import annotations

import threading
from collections import deque  # a list also works; deque.popleft is O(1)


class BoundedBuffer:
    """A first-in, first-out queue that holds at most `capacity` items.

    put(item) blocks while the buffer is full. get() blocks while it is empty.
    len(buffer) is the number of items currently inside. A capacity below 1
    raises ValueError.

    Example: with capacity 2, put("a"), put("b") return at once, and a third
    put blocks until another thread calls get(), which returns "a".

    Hint: make one lock and two Conditions that share it, and wait inside a
    `while` loop that re-checks the condition.
    """

    def __init__(self, capacity):
        raise NotImplementedError

    def put(self, item):
        raise NotImplementedError

    def get(self):
        raise NotImplementedError

    def __len__(self):
        raise NotImplementedError


class Semaphore:
    """A counting semaphore built from a Condition (not threading.Semaphore).

    acquire() waits until the count is positive, then lowers it by one.
    try_acquire() does the same if the count is positive right now and returns
    True, or returns False without waiting. release() raises the count by one
    and wakes a waiter. A negative starting value raises ValueError.

    Example: Semaphore(2) lets two threads acquire; a third waits for a release.
    """

    def __init__(self, value=1):
        raise NotImplementedError

    def acquire(self):
        raise NotImplementedError

    def try_acquire(self):
        raise NotImplementedError

    def release(self):
        raise NotImplementedError


class ReadWriteLock:
    """Many readers at once, or one writer alone, never both.

    acquire_read / release_read bracket a read. acquire_write / release_write
    bracket a write. Readers may enter together. A writer waits until no reader
    and no other writer is inside. Readers wait while a writer is inside.
    """

    def __init__(self):
        raise NotImplementedError

    def acquire_read(self):
        raise NotImplementedError

    def release_read(self):
        raise NotImplementedError

    def acquire_write(self):
        raise NotImplementedError

    def release_write(self):
        raise NotImplementedError


def run_pipeline(n_producers, n_consumers, per_producer, capacity):
    """Move items from producers to consumers through a BoundedBuffer.

    Build the buffer with `BoundedBuffer(capacity)`. Producer p puts the tuples
    (p, 0), (p, 1), ... (p, per_producer - 1). Consumers run until the producers
    are finished and the buffer is drained; stop them with one `None` per
    consumer (a "poison pill"). Join every thread with a timeout and raise
    RuntimeError if one is still alive.

    Returns a list with one list per consumer: the items that consumer got, in
    the order it got them. Every item is delivered exactly once.

    Example: run_pipeline(1, 1, 3, 2) returns [[(0, 0), (0, 1), (0, 2)]].
    """
    raise NotImplementedError


if __name__ == "__main__":
    got = run_pipeline(n_producers=2, n_consumers=2, per_producer=5, capacity=2)
    everything = sorted(item for consumer in got for item in consumer)
    print("items delivered:", len(everything))
    print("all present exactly once:", everything == [(p, s) for p in range(2) for s in range(5)])

    sem = Semaphore(2)
    print("semaphore of 2:", sem.try_acquire(), sem.try_acquire(), sem.try_acquire())
    sem.release()
    print("after a release:", sem.try_acquire())

    rw = ReadWriteLock()
    rw.acquire_read()
    rw.acquire_read()
    print("two readers hold the lock together")
    rw.release_read()
    rw.release_read()
    rw.acquire_write()
    rw.release_write()
    print("a writer got it once both readers left")
