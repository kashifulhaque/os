---
title: Condition variables and semaphores
slug: 20-condition-variables-and-semaphores
part: "Part 5 — Concurrency"
summary: Make threads wait for a condition without spinning, and build a bounded buffer, a semaphore, and a reader-writer lock from it.
minutes: 65
gpu: false
objectives:
  - Explain why a lock alone cannot make a thread wait for something to happen, and what a condition variable adds.
  - "Write the wait pattern correctly: hold the lock, wait in a `while` loop, and notify after changing state."
  - Build a bounded buffer, a counting semaphore, and a reader-writer lock from `threading.Condition`.
  - Say when to call `notify` and when `notify_all`.
prereqs:
  - 19-locks
exercise: 20-condition-variables-and-semaphores
---

# Condition variables and semaphores

A lock answers one question: "who may touch this data at this moment?" Many programs
need to answer a different one: "has the thing I need happened yet?" A consumer
thread needs an item to appear in a queue. A worker needs a job. A thread
reading a pipe needs data.

You could ask the question in a loop: lock, look, unlock, repeat. That is
*busy waiting*, and it burns a CPU core to learn nothing. This lesson shows the
tool that fixes it, the *condition variable*, and uses it to build three classic
structures: a bounded buffer, a semaphore, and a reader-writer lock. Here you work with real threads
throughout.

## What you already know

- A race condition comes from two threads touching shared data without
  coordination (lesson 18).
- A lock gives mutual exclusion, and `with lock:` is the safe way to use one
  (lessons 18 and 19).
- A blocked thread sleeps in the kernel and uses no CPU, and a spinning thread
  uses CPU while it waits (lesson 19).
- A thread that waits forever for something that never comes is stuck, and the
  program hangs.

## Waiting for a condition

Picture a sushi restaurant. A chef puts plates on a counter. Customers take
plates. The counter fits at most eight plates. If it is full, the chef must wait.
If it is empty, the customers must wait.

A lock protects the counter from two people grabbing the same plate. It does not
tell a customer to go to sleep until a plate arrives. A customer who checks the
counter every millisecond wastes effort, and the chef is slowed by the traffic.

A *condition variable* is a waiting room attached to a lock. A thread that
cannot proceed goes to sleep in the waiting room. A thread that changes the
situation knocks on the door and wakes a sleeper. In Python, it is a
`threading.Condition`. It has three operations, all used while holding the
lock:

- `wait()` releases the lock and puts the thread to sleep, in one atomic step.
  When the thread wakes, `wait()` reacquires the lock before it returns.
- `notify()` wakes one sleeping thread, if any.
- `notify_all()` wakes every sleeping thread.

The "in one atomic step" part matters. Suppose a consumer found the queue empty,
released the lock, and *then* went to sleep. A producer could add an item and
call `notify` in the gap. Nobody is asleep yet, so the notification is lost. The
consumer then sleeps while an item sits waiting. This is a *lost wakeup*.
Releasing the lock and sleeping as one step closes the gap.

## The pattern

Every use of a condition variable follows the same shape.

```python
cond = threading.Condition()          # makes its own lock

# The waiter:
with cond:                            # 1. hold the lock
    while not ready():                # 2. re-test in a loop
        cond.wait()                   # 3. sleep until notified
    use_the_thing()                   # 4. the condition is true, and you hold the lock

# The changer:
with cond:
    make_it_ready()
    cond.notify()                     # 5. wake a waiter, after changing the state
```

The state that the condition is about (`ready()`) is ordinary shared data, and
the lock protects it. The condition variable stores no state. It only lets
threads sleep and wake.

> [!KEY]
> A condition variable does not remember a notification. It is a waiting room,
> not a flag. The truth lives in the shared data, which the waiter re-tests under
> the lock.

## Why `while`, not `if`

Beginners write `if not ready(): cond.wait()`. It seems to say the same
thing. It is wrong, for three reasons.

1. **Someone else got there first.** After a notification, the woken thread must
   compete for the lock again. Before it gets the lock, another thread may take
   the item it was woken for.
