---
title: Swapping and page replacement
slug: 16-page-replacement
part: "Part 4 — Memory"
summary: Run programs bigger than RAM by keeping pages on disk, and compare the policies that choose which page to evict.
minutes: 55
gpu: false
objectives:
  - Describe what happens on a page fault when the page is on disk, step by step.
  - Count page faults for FIFO, LRU, Clock, and OPT on a reference string by hand and in code.
  - "Reproduce Belady's anomaly: FIFO can fault more when it is given more memory."
  - Say why real systems approximate LRU rather than implement it exactly.
prereqs:
  - 15-tlbs
exercise: 16-page-replacement
---

# Swapping and page replacement

So far every page of a process sat in a frame of RAM. Real machines do not have that luxury. You may run a browser, an editor, and a compiler whose pages add up to more than the RAM you own. Some pages must live somewhere else.

That somewhere is the disk. The operating system keeps the pages it needs soon in RAM, and parks the rest on disk. When a program touches a page that is parked, the system loads it back. RAM becomes a cache for a much larger disk-backed address space.

A cache that is full needs a rule for what to throw out. This rule is the **page-replacement policy**, and it decides how fast your machine feels. A good policy keeps the pages you are about to use. A bad one makes the machine crawl. This lesson builds four policies and counts their mistakes.

## What you already know

- A page table maps virtual pages to physical frames, and a `valid` bit says whether the mapping is usable.
- Touching an unmapped page raises a page fault, a trap into the kernel.
- A cache keeps a small copy of a larger store, and needs an eviction rule.
- LRU means "evict the item unused for the longest time", as in the TLB lesson.
- Reading from a disk is thousands of times slower than reading from RAM.

## Pages that live on disk

The page-table entry gains one more meaning. A page with `valid = 0` is not in RAM. Either it was never used, or the OS wrote it to disk. The OS records where it went. A real PTE has spare bits for this, and the kernel stores the disk location there.

The area of disk used for evicted pages is called **swap**. Linux can use a dedicated partition or a file.

When a program touches a page that is on disk, the machine runs this sequence:

1. The hardware sees `valid = 0` and raises a page fault.
2. The kernel looks up why. The page is legal but on disk, so this is not an error.
3. The kernel finds a free frame. If none is free, it picks a **victim** page with the replacement policy and evicts it. If the victim was modified, the kernel writes it to disk first.
4. The kernel reads the wanted page from disk into the frame. The process sleeps while this happens, and the scheduler runs something else.
5. The kernel updates the page table so the entry points to the frame and `valid = 1`.
6. The instruction that faulted runs again. This time it works.

Step 4 is the expensive one. A memory access takes about 100 ns. A disk read takes milliseconds on a spinning disk and around 100 microseconds on an SSD. Suppose one access in a thousand faults, memory costs 100 ns, and a fault costs 8 ms:

```text
average = 0.999 * 100 ns + 0.001 * 8,000,000 ns
        = 99.9 ns + 8,000 ns
        = about 8,100 ns
```

The program runs 81 times slower, with only one fault in a thousand accesses. The goal of any policy is simple: fewer faults.

> [!KEY]
> A page fault on a swapped-out page costs as much as hundreds of thousands of memory accesses. A replacement policy is judged by how few faults it causes.

## How to count faults

To compare policies we use a **reference string**: the list of page numbers a program touches, in order. We ignore offsets because they do not matter here. The string `1, 2, 3, 1` means: page 1, page 2, page 3, page 1 again.

Memory has `frames` slots and starts empty. The rule for counting is exact:

> A reference is a **fault** when its page is not in memory at that moment.

That includes cold misses. The first touch of any page is a fault, because memory started empty. Loading a page into a still-empty frame counts as a fault too. It is only when memory is full that a policy must choose a victim.

A hit costs nothing and is not counted. With 3 frames, the string `1, 2, 3, 1, 2, 3` faults 3 times, once per distinct page, and then hits three times.

Every policy below follows these counting rules and differs only in the victim it picks.

## FIFO: first in, first out

FIFO evicts the page that has been in memory the longest. Think of a queue at a shop: first to arrive is first to leave. FIFO needs no information about use, only a queue of arrival order. A hit does not change the order.

