---
title: Deadlock
slug: 21-deadlock
part: "Part 5 — Concurrency"
summary: Learn the four conditions that cause deadlock, then detect it with a graph, avoid it with the Banker's algorithm, and prevent it with lock ordering.
minutes: 60
gpu: false
objectives:
  - State the four Coffman conditions, and name a real fix that breaks each one.
  - Build a wait-for graph and find a deadlock as a cycle.
  - Run the Banker's safety algorithm by hand and in code, and decide whether to grant a request.
  - Fix a dining-philosophers program with a global lock order.
prereqs:
  - 19-locks
  - 20-condition-variables-and-semaphores
exercise: 21-deadlock
---

# Deadlock

Locks and condition variables give threads a way to wait for each other. They
also give threads a way to wait for each other *forever*. A *deadlock* is a
state in which every thread in a group is waiting for something that only
another thread in the group can provide. Nobody can move, so nobody ever
provides it.

A deadlocked program does not crash and does not print an error. It sits there,
using no CPU, and the user sees a frozen window or a request that never
returns. It is also hard to reproduce, because it needs an unlucky schedule, as
in lesson 18.

This lesson gives you four tools: the conditions that make deadlock possible,
a graph that finds it, an algorithm that steers around it, and a lock-ordering
rule that rules it out.

## What you already know

- A lock lets one thread in and makes others wait (lessons 18 and 19).
- A blocked thread sleeps and does nothing until another thread wakes it
  (lesson 20).
- A schedule is an order of thread steps, and bugs can hide in rare schedules
  (lesson 18).
- A directed graph is nodes and arrows, and depth-first search walks along
  arrows as far as it can before backing up.

## The classic deadlock

Think of two people in a narrow corridor, each holding a door the other needs.
Neither can pass without the other's door, and neither lets go.

In code, this is two threads and two locks, taken in opposite orders.

```python
def transfer_1():
    with lock_a:
        with lock_b:      # waits for lock_b
            ...

def transfer_2():
    with lock_b:
        with lock_a:      # waits for lock_a
            ...
```

The following table shows the unlucky schedule.

```text
step  thread  action          holds       waits for
----  ------  --------------  ----------  ---------
 1    T1      lock(A)  ok     A
 2    T2      lock(B)  ok     A | B
 3    T1      lock(B)  blocks A           B (held by T2)
 4    T2      lock(A)  blocks             A (held by T1)

                T1 --waits for B--> T2
                T2 --waits for A--> T1      a cycle: deadlock
```

Most schedules are fine. If T1 runs both of its locks before T2 starts, nothing
goes wrong. The bug appears in a narrow window, so tests pass and production
hangs.

## The four conditions

In 1971, Coffman, Elphick, and Shoshani listed four conditions that must *all*
hold for a deadlock. They are a checklist: break any one, and deadlock cannot
happen.

| Condition | Meaning | One way to break it |
|---|---|---|
| Mutual exclusion | A resource is held by one thread at a time. | Use resources that can be shared, such as read-only data, or lock-free structures. |
| Hold and wait | A thread holds one resource while waiting for another. | Take every lock at once, or release what you hold before waiting. |
| No preemption | A resource cannot be forcibly taken from its holder. | Use `trylock`: if the second lock is busy, release the first and retry. |
| Circular wait | There is a loop of threads, each waiting for the next. | Give every lock a number, and always take them in increasing order. |

Circular wait is the easiest to break in practice, and lock ordering is the most
used fix. You will build it in this lesson.

> [!KEY]
> Deadlock needs all four conditions at once. To prevent it, you only need to
> make one of them impossible.

## Finding deadlock: the wait-for graph

A *wait-for graph* has one node per thread. It has an arrow from T to U when T
is waiting for a lock that U holds. A deadlock is a *cycle* in this graph: a
path that leads from a node back to itself.

Given a table of which thread owns which lock, and which locks each thread
wants, you can build the graph.

```text
  lock owner:  L1 -> A    L2 -> B    L3 -> C
  wants:       A wants L2     B wants L3     C wants L1

  A --> B       A wants L2, held by B
  B --> C       B wants L3, held by C
  C --> A       C wants L1, held by A

       A ---> B
       ^      |
       |      v
       +----- C            a cycle of length 3
```

A lock that nobody holds blocks nobody, so it adds no arrow. A thread that holds
locks but waits for nothing is a node with no outgoing arrows, which is fine.

For locks that allow one holder at a time, a cycle in the wait-for graph is
exactly a deadlock. The converse also holds: no cycle means every thread can
eventually finish. Other threads that wait on a deadlocked thread are blocked
too, but they are not on the cycle.

### Finding the cycle with depth-first search