2. **`notify_all` wakes everyone.** Five waiters wake for one item. Four of them
   must go back to sleep.
3. **Spurious wakeups.** POSIX allows a condition wait to return even though
   nobody notified. CPython's `Condition` is built from ordinary locks and rarely
   does this, but a pthread-based condition in C can. A portable program cannot
   count on it not happening.

The following table shows the `if` bug with two consumers and one item. The
buffer starts empty, and the producer calls `notify_all`.

```text
step  thread       action                          items in buffer
----  -----------  ------------------------------  ---------------
 1    consumer A   lock, buffer empty, wait()              0
 2    consumer B   lock, buffer empty, wait()              0
 3    producer     lock, put "x", notify_all()             1     (both wake up)
 4    consumer A   reacquires lock, takes "x"              0
 5    consumer B   reacquires lock, `if` is already
                   past, calls get on an empty buffer      0     <-- IndexError
```

With `while`, step 5 re-tests, finds the buffer empty, and waits again. The loop
is the safe version of the check, so use it everywhere.

> [!WARNING]
> Always wait in a `while` loop that re-tests the condition. The wait returns
> when waking is *possible*, not when the condition is *true*. Python also gives
> you `cond.wait_for(predicate)`, which writes the loop for you.

## The bounded buffer

A *bounded buffer* is a queue with a fixed capacity, shared by *producers* that
add items and *consumers* that remove them. It is the model for pipes, network
packet queues, and job queues. When it is full, producers wait. When it is
empty, consumers wait.

There are two different reasons to wait, so use two waiting rooms on one lock.

```python
class BoundedBuffer:
    def __init__(self, capacity):
        self._items = deque()
        self._lock = threading.Lock()
        self._not_full = threading.Condition(self._lock)
        self._not_empty = threading.Condition(self._lock)

    def put(self, item):
        with self._lock:
            while len(self._items) >= self.capacity:
                self._not_full.wait()
            self._items.append(item)
            self._not_empty.notify()
```

`put` waits on `_not_full`. After adding, it wakes one consumer from
`_not_empty`. `get` is the mirror image. Two conditions share one lock, so a
single mutual-exclusion region protects the data, and each kind of waiter has its
own room.

What if you used one condition for both? A consumer's `notify()` could wake
another sleeping consumer instead of the producer. That consumer finds the
buffer empty and goes back to sleep. The producer is never woken, every thread
sleeps, and the program stalls. With one condition you must use `notify_all`, at
the cost of waking everyone. Two conditions avoid that waste.

### Which notify?

Use `notify()` when exactly one waiter can proceed, and every waiter in that room
is interchangeable. One item added, one consumer woken: `notify()` is right.

Use `notify_all()` when several waiters might proceed, or when the waiters in one
room wait for different things. A reader-writer lock has both problems, so it
uses `notify_all()`. When in doubt, `notify_all()` with a `while` loop is always
correct. It is only slower.

### What the checks verify

You cannot test a threading program by running it once and looking. The checks
rely on facts that hold under every interleaving. All items come out exactly
once. Each producer's items keep their order, because the buffer is first in,
first out and a consumer sees them in buffer order. The number of items never
exceeds the capacity. A buggy `if` version fails these only sometimes, so the
checks include a case built to make it fail every time: two consumers, one item.

## Semaphores

A *semaphore* is a counter with two operations. Edsger Dijkstra named them `P`
and `V`, from Dutch words. Today they are called `acquire` (also `wait` or
`down`) and `release` (also `post` or `up`).

- `acquire` waits until the counter is above 0, then lowers it by one.
- `release` raises the counter by one.

Think of a car park with a fixed number of spaces. The counter is the number of
free spaces. A car enters only if the counter is positive, and it lowers the
counter. A car leaving raises it. A full car park makes cars wait at the gate.

Semaphores cover three jobs.

| Starting value | Use | Example |
|---|---|---|
| 1 | Mutual exclusion, a lock | Protect one counter. |
| N | Limit concurrency to N | At most 10 database connections. |
| 0 | A signal between threads | "The data is ready", where one thread releases and another acquires. |