Here is FIFO with 3 frames on the classic reference string `1 2 3 4 1 2 5 1 2 3 4 5`. The queue is shown oldest on the left:

```text
ref   queue after     result   fault count
1     [1]             fault    1
2     [1 2]           fault    2
3     [1 2 3]         fault    3
4     [2 3 4]         fault    4   (evict 1)
1     [3 4 1]         fault    5   (evict 2)
2     [4 1 2]         fault    6   (evict 3)
5     [1 2 5]         fault    7   (evict 4)
1     [1 2 5]         hit
2     [1 2 5]         hit
3     [2 5 3]         fault    8   (evict 1)
4     [5 3 4]         fault    9   (evict 2)
5     [5 3 4]         hit
```

FIFO has 9 faults. Its weakness is that age does not mean uselessness. Page 1 is evicted at reference 4 although the program uses it again right away.

## LRU: least recently used

LRU evicts the page whose last use is furthest in the past. It bets that recent history predicts the near future, which is the locality idea again. Each hit moves the page to the "most recent" end, so LRU tracks use instead of arrival.

On the classic string with 3 frames, LRU faults 10 times, one more than FIFO. LRU is not always better than FIFO. This string cycles through pages in a pattern that suits FIFO. On real programs, LRU is better on average.

LRU has one strong property. Giving LRU more frames never increases its faults. The pages in a 4-frame LRU memory always include everything in a 3-frame LRU memory. Policies with this property are called **stack algorithms**.

## OPT: the best possible

Imagine you could see the future. When a victim is needed, evict the page whose next use is *furthest away*. If a page is never used again, it is the perfect victim. This is Belady's **OPT** policy, and it has the fewest faults of any policy on a given string.

OPT cannot be built, because the OS does not know what a program will do next. It matters as a yardstick: it tells you how close a real policy comes to the best possible result.

Here is one OPT decision on the classic string with 3 frames. Memory is `[1 2 3]` and reference 4 faults. The future after reference 4 is `1 2 5 1 2 3 4 5`:

```text
page 1 is next used 1 reference from now
page 2 is next used 2 references from now
page 3 is next used 6 references from now   <- furthest
evict 3
```

With OPT, the classic string causes 7 faults with 3 frames and 6 faults with 4 frames.

## Clock: a cheap LRU approximation

Exact LRU needs the system to record every memory access, which hardware does not do. Hardware does give us one cheap bit. The MMU sets an **accessed bit**, also called a **reference bit**, in the PTE whenever the page is used. The OS can read it and clear it.

**Clock**, also called second chance, uses that one bit. Picture the frames arranged in a circle with a clock hand pointing at one slot. Drawn flat, the circle is a row whose end wraps to its start:

```text
 slot 0   slot 1   slot 2
 [2:1]    [3:0]    [4:1]
   ^
   hand        each slot shows page:reference-bit
```

The hand that moves past slot 2 comes back to slot 0.

The rules in the exercise are exact, so follow them closely:

- A hit sets that page's reference bit to 1. The hand does not move.
- On a fault, look at the slot under the hand. If it is empty, or its bit is 0, load the new page there. If its bit is 1, clear the bit to 0 and advance the hand. Repeat.
- A freshly loaded page gets bit 1, and the hand advances to the next slot.

A page that was used since the hand last passed gets a second chance. A page that was not used is evicted. If every bit is 1, the hand goes all the way around, clearing bits, and evicts the first page it reached, which acts like FIFO.

Trace Clock with 3 frames on `2 3 2 1 5 2 4 5 3 2 5 2`. Each slot shows `page:bit`, and `h` is the hand position after the step:

```text
ref  action                                  slots              h
2    fault, load slot 0                      [2:1  _    _  ]    1
3    fault, load slot 1                      [2:1  3:1  _  ]    2
2    hit, set bit                            [2:1  3:1  _  ]    2
1    fault, load slot 2                      [2:1  3:1  1:1]    0
5    fault: clear 2, 3, 1; replace slot 0    [5:1  3:0  1:0]    1
2    fault: slot 1 has bit 0, replace 3      [5:1  2:1  1:0]    2
4    fault: slot 2 has bit 0, replace 1      [5:1  2:1  4:1]    0
5    hit                                     [5:1  2:1  4:1]    0
3    fault: clear 5, 2, 4; replace slot 0    [3:1  2:0  4:0]    1
2    hit, set bit                            [3:1  2:1  4:0]    1
5    fault: clear 2; slot 2 has bit 0        [3:1  2:0  5:1]    0
2    hit, set bit                            [3:1  2:1  5:1]    0
```

