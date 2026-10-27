"""Condition variables and semaphores: a bounded buffer, a semaphore, and a
reader-writer lock, built on `threading.Condition`."""

from __future__ import annotations

import threading
from collections import deque


class BoundedBuffer:
    """A first-in, first-out queue that holds at most `capacity` items.

    put(item) blocks while the buffer is full. get() blocks while it is empty.
    len(buffer) is the number of items currently inside.
    """

    def __init__(self, capacity):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._items = deque()
        self._lock = threading.Lock()
        # Two conditions share one lock: producers wait on `_not_full`,
        # consumers wait on `_not_empty`.
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)

    def put(self, item):
        with self._lock:
            # `while`, not `if`: after waking, the buffer may be full again.
            while len(self._items) >= self.capacity:
                self._not_full.wait()
            self._items.append(item)
            self._not_empty.notify()

    def get(self):
        with self._lock:
            while not self._items:
                self._not_empty.wait()
            item = self._items.popleft()
            self._not_full.notify()
            return item

    def __len__(self):
        with self._lock:
            return len(self._items)


class Semaphore:
    """A counting semaphore built from a Condition.

    acquire() waits until the count is positive, then lowers it by one.
    release() raises it by one and wakes one waiter.
    """

    def __init__(self, value=1):
        if value < 0:
            raise ValueError("value must not be negative")
        self._value = value
        self._cond = threading.Condition()

    def acquire(self):
        with self._cond:
            while self._value == 0:
                self._cond.wait()
            self._value -= 1

    def try_acquire(self):
        """Take a unit if one is free right now. Never blocks. Returns True or False."""
        with self._cond:
            if self._value == 0:
                return False
            self._value -= 1
            return True

    def release(self):
        with self._cond:
            self._value += 1
            self._cond.notify()


class ReadWriteLock:
    """Many readers at once, or one writer alone, never both.

    This version prefers readers: while any reader is inside, new readers enter,
    so a steady stream of readers can starve a writer.
    """

    def __init__(self):
        self._cond = threading.Condition()
        self._readers = 0
        self._writing = False

    def acquire_read(self):
        with self._cond:
            while self._writing:
                self._cond.wait()
            self._readers += 1

    def release_read(self):
        with self._cond:
            self._readers -= 1
            if self._readers == 0:
                # Only writers can be waiting, and a writer needs zero readers.
                self._cond.notify_all()

    def acquire_write(self):
        with self._cond:
            while self._writing or self._readers > 0:
                self._cond.wait()
            self._writing = True

    def release_write(self):
        with self._cond:
            self._writing = False
            # Readers and writers may both be waiting, so wake everyone.
            self._cond.notify_all()


def run_pipeline(n_producers, n_consumers, per_producer, capacity):
    """Move items from producers to consumers through a BoundedBuffer.

    Producer p puts the tuples (p, 0), (p, 1), ... (p, per_producer - 1).
    Returns a list with one list per consumer: the items that consumer got, in
    the order it got them. Every item is delivered exactly once.
    """
    buffer = BoundedBuffer(capacity)
    received = [[] for _ in range(n_consumers)]

    def produce(p):
        for seq in range(per_producer):
            buffer.put((p, seq))

    def consume(c):
        while True:
            item = buffer.get()
            if item is None:  # poison pill: no more items are coming
                return
            received[c].append(item)

    producers = [threading.Thread(target=produce, args=(p,)) for p in range(n_producers)]
    consumers = [threading.Thread(target=consume, args=(c,)) for c in range(n_consumers)]
    for t in producers + consumers:
        t.start()
    for t in producers:
        t.join(timeout=20)
        if t.is_alive():
            raise RuntimeError("a producer did not finish")
    # Every real item is in the buffer or already taken. One pill per consumer.
    for _ in consumers:
        buffer.put(None)
    for t in consumers:
        t.join(timeout=20)
        if t.is_alive():
            raise RuntimeError("a consumer did not finish")
    return received


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