A semaphore is one Condition, one counter, and a `while` loop. That is all it
takes.

```python
class Semaphore:
    def __init__(self, value=1):
        self._value = value
        self._cond = threading.Condition()

    def acquire(self):
        with self._cond:
            while self._value == 0:
                self._cond.wait()
            self._value -= 1
```

`release` adds one to the counter under the lock and calls `notify()`. Only one
waiter can use one unit, so `notify()` is enough.

> [!KEY]
> A semaphore is a counter plus a waiting room. A lock is a semaphore that
> counts to one. A condition variable is the more general tool: with it you can
> wait for any condition you can write as a Boolean expression.

Why have both? A semaphore remembers how many times `release` was called. A
condition variable remembers nothing. The semaphore's memory makes it good for
counting resources and sending signals. A condition variable is better when the
condition is complex, such as "the buffer is not full and no writer is waiting".

Python ships `threading.Semaphore`, and the exercise asks you to build your own so
you see what is inside. Linux provides POSIX semaphores (`sem_wait`, `sem_post`)
and System V semaphores (`semget`).

## The reader-writer lock

Many data structures are read far more often than they are written. A plain lock
forces readers to queue up one by one, though readers cannot hurt each other.

A *reader-writer lock* has two modes.

- Any number of readers may hold it together.
- A writer holds it alone: no readers, no other writers.

The state is a count of active readers and a flag for an active writer, both
under one Condition. Readers wait while a writer is inside. Writers wait while a
writer is inside or any reader is. The matrix shows who may enter at the same
time.

```text
                 reader inside    writer inside    nobody inside
new reader          enter             wait             enter
new writer          wait              wait             enter
```

When the last reader leaves, it must wake a waiting writer. When a writer leaves,
it must wake readers and writers. That mix of waiters is why the exercise uses
`notify_all()` here.

This version favours readers. As long as any reader is inside, further readers keep
entering, so a writer can wait forever if readers never stop. That is *writer
starvation*. A fairer lock makes arriving readers queue behind a waiting writer. Real
implementations choose a policy deliberately, and Linux's `pthread_rwlock_t`
lets you pick one.

## Try it on your own machine

1. Use the standard library's finished bounded buffer. `queue.Queue(maxsize=n)`
   is a bounded buffer built from the same parts.

   ```bash
   python3 -c "
   import queue, threading
   q = queue.Queue(maxsize=2)
   def producer():
       for i in range(6):
           q.put(i)
       q.put(None)
   threading.Thread(target=producer).start()
   while (item := q.get()) is not None:
       print('got', item)
   "
   ```

   You should see 0 to 5 in order. The producer sleeps whenever two items wait in
   the queue.

2. Watch a condition wait time out.

   ```bash
   python3 -c "
   import threading, time
   c = threading.Condition()
   with c:
       t = time.time()
       print(c.wait(timeout=0.3), round(time.time() - t, 1))
   "
   ```

   It prints `False 0.3`: nobody notified, so the wait returned after the
   timeout. `wait` returns `True` when a notification arrives first.

3. See the sleeping in the kernel. This is Linux-only and needs `strace`.

   ```bash
   strace -f -e trace=futex python3 -c "
   import threading, queue
   q = queue.Queue()
   t = threading.Thread(target=q.get); t.start()
   q.put(1); t.join()
   " 2>&1 | head
   ```

   When the `get` blocks first, it and the `put` that wakes it appear as `futex`
   calls, the same system call as in lesson 19.

4. List System V semaphores on the machine with `ipcs -s`. Most machines have
   none, and that is normal. Few programs use them today.

## Build it step by step

The starter imports `threading` and `deque` and gives you four things to write.

1. **`BoundedBuffer(capacity)`**: store a `deque`, a `Lock`, and two `Condition`
   objects made from that lock. `put` waits in a `while` loop while the buffer is
   full, appends, and calls `notify()` on the not-empty condition. `get` waits
   while it is empty, pops from the left, and notifies the not-full condition.
   `__len__` reads the length under the lock. Raise `ValueError` for a capacity
   below 1. The most common mistake is `if` in place of `while`. The second is
   waiting on the wrong condition.