That is 8 faults. On the same string, FIFO has 9, LRU has 7, and OPT has 6. Clock lands between FIFO and LRU, which is typical.

Linux does not run this exact algorithm. It keeps "active" and "inactive" lists of pages and moves pages between them using the accessed bit, a descendant of the same idea. The textbook Clock is still the clearest model.

## Belady's anomaly

It feels certain that more memory means fewer faults. For FIFO it is not true. Run FIFO on the classic string with 4 frames:

```text
ref   queue after        result   fault count
1     [1]                fault    1
2     [1 2]              fault    2
3     [1 2 3]            fault    3
4     [1 2 3 4]          fault    4
1     [1 2 3 4]          hit
2     [1 2 3 4]          hit
5     [2 3 4 5]          fault    5   (evict 1)
1     [3 4 5 1]          fault    6   (evict 2)
2     [4 5 1 2]          fault    7   (evict 3)
3     [5 1 2 3]          fault    8   (evict 4)
4     [1 2 3 4]          fault    9   (evict 5)
5     [2 3 4 5]          fault    10  (evict 1)
```

Four frames cause 10 faults, one *more* than the 9 faults with three frames. This is **Belady's anomaly**. FIFO's 4-frame memory does not contain the 3-frame memory's pages, so extra memory can change the eviction order for the worse.

Here are the counts for each policy on this string:

| Frames | FIFO | LRU | Clock | OPT |
|---|---|---|---|---|
| 3 | 9 | 10 | 9 | 7 |
| 4 | 10 | 8 | 10 | 6 |

LRU and OPT improve with more frames, because they are stack algorithms. FIFO and Clock do not have the property. This is one reason to prefer policies that look at use.

> [!WARNING]
> The anomaly is rare on real programs, and the classic string is built to trigger it. Do not conclude that adding RAM makes systems slower. The lesson is that FIFO has no guarantee.

## Thrashing and dirty pages

When programs together need more pages than RAM holds, every fault evicts a page that is needed soon. The system spends its time moving pages between disk and RAM and does little useful work. This is **thrashing**. Systems fight it by keeping fewer processes in memory or, as Linux does, by killing a process with the out-of-memory killer.

The **dirty bit** is another cheap hardware bit. The MMU sets it when a page is written. Evicting a clean page costs nothing, because the disk copy is still good. Evicting a dirty page costs a disk write first. Real policies prefer clean victims when the choice is close.

## Try it on your own machine

1. Check how much memory and swap you have (Linux-only):

   ```bash
   grep -E 'MemTotal|MemAvailable|SwapTotal|SwapFree' /proc/meminfo
   ```

   Compare `SwapFree` with `SwapTotal`. A machine with swap enabled shows a non-zero total. Run `swapon --show` to see the swap devices.

2. Watch paging live (Linux-only):

   ```bash
   vmstat 1 5
   ```

   The `si` and `so` columns are kilobytes swapped in and out per second. On a quiet machine both are 0. Open many large programs and run it again to see them rise.

3. Count page faults of a real command (Linux-only):

   ```bash
   /usr/bin/time -v python3 -c "x = bytearray(200_000_000); x[::4096] = b'a' * len(x[::4096])" 2>&1 | grep -E 'page faults|Maximum resident'
   ```

   A **minor** fault finds the page in memory and only fixes the page table, such as the first touch of a fresh page. A **major** fault reads from disk. Expect tens of thousands of minor faults and few major ones. On macOS, `/usr/bin/time -l` prints similar counters.

4. Ask for a process's fault counts (Linux-only):

   ```bash
   python3 -c "import resource; r = resource.getrusage(resource.RUSAGE_SELF); print(r.ru_minflt, r.ru_majflt)"
   ```

   The two numbers are minor and major faults since the process started.