Depth-first search (DFS) follows arrows as deep as possible. It colours each node:

- **unseen**: not visited yet,
- **on the current path**: visited, and DFS is still exploring its descendants,
- **finished**: fully explored, and no cycle was found through it.

If DFS meets a node that is *on the current path*, the path from that node to
the current one, plus the closing arrow, is a cycle.

```text
graph: A -> B,  B -> C,  C -> A

visit A       path [A]
  visit B     path [A, B]
    visit C   path [A, B, C]
      C -> A: A is on the path  =>  cycle is path from A: [A, B, C]
```

A *finished* node is not a cycle. In a diamond, A leads to B and C, and both lead
to D. DFS reaches D twice. The second time D is finished, not on the path, so DFS
correctly reports no cycle. Treating every seen node as a cycle is the most
common bug.

A thread that waits for itself, such as one that locks a non-reentrant lock twice,
is a cycle of length one.

## Preventing deadlock with lock ordering

Prevention changes the program so that deadlock cannot occur. Lock ordering
breaks circular wait. Number every lock. Every thread takes locks in increasing
number. Then a thread that waits for lock 7 holds only locks numbered below 7,
and a cycle would need some thread to wait for a lower number than the one it
holds, which the rule forbids.

### Dining philosophers

Dijkstra's puzzle gives the problem a face. Five philosophers sit at a round
table. A fork lies between each neighbouring pair, five forks in all. To eat, a
philosopher needs both adjacent forks. They think, get hungry, pick up forks,
eat, and put them down.

```text
  P0 -- f1 -- P1 -- f2 -- P2 -- f3 -- P3 -- f4 -- P4 -- f0 -- (back to P0)

  Philosopher i uses fork i and fork (i + 1) mod 5.
  P0: f0 and f1.   P4: f4 and f0.
```

The obvious rule is "pick up the left fork, then the right one", which is fork `i`
first, then fork `(i + 1) % 5`. If all five philosophers get hungry together
and each picks up their first fork, every fork is held and every philosopher
waits for the neighbour's fork. The wait-for graph is a circle of five.

```text
P0 holds f0, wants f1 (held by P1)
P1 holds f1, wants f2 (held by P2)
P2 holds f2, wants f3 (held by P3)
P3 holds f3, wants f4 (held by P4)
P4 holds f4, wants f0 (held by P0)       cycle of five: deadlock
```

Apply lock ordering. Each philosopher picks up the lower-numbered fork first.
Four philosophers are unchanged. P4 needs forks 4 and 0, and takes fork 0
first.

```text
P0: f0, f1    P1: f1, f2    P2: f2, f3    P3: f3, f4    P4: f0, f4
```

P0 and P4 both go for fork 0 first. If P4 gets it, P0 waits for it while
holding nothing, so no cycle forms. The longest chain ends at fork 4 with P3,
who holds fork 3 and needs fork 4. Fork 4's only other user is P4, who needs fork
0 before fork 4. Some philosopher can always take their second fork, eat, and
release. The circle is broken.

The same rule works for real software. When two functions both need the account
lock and the audit lock, pick an order, write it in a comment, and follow it
everywhere. In larger programs, the order is often by the address of the lock
object or an explicit rank number.

## Avoiding deadlock with the Banker's algorithm

Prevention rules out a condition for all programs. *Avoidance* is more flexible.
It lets all four conditions hold but refuses any request that could lead to
trouble. To do so, it needs to know in advance the most each process will ever
ask for.

Dijkstra named it the *Banker's algorithm*. A banker has a fixed amount of money
and lends it to clients. Each client declares a credit limit. The banker lends
only if, afterwards, there is still some order in which every client could
borrow up to their limit, finish, and repay.

A state is *safe* if such an order exists. The order is called a *safe sequence*.
An *unsafe* state does not have to deadlock, but it might, depending on what
processes ask for. The banker keeps the system out of unsafe states.

### The data

There are $n$ processes and $m$ resource types.

- `available[j]` is how many units of resource `j` are free.
- `max_need[i][j]` is the most of resource `j` that process `i` will ever hold.
- `allocation[i][j]` is how many units process `i` holds at the moment.
- `need[i][j] = max_need[i][j] - allocation[i][j]` is what it may still ask for.

### The safety algorithm

1. Set `work = available`. Mark every process unfinished.
2. Find an unfinished process whose `need` fits in `work`, meaning every entry of
   `need` is at most the matching entry of `work`.
3. Pretend it runs to completion and returns everything it holds. Add its
   `allocation` to `work`. Mark it finished and append it to the sequence.
4. Repeat from step 2. If every process is finished, the state is safe. If none
   fits, the state is unsafe.

### A worked example