2. **`Semaphore(value=1)`**: one `Condition` and a counter. `acquire` loops while
   the counter is 0, then decrements. `try_acquire` returns `False` instead of
   waiting. `release` increments and calls `notify()`. Raise `ValueError` for a
   negative start. The mistake is to decrement before the loop, which lets the
   counter go negative.

3. **`ReadWriteLock`**: one `Condition`, a reader count, and a `writing` flag.
   `acquire_read` waits while `writing`. `acquire_write` waits while `writing` or
   readers exist. Both release methods must call `notify_all()`, because both
   kinds of waiter may be asleep. The mistake is to notify only when the reader
   count reaches zero, and forget the writer's release.

4. **`run_pipeline(n_producers, n_consumers, per_producer, capacity)`**: build
   one `BoundedBuffer(capacity)`, start producer and consumer threads, and return
   what each consumer received. Producer `p` puts `(p, 0)`, `(p, 1)`, and so on.
   Consumers loop on `get()`. To stop them, join every producer first, then put
   one `None` per consumer. A consumer that gets `None` returns. This is a
   *poison pill*. Putting the pills before the producers finish strands items
   behind them. Join with timeouts and raise `RuntimeError` when a thread stays
   alive.

## Where this breaks

- **Forgetting the lock.** `wait` and `notify` must be called while holding the
  lock. Python raises `RuntimeError` if you do not. Some languages do not check.
- **Lost wakeups.** Changing the condition without the lock lets a waiter test,
  miss the change, and sleep forever. Always change the shared state under the
  lock, as in the pattern above.
- **Wrong waiter woken.** Mixing different waits in one condition with `notify()`
  can strand a thread. Use separate conditions, or `notify_all()`.
- **Starvation.** The reader-writer lock above starves writers. Fair versions
  cost throughput. No choice is best for every workload.
- **Fairness.** Neither a semaphore nor a condition variable promises that the
  longest waiter wakes first. Do not write code that depends on the wake order.
- **Hangs are quiet.** A program stuck in `wait()` prints nothing and uses no CPU.
  Give waits a timeout during development, and use `py-spy dump` or `gdb` to see
  where threads sleep.
- **Deadlock.** Waiting while holding other locks can make threads wait on each
  other in a cycle. That is the subject of lesson 21.

## Further reading

- [OSTEP chapter 30, Condition variables](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-cv.pdf) —
  the producer-consumer problem, why `while` matters, and the lost wakeup.
- [OSTEP chapter 31, Semaphores](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-sema.pdf) —
  semaphores as locks, as signals, and as the base for the reader-writer lock.
- [Python `threading.Condition`](https://docs.python.org/3/library/threading.html#condition-objects) —
  `wait`, `wait_for`, `notify`, and `notify_all` with their exact behaviour.
- [Python `queue`](https://docs.python.org/3/library/queue.html) —
  the standard library's ready-made bounded buffer.
- [pthread_cond_wait(3p)](https://man7.org/linux/man-pages/man3/pthread_cond_wait.3p.html) —
  the POSIX specification, including the statement that spurious wakeups may occur.
- [sem_overview(7)](https://man7.org/linux/man-pages/man7/sem_overview.7.html) —
  Linux's POSIX semaphores.

## The exercise

You write four things in `starter.py`: `BoundedBuffer`, `Semaphore`,
`ReadWriteLock`, and `run_pipeline`. Each uses `threading.Condition`.

The checks use real threads, and each one verifies something that holds under
every interleaving. A full buffer blocks `put` and an empty one blocks `get`. Two
consumers woken for one item must not take from an empty buffer. A semaphore
limits how many threads are inside. Readers share the lock and writers have it
alone. The pipeline delivers every item exactly once, keeps each producer's
order, and never lets the buffer hold more than its capacity. Every thread is
joined with a timeout, so a wrong answer fails with a message and does not hang.