## Build it step by step

Open `starter.py`. Every function takes a list of page numbers `refs` and a number of `frames`, and returns the fault count. A page is a hit exactly when it is already in memory.

1. `fifo_faults(refs, frames)` keeps a `collections.deque` of resident pages in arrival order and a set for fast membership checks. On a fault with full memory, `popleft()` is the victim. A hit changes nothing. The common mistake is to refresh a page's position on a hit, which turns FIFO into LRU.

2. `lru_faults(refs, frames)` keeps an `OrderedDict` with the oldest use first. A hit calls `move_to_end`. On a fault with full memory, `popitem(last=False)` evicts. The common mistake is to forget the `move_to_end` on a hit.

3. `clock_faults(refs, frames)` keeps two lists of length `frames`, `pages` filled with `None` and `bits` filled with `0`, and an integer `hand`. Follow the three rules in the Clock section exactly. The common mistake is to advance the hand on a hit, or to forget to advance it after loading.

4. `opt_faults(refs, frames)` loops with an index `i`. On a fault with full memory, evict the resident page whose next use after `i` is farthest away. `refs.index(page, i + 1)` finds the next use, and a `ValueError` means never. The common mistake is to look for the next use from the start of the string.

5. `compare_policies(refs, frames)` returns `{"FIFO": ..., "LRU": ..., "Clock": ..., "OPT": ...}` by calling the four functions.

6. `find_belady(refs, max_frames, policy=fifo_faults)` tries `f = 1, 2, ...` up to `max_frames - 1`. It returns `(f, faults_f, faults_f_plus_1)` for the first `f` where more frames give more faults, or `None`.

## Where this breaks

- **OPT is impossible.** No system knows the future. Real kernels guess from the past, and some use hints from programs, such as `madvise` in Linux.
- **LRU is too expensive.** Updating a list on every memory access would slow every program. Clock-like schemes spend the cost only when the hand sweeps.
- **The reference bit is coarse.** One bit cannot tell a page used once from a page used a million times. Real kernels sample the bit over time, and keep a little history per page.
- **Scans pollute memory.** A program that reads a huge file once fills RAM with pages it never reuses. Linux separates active and inactive pages so that a one-time scan cannot flush the useful pages.
- **Memory pressure has no good answer.** When the working set of all processes exceeds RAM, no replacement policy saves you. Thrashing needs fewer processes, more RAM, or the out-of-memory killer.
- **Disks are not the only backing store.** Compressed memory (`zswap` on Linux) keeps evicted pages compressed in RAM, which turns a disk read into a cheaper decompression.

## Further reading

- [OSTEP chapter 21, Beyond Physical Memory: Mechanisms](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-beyondphys.pdf) covers swap space and the page-fault control flow.
- [OSTEP chapter 22, Beyond Physical Memory: Policies](https://pages.cs.wisc.edu/~remzi/OSTEP/vm-beyondphys-policy.pdf) covers OPT, FIFO, LRU, Clock, and thrashing, with the same kind of traces.
- [Belady, Nelson, and Shedler, "An anomaly in space-time characteristics of certain programs running in a paging machine" (1969)](https://dl.acm.org/doi/10.1145/363011.363155) is the paper that reported the anomaly.
- [The vmstat man page](https://man7.org/linux/man-pages/man8/vmstat.8.html) explains the `si` and `so` columns.
- [The getrusage man page](https://man7.org/linux/man-pages/man2/getrusage.2.html) documents `ru_minflt` and `ru_majflt`.

## The exercise

You write four replacement policies and two helpers. `fifo_faults`, `lru_faults`, `clock_faults`, and `opt_faults` each take a reference string and a frame count, and return the number of faults, counting cold misses. `compare_policies` runs all four. `find_belady` scans frame counts and reports the first place where a policy gets worse with more memory.

The checks use the hand traces in this lesson. They require 9 faults with 3 frames and 10 with 4 frames for FIFO on `1 2 3 4 1 2 5 1 2 3 4 5`, and 8 faults for Clock on the textbook string. They also verify properties on seeded random strings: OPT is never beaten, LRU never gets worse with more frames, and a memory with enough frames has only cold misses.