Five processes, resources A, B, and C with totals (10, 5, 7). The state is:

```text
process   allocation   max       need = max - alloc
          A B C        A B C     A B C
P0        0 1 0        7 5 3     7 4 3
P1        2 0 0        3 2 2     1 2 2
P2        3 0 2        9 0 2     6 0 0
P3        2 1 1        2 2 2     0 1 1
P4        0 0 2        4 3 3     4 3 1

available = (3, 3, 2)
```

Check the totals: column A has 0+2+3+2+0 = 7 held plus 3 free, which is 10.
Column B is 2 held plus 3 free, which is 5. Column C is 5 held plus 2 free,
which is 7. The numbers are consistent.

The exercise picks the lowest-numbered process that fits, each time, scanning
from P0.

```text
step  work       candidates (need <= work)            pick   new work
----  ---------  -----------------------------------  -----  ---------
 1    (3,3,2)    P0 (7,4,3) no, P1 (1,2,2) yes         P1    (5,3,2)
 2    (5,3,2)    P0 no, P2 (6,0,0) no, P3 (0,1,1) yes  P3    (7,4,3)
 3    (7,4,3)    P0 (7,4,3) yes                         P0    (7,5,3)
 4    (7,5,3)    P2 (6,0,0) yes                         P2    (10,5,5)
 5    (10,5,5)   P4 (4,3,1) yes                         P4    (10,5,7)
```

The safe sequence is P1, P3, P0, P2, P4, and the final work vector equals the
totals (10, 5, 7), as it must. Other safe sequences exist, such as P1, P3, P4,
P0, P2. Any valid one proves safety.

### Granting a request

When process `i` asks for `request`, the banker does three tests in order.

1. If `request` is more than `need[i]`, the process broke its promise. Reject
   it as an error.
2. If `request` is more than `available`, the process must wait.
3. Otherwise, pretend to grant it: subtract from `available`, add to
   `allocation[i]`. Run the safety algorithm on the pretend state. If it is
   safe, grant. If not, the process waits.

Try three requests on the state above.

- **P1 asks for (1,0,2).** Within its need (1,2,2) and within available (3,3,2).
  The pretend state is available (2,3,0). The safety algorithm still finds
  P1, P3, P0, P2, P4. Grant.
- **P4 asks for (3,3,0), after that grant.** Available is only (2,3,0). Wait.
- **P0 asks for (0,2,0), after that grant.** Available is enough. But the
  pretend state has available (2,1,0), and no process's need fits: P1 needs
  (0,2,0) and only one unit of B is free, and P3 needs one unit of C and none is
  free. The state is unsafe, so P0 waits, even though the resources exist.

> [!KEY]
> A safe state means "there is an order that works if everyone behaves." An unsafe
> state means "deadlock is possible", not "deadlock has happened". The banker
> refuses to cross into unsafe territory.

## Detection and recovery

The third strategy is to allow deadlock and clean up. A system builds the
wait-for graph from time to time, and runs cycle detection. When it finds a
cycle, it breaks it: kill one thread, roll one back, or make it give up its
lock.

Databases do this. PostgreSQL waits `deadlock_timeout` (one second by default)
for a lock, then looks for a cycle among waiting transactions. If it finds one,
it aborts one transaction with a "deadlock detected" error, and the application
retries. This works because transactions can be undone.

Most operating systems take a fourth option, called the *ostrich algorithm*.
They ignore the problem and let the programmer deal with it. Deadlock in user
programs is rare, detection costs time, and killing a process may do more harm
than waiting. The Linux kernel prevents deadlock in its own code with ordering
rules, and the `lockdep` tool, enabled in debug builds, checks at runtime that
the kernel always takes locks in a consistent order.

## Try it on your own machine

1. Make a deadlock, and see it end by timeout. Two threads each hold a lock and
   try to take the other's.

   ```bash
   python3 -c "
   import threading
   a, b = threading.Lock(), threading.Lock()
   holding = threading.Barrier(2)
   tried = threading.Barrier(2)
   def worker(name, first, second):
       with first:
           holding.wait()
           got = second.acquire(timeout=0.5)
           print(name, 'got the second lock?', got)
           tried.wait()
           if got: second.release()
   ts = [threading.Thread(target=worker, args=('t1', a, b)),
         threading.Thread(target=worker, args=('t2', b, a))]
   [t.start() for t in ts]; [t.join() for t in ts]
   "
   ```

   Both lines print `False`: after half a second, neither thread could take its
   second lock. Without the timeout, this program would hang.

2. Ask Python where every thread is stuck.

   ```bash
   python3 -c "
   import faulthandler, threading, time
   l = threading.Lock(); l.acquire()
   threading.Thread(target=l.acquire, daemon=True).start()
   time.sleep(0.2)
   faulthandler.dump_traceback()
   "
   ```

   The dump lists each thread and the line where it waits. A hung production
   program can use `faulthandler.dump_traceback_later(60)`, or you can attach
   from outside with `py-spy dump --pid PID` (a separate install).

3. Look at the lock-ordering checker in the Linux kernel. This is Linux-only and
   needs a kernel built with `CONFIG_LOCKDEP`. Check for it.

   ```bash
   ls /proc/lockdep_stats 2>/dev/null || echo "this kernel has no lockdep"
   ```

   Distribution kernels usually omit it. Debug kernels include it.

## Build it step by step

1. **`wait_for_graph(owner, wants)`** takes `owner`, a dict from lock to the thread
   holding it, and `wants`, a dict from thread to the locks it is waiting for.
   Return a dict from every thread (in `wants` or among the owners) to the sorted
   list of threads it waits for. Skip locks that nobody owns. The usual mistake
   is leaving out threads that only hold locks.

2. **`find_cycle(graph)`** takes a dict from node to a list of nodes and returns
   a cycle as a list, or `None`. Use depth-first search with a path list and
   three colours. When you see an edge to a node that is on the current path,
   return `path[path.index(node):]`. Nodes can appear only as targets, so use
   `graph.get(node, [])`. The usual mistake is to report a cycle for any node
   already seen, which wrongly flags diamonds.

3. **`is_safe(available, max_need, allocation)`** runs the safety algorithm and
   returns a safe sequence as a list of process numbers, or `None`. Scan from
   the lowest process number every time. When a process finishes, add its
   *allocation* to `work`, not its need.

4. **`request_resources(available, max_need, allocation, tid, request)`** follows the
   three tests: `ValueError` when above need, `False` when above available,
   otherwise pretend to grant on *copies* and ask `is_safe`. Never change the
   caller's lists.

5. **`fork_order(i, n)`** returns the pair of fork numbers for philosopher `i`, the
   lower number first.

6. **`dine(n, meals)`** creates one `threading.Lock` per fork, then `n` threads. Each
   philosopher takes its forks in `fork_order`, with `time.sleep(0)` between the
   two takes to invite a context switch, eats, and releases. Return the meals
   each ate. Join with a timeout. If you call `fork_order` and then take the
   locks in a different order, the deadlock returns.

## Where this breaks

- **Banker's algorithm needs maximum claims in advance.** Few programs know how
  many locks or how much memory they will need. It also assumes a fixed number
  of processes. So real systems almost never use it, but the idea of safe states
  appears in many resource managers.
- **Ordering is a convention.** The compiler will not stop you from taking locks
  in the wrong order. Code reviews, lockdep in the kernel, and ThreadSanitizer's
  deadlock detector catch violations.
- **Orderings are hard to maintain.** When code calls a callback while holding a
  lock, the callback can take a lock that breaks the order. Real systems avoid
  calling unknown code with locks held.
- **Other waits are not locks.** A thread can wait for a message, a pipe, or a
  condition variable. These deadlocks do not appear in a lock graph. Two threads
  that each wait to receive from the other form a deadlock with no locks at all.
- **Livelock.** Threads that keep retrying and backing off can run forever without
  progress. They are not blocked, but they achieve nothing. Random delays
  between retries help.

## Further reading

- [OSTEP chapter 32, Common concurrency problems](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf) —
  deadlock causes, the four conditions, and prevention by lock ordering.
- [Coffman, Elphick, and Shoshani, "System Deadlocks" (1971)](https://dl.acm.org/doi/10.1145/356586.356588) —
  the paper that names the four conditions.
- [Linux kernel lockdep design](https://www.kernel.org/doc/html/latest/locking/lockdep-design.html) —
  how the kernel finds lock-order violations before they deadlock.
- [PostgreSQL: Deadlocks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-DEADLOCKS) —
  how a database detects a deadlock cycle and aborts a transaction.
- [Python `faulthandler`](https://docs.python.org/3/library/faulthandler.html) —
  dump every thread's stack, including from a watchdog timer, to find a hang.

## The exercise

You write the three ideas of this lesson in `starter.py`. `wait_for_graph` and
`find_cycle` detect deadlock. `is_safe` and `request_resources` implement the
Banker's algorithm. `fork_order` and `dine` prevent deadlock in dining
philosophers.

The checks use the textbook five-process example and compare your answers with
hand-computed values: the safe sequence, the unsafe state, and the three requests
above. For philosophers, the checks try every set of philosophers that could each
hold their first fork, and fail if your order leaves any possible circular wait.
They then run real threads, and fail with a message, not a hang, if the
philosophers stall.
